"""Avatar video pewawancara AI -- lem ke LiveKit Agents 1.7.1.

Mekanisme resmi LiveKit untuk avatar di proses terpisah: agent mengganti
`session.output.audio` dengan `DataStreamAudioOutput` (audio TTS dikirim
lewat byte stream topik `lk.audio_stream` ke peserta avatar), worker avatar
memakai `DataStreamAudioReceiver` + `AvatarRunner` dan mempublikasikan
video+audio tersinkron. API diverifikasi langsung di source livekit-agents
1.7.1 (`livekit/agents/voice/avatar/`), lihat avatar-worker/README.md.

Rekaman audio.ogg: `RecorderIO` membungkus output apa pun yang terpasang,
jadi kanal suara AI tetap terekam -- ditulis saat worker mengirim RPC
`lk.playback_finished` (AvatarRunner melakukannya per segmen).

Dua jalur jatuh ke voice-only:
1. Sebelum sesi: worker tidak menjawab / penuh / avatar tidak join dalam
   AVATAR_JOIN_TIMEOUT -> output audio tidak diganti, RoomIO mempublikasikan
   audio agen seperti biasa. WAJIB dicek sebelum sesi: `DataStreamAudioOutput`
   menunggu peserta avatar TANPA batas waktu -- tanpa pengecekan ini agen
   diam selamanya bila worker tidak pernah datang.
2. Di tengah sesi: peserta avatar keluar (worker crash) -> sink audio di
   dasar rantai output ditukar ke track audio room milik agen sendiri
   (`_AudioSinkProxy.set_next_in_chain`, titik tukar bawaan 1.7.1). Bila
   rantai tidak punya titik tukar, sesi diakhiri rapi (transkrip parsial
   tetap terkirim lewat _finalize di main.py) daripada kandidat menunggu
   pewawancara yang tidak bersuara.

CATATAN: jalur 2 memakai dua kelas PRIVAT LiveKit (`_AudioSinkProxy`,
`_ParticipantAudioOutput`). Versi dikunci 1.7.1 dan agent/tests mengecek
import-nya -- upgrade livekit-agents wajib cek ulang modul ini.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from avatar_fallback import AvatarSettings, release_avatar, request_avatar, wait_ready
from livekit import rtc
from livekit.agents import AgentSession, JobContext, get_job_context, utils
from livekit.agents.voice.avatar import DataStreamAudioOutput
from livekit.agents.voice.io import AudioOutput, _AudioSinkProxy
from livekit.agents.voice.room_io._output import _ParticipantAudioOutput

logger = logging.getLogger("ai-interview-agent.avatar")

# Sama dengan default RoomIO (AudioOutputOptions.sample_rate) dan keluaran
# TTS OpenAI, jadi tidak ada resample tambahan di kedua jalur.
AUDIO_SAMPLE_RATE = 24000


def find_sink_proxy(output: AudioOutput | None) -> _AudioSinkProxy | None:
    """Telusuri rantai output audio sampai titik tukar sink di dasarnya."""
    node = output
    while node is not None:
        if isinstance(node, _AudioSinkProxy):
            return node
        node = node.next_in_chain
    return None


class AvatarLink:
    """Avatar aktif untuk satu sesi: memantau kepergian peserta avatar dan
    menjalankan fallback di tengah sesi."""

    def __init__(
        self,
        *,
        ctx: JobContext,
        session: AgentSession,
        identity: str,
        settings: AvatarSettings,
        secret: str,
    ) -> None:
        self._ctx = ctx
        self._session = session
        self.identity = identity
        self._settings = settings
        self._secret = secret
        self.active = True
        self._fallback_output: _ParticipantAudioOutput | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    def watch(self) -> None:
        self._ctx.room.on("participant_disconnected", self._on_participant_disconnected)

    def _on_participant_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        if participant.identity != self.identity or not self.active:
            return
        self.active = False
        logger.warning("Avatar keluar di tengah sesi -- beralih ke voice-only")
        task = asyncio.create_task(self._fall_back())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _fall_back(self) -> None:
        proxy = find_sink_proxy(self._session.output.audio)
        if proxy is None:
            logger.error("Rantai audio tanpa titik tukar -- sesi diakhiri rapi")
            get_job_context().shutdown(reason="avatar_hilang")
            return
        try:
            out = _ParticipantAudioOutput(
                self._ctx.room,
                sample_rate=AUDIO_SAMPLE_RATE,
                num_channels=1,
                track_publish_options=rtc.TrackPublishOptions(
                    source=rtc.TrackSource.SOURCE_MICROPHONE
                ),
            )
            await out.start()
            # Segmen yang sedang diputar avatar ditandai terputus oleh proxy
            # (wait_for_playout tidak menggantung); ucapan berikutnya lewat
            # track audio agen sendiri.
            proxy.set_next_in_chain(out)
            self._fallback_output = out
        except Exception:  # noqa: BLE001
            logger.exception("Fallback audio gagal -- sesi diakhiri rapi")
            get_job_context().shutdown(reason="avatar_hilang")

    async def aclose(self) -> None:
        self._ctx.room.off("participant_disconnected", self._on_participant_disconnected)
        await utils.aio.cancel_and_wait(*self._tasks)
        if self._fallback_output is not None:
            await self._fallback_output.aclose()
        async with httpx.AsyncClient() as http:
            await release_avatar(
                http, self._settings, room=self._ctx.room.name, secret=self._secret
            )


async def _avatar_published_video(room: rtc.Room, identity: str) -> None:
    await utils.wait_for_participant(room=room, identity=identity)
    await utils.wait_for_track_publication(
        room=room, identity=identity, kind=rtc.TrackKind.KIND_VIDEO
    )


async def setup_avatar(
    ctx: JobContext, session: AgentSession, settings: AvatarSettings, secret: str
) -> AvatarLink | None:
    """Pasang avatar sebelum `session.start`. None = jalan voice-only.
    Tidak pernah raise: kegagalan avatar tidak boleh menggagalkan interview."""
    try:
        # Identitas agen baru ada setelah terhubung; connect() idempoten,
        # session.start nanti tidak menyambung ulang.
        await ctx.connect()
        room = ctx.room
        async with httpx.AsyncClient() as http:
            decision = await request_avatar(
                http,
                settings,
                room=room.name,
                agent_identity=room.local_participant.identity,
                secret=secret,
            )
            if not decision.enabled:
                logger.warning("Avatar tidak dipakai, sesi voice-only: %s", decision.reason)
                return None
            joined = await wait_ready(
                _avatar_published_video(room, decision.identity), settings.join_timeout
            )
            if not joined:
                logger.warning(
                    "Avatar tidak join dalam %.0f dtk -- sesi voice-only", settings.join_timeout
                )
                await release_avatar(http, settings, room=room.name, secret=secret)
                return None

        session.output.audio = DataStreamAudioOutput(
            room,
            destination_identity=decision.identity,
            sample_rate=AUDIO_SAMPLE_RATE,
            # Waktu mulai bicara diambil saat avatar BENAR-BENAR mulai memutar
            # (RPC lk.playback_started dari AvatarRunner), bukan saat audio
            # dikirim -- renderer menambah jeda (FlashHead >= 1 chunk), dan
            # waktu ini dipakai offset transkrip & posisi suara AI di rekaman.
            wait_playback_start=True,
        )
        link = AvatarLink(
            ctx=ctx, session=session, identity=decision.identity, settings=settings, secret=secret
        )
        link.watch()
        ctx.add_shutdown_callback(link.aclose)
        logger.info("Avatar video aktif (identitas %s)", decision.identity)
        return link
    except Exception:  # noqa: BLE001
        logger.exception("Setup avatar gagal -- sesi voice-only")
        return None
