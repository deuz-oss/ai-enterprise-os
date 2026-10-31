"""avatar-worker -- wajah video pewawancara AI, proses terpisah dari agen.

Agen (agent/avatar.py) memanggil `POST /sessions` sebelum sesi interview
dimulai. Worker menyiapkan renderer, lalu join room LiveKit sebagai peserta
`ai-interview-avatar` (kind agent, atribut `lk.publish_on_behalf` = identitas
agen -- cara resmi LiveKit menandai avatar, dipakai frontend & RoomIO),
menerima audio TTS lewat `DataStreamAudioReceiver`, dan mempublikasikan video
+ audio tersinkron lewat `AvatarRunner`. Otak interview (STT/LLM/TTS, alur,
rubrik, penilaian) tetap milik agen & backend -- worker hanya "wajah".

Endpoint ditandatangani HMAC LIVEKIT_API_SECRET atas nama room (pola sama
dengan X-Agent-Signature agen -> backend). Port tidak dibuka ke host.

Foto wajah: per tenant. Agen mengambil foto tenant dari backend dan
mengirimnya sebagai `reference_image_b64` di body POST; worker menulisnya ke
file sementara per room (dihapus saat sesi berakhir / start gagal). Tanpa
field itu (tenant belum punya foto, atau base64 rusak) dipakai foto bawaan
env `AVATAR_REFERENCE_IMAGE`. Tanda tangan tetap atas room saja: worker
hanya terjangkau dari jaringan internal Docker (agen), bukan dari host.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import hashlib
import hmac
import logging
import os
import tempfile
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path

from aiohttp import web
from capacity import SessionSlots
from livekit import api, rtc
from livekit.agents.voice.avatar import AvatarOptions, AvatarRunner, DataStreamAudioReceiver
from livekit.agents.voice.room_io import ATTRIBUTE_PUBLISH_ON_BEHALF
from renderers import (
    FPS,
    HEIGHT,
    SAMPLE_RATE,
    WIDTH,
    AvatarRenderer,
    RendererUnavailable,
    make_renderer,
)
from video_gen import RendererVideoGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("avatar-worker")

# Harus sama dengan AVATAR_IDENTITY di agent/avatar_fallback.py.
AVATAR_IDENTITY = "ai-interview-avatar"
SIGNATURE_HEADER = "X-Avatar-Signature"
# Foto tenant dinormalisasi backend (JPEG <= 1024 px, biasanya < 1 MB);
# batas longgar untuk foto 5 MB yang belum ternormalisasi. Body POST memuat
# base64 (+33%), jadi batas body aiohttp (default 1 MB) dinaikkan.
MAX_REFERENCE_IMAGE_BYTES = 6 * 1024 * 1024
CLIENT_MAX_SIZE = 8 * 1024 * 1024


@dataclass(frozen=True)
class WorkerSettings:
    livekit_url: str
    api_key: str
    api_secret: str
    renderer: str = "static"
    max_sessions: int = 2
    reference_image: Path | None = None
    start_timeout: float = 15.0
    max_session_sec: float = 3600.0

    @classmethod
    def from_env(cls) -> WorkerSettings:
        ref = os.environ.get("AVATAR_REFERENCE_IMAGE") or ""
        return cls(
            livekit_url=os.environ.get("LIVEKIT_URL", ""),
            api_key=os.environ.get("LIVEKIT_API_KEY", ""),
            api_secret=os.environ.get("LIVEKIT_API_SECRET", ""),
            renderer=(os.environ.get("AVATAR_RENDERER") or "static").lower(),
            max_sessions=int(os.environ.get("AVATAR_MAX_SESSIONS") or 2),
            reference_image=Path(ref) if ref else None,
            start_timeout=float(os.environ.get("AVATAR_START_TIMEOUT") or 15),
            max_session_sec=float(os.environ.get("AVATAR_MAX_SESSION_SEC") or 3600),
        )


def sign(secret: str, room: str) -> str:
    return hmac.new(secret.encode(), room.encode(), hashlib.sha256).hexdigest()


def decode_reference_image(raw: object) -> bytes | None:
    """`reference_image_b64` dari agen -> bytes, atau None (pakai foto env)
    bila tidak ada, bukan base64 sah, kosong, atau terlalu besar."""
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        logger.warning("reference_image_b64 bukan string -- foto bawaan env dipakai")
        return None
    if len(raw) > (MAX_REFERENCE_IMAGE_BYTES // 3 + 1) * 4:
        logger.warning("reference_image_b64 terlalu besar -- foto bawaan env dipakai")
        return None
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        logger.warning("reference_image_b64 rusak -- foto bawaan env dipakai")
        return None
    return data or None


def _write_temp_image(data: bytes) -> Path | None:
    """File sementara per sesi (renderer menerima path). None = gagal tulis
    (disk penuh, dsb.) -> foto bawaan env."""
    try:
        fd, name = tempfile.mkstemp(prefix="avatar-ref-", suffix=".jpg")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    except OSError:
        logger.warning("Gagal menulis foto avatar sementara -- foto bawaan env", exc_info=True)
        return None
    return Path(name)


def _discard_temp_image(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Gagal menghapus foto avatar sementara %s", path, exc_info=True)


def avatar_token(settings: WorkerSettings, room: str, agent_identity: str) -> str:
    return (
        api.AccessToken(settings.api_key, settings.api_secret)
        .with_identity(AVATAR_IDENTITY)
        .with_name("Pewawancara AI (avatar)")
        .with_kind("agent")
        .with_attributes({ATTRIBUTE_PUBLISH_ON_BEHALF: agent_identity})
        .with_grants(api.VideoGrants(room_join=True, room=room, can_publish=True))
        .to_jwt()
    )


class AvatarService:
    def __init__(
        self,
        settings: WorkerSettings,
        renderer_factory: Callable[[], AvatarRenderer] | None = None,
    ) -> None:
        self.settings = settings
        self.slots = SessionSlots(settings.max_sessions)
        self._renderer_factory = renderer_factory or (
            lambda: make_renderer({**os.environ, "AVATAR_RENDERER": settings.renderer})
        )
        self.tasks: dict[str, asyncio.Task[None]] = {}
        # Satu start per room pada satu waktu. Tanpa ini dua POST bersamaan
        # untuk room yang sama sama-sama lolos (task baru tercatat setelah
        # renderer siap, slot room yang sama dianggap sudah dipegang) ->
        # dua avatar beridentitas sama, dan sesi pertama yang selesai
        # melepas slot milik sesi kedua.
        # Nilai: (lock, jumlah permintaan yang memegang/menunggu). Dihapus
        # saat hitungan 0 -- nama room unik per interview, jangan menumpuk.
        self._start_locks: dict[str, tuple[asyncio.Lock, int]] = {}

    @contextlib.asynccontextmanager
    async def _room_lock(self, room: str) -> AsyncIterator[None]:
        lock, users = self._start_locks.get(room, (asyncio.Lock(), 0))
        self._start_locks[room] = (lock, users + 1)
        try:
            async with lock:
                yield
        finally:
            lock, users = self._start_locks[room]
            if users <= 1:
                del self._start_locks[room]
            else:
                self._start_locks[room] = (lock, users - 1)

    async def start_session(
        self, room: str, agent_identity: str, reference_image: bytes | None = None
    ) -> tuple[int, dict]:
        async with self._room_lock(room):
            return await self._start_session_locked(room, agent_identity, reference_image)

    async def release_session(self, room: str) -> None:
        """DELETE dari agen. Lewat lock yang sama dengan start: agen yang
        menyerah menunggu POST (timeout -> voice-only) bisa mengirim DELETE
        saat start masih berjalan -- aiohttp tidak membatalkan handler saat
        klien putus, jadi tanpa lock avatar tetap join sebagai wajah bisu
        di sesi voice-only dan menahan slot sampai interview selesai."""
        async with self._room_lock(room):
            await self.stop_session(room)

    async def _start_session_locked(
        self, room: str, agent_identity: str, reference_image: bytes | None
    ) -> tuple[int, dict]:
        if room in self.tasks:
            # Job agen diulang untuk room yang sama: avatar lama diganti.
            await self.stop_session(room)
        if not self.slots.try_acquire(room):
            logger.warning(
                "Kapasitas avatar penuh (%d/%d) -- room %s voice-only",
                self.slots.active,
                self.slots.max_sessions,
                room,
            )
            return 503, {
                "detail": f"kapasitas avatar penuh ({self.slots.active}/{self.slots.max_sessions})"
            }
        # File sementara baru ditulis SETELAH slot didapat: permintaan yang
        # ditolak karena penuh tidak meninggalkan apa pun di disk.
        temp_image = _write_temp_image(reference_image) if reference_image else None
        image = temp_image or self.settings.reference_image
        renderer = self._renderer_factory()
        try:
            await asyncio.wait_for(renderer.start(image), self.settings.start_timeout)
        except (RendererUnavailable, TimeoutError, OSError) as exc:
            self.slots.release(room)
            await renderer.aclose()
            _discard_temp_image(temp_image)
            logger.warning("Renderer tidak siap untuk room %s: %r", room, exc)
            return 503, {"detail": f"renderer tidak siap: {exc}"}
        except BaseException:
            _discard_temp_image(temp_image)
            raise
        task = asyncio.create_task(self._run(room, agent_identity, renderer))
        self.tasks[room] = task

        def _done(t: asyncio.Task[None]) -> None:
            # Callback, bukan `finally` di _run: tetap jalan walau task
            # dibatalkan sebelum sempat mulai (coroutine tidak pernah masuk).
            _discard_temp_image(temp_image)
            if self.tasks.get(room) is t:
                del self.tasks[room]

        task.add_done_callback(_done)
        return 201, {"identity": AVATAR_IDENTITY}

    async def stop_session(self, room: str) -> None:
        task = self.tasks.get(room)
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def _run(self, room_name: str, agent_identity: str, renderer: AvatarRenderer) -> None:
        room = rtc.Room()
        runner: AvatarRunner | None = None
        try:
            token = avatar_token(self.settings, room_name, agent_identity)
            # auto_subscribe mati: avatar tidak perlu mendengar/ melihat
            # kandidat. Video kandidat tidak pernah diambil apalagi dinilai.
            await room.connect(
                self.settings.livekit_url, token, rtc.RoomOptions(auto_subscribe=False)
            )
            agent_left = asyncio.Event()

            def _on_left(participant: rtc.RemoteParticipant) -> None:
                if participant.identity == agent_identity:
                    agent_left.set()

            room.on("participant_disconnected", _on_left)
            room.on("disconnected", lambda *_: agent_left.set())
            # Agen sudah pergi sebelum avatar tersambung (job crash di jendela
            # POST -> connect): event di atas tidak akan pernah datang, slot
            # GPU tertahan sampai max_session_sec.
            if agent_identity not in room.remote_participants:
                agent_left.set()

            runner = AvatarRunner(
                room,
                audio_recv=DataStreamAudioReceiver(room, sender_identity=agent_identity),
                video_gen=RendererVideoGenerator(renderer),
                options=AvatarOptions(
                    video_width=WIDTH,
                    video_height=HEIGHT,
                    video_fps=FPS,
                    audio_sample_rate=SAMPLE_RATE,
                    audio_channels=1,
                ),
            )
            await runner.start()
            logger.info("Avatar aktif di room %s", room_name)
            try:
                await asyncio.wait_for(agent_left.wait(), self.settings.max_session_sec)
            except TimeoutError:
                logger.warning("Sesi avatar %s melewati batas durasi -- diakhiri", room_name)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Sesi avatar %s gagal", room_name)
        finally:
            if runner is not None:
                await runner.aclose()
            await renderer.aclose()
            await room.disconnect()
            self.slots.release(room_name)
            logger.info("Avatar keluar dari room %s", room_name)


def _verified(request: web.Request, room: str, secret: str) -> bool:
    given = request.headers.get(SIGNATURE_HEADER, "")
    return bool(secret) and hmac.compare_digest(given, sign(secret, room))


def create_app(service: AvatarService) -> web.Application:
    async def post_session(request: web.Request) -> web.Response:
        try:
            body = await request.json()
            room, agent_identity = str(body["room"]), str(body["agent_identity"])
            raw_image = body.get("reference_image_b64")
        except (ValueError, KeyError, TypeError, AttributeError):
            return web.json_response({"detail": "body tidak valid"}, status=400)
        if not _verified(request, room, service.settings.api_secret):
            return web.json_response({"detail": "tanda tangan salah"}, status=401)
        status, payload = await service.start_session(
            room, agent_identity, decode_reference_image(raw_image)
        )
        return web.json_response(payload, status=status)

    async def delete_session(request: web.Request) -> web.Response:
        room = request.match_info["room"]
        if not _verified(request, room, service.settings.api_secret):
            return web.json_response({"detail": "tanda tangan salah"}, status=401)
        await service.release_session(room)
        return web.Response(status=204)

    async def health(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "renderer": service.settings.renderer,
                "active": service.slots.active,
                "max_sessions": service.slots.max_sessions,
            }
        )

    app = web.Application(client_max_size=CLIENT_MAX_SIZE)
    app.add_routes(
        [
            web.post("/sessions", post_session),
            web.delete("/sessions/{room}", delete_session),
            web.get("/health", health),
        ]
    )
    return app


if __name__ == "__main__":
    settings = WorkerSettings.from_env()
    if settings.reference_image is not None and not settings.reference_image.is_file():
        logger.warning("AVATAR_REFERENCE_IMAGE %s tidak ada", settings.reference_image)
    web.run_app(create_app(AvatarService(settings)), port=int(os.environ.get("PORT") or 8090))
