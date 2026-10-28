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
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
from collections.abc import Callable
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

    async def start_session(self, room: str, agent_identity: str) -> tuple[int, dict]:
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
        renderer = self._renderer_factory()
        try:
            await asyncio.wait_for(
                renderer.start(self.settings.reference_image), self.settings.start_timeout
            )
        except (RendererUnavailable, TimeoutError, OSError) as exc:
            self.slots.release(room)
            await renderer.aclose()
            logger.warning("Renderer tidak siap untuk room %s: %r", room, exc)
            return 503, {"detail": f"renderer tidak siap: {exc}"}
        task = asyncio.create_task(self._run(room, agent_identity, renderer))
        self.tasks[room] = task

        def _done(t: asyncio.Task[None]) -> None:
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
        except (ValueError, KeyError, TypeError):
            return web.json_response({"detail": "body tidak valid"}, status=400)
        if not _verified(request, room, service.settings.api_secret):
            return web.json_response({"detail": "tanda tangan salah"}, status=401)
        status, payload = await service.start_session(room, agent_identity)
        return web.json_response(payload, status=status)

    async def delete_session(request: web.Request) -> web.Response:
        room = request.match_info["room"]
        if not _verified(request, room, service.settings.api_secret):
            return web.json_response({"detail": "tanda tangan salah"}, status=401)
        await service.stop_session(room)
        return web.Response(status=204)

    async def health(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "renderer": service.settings.renderer,
                "active": service.slots.active,
                "max_sessions": service.slots.max_sessions,
            }
        )

    app = web.Application()
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
