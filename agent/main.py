"""AI Interview Fase 2 — LiveKit Agents worker (PRD "Berikutnya" §5).

Proses long-running TERPISAH dari backend FastAPI — paradigma pertama di
codebase AEOS (semua yang lain request/response). Join room LiveKit,
jalankan pipeline STT->LLM->TTS, kirim transkrip balik ke backend lewat
REST begitu selesai.

LLM/reasoning TETAP lewat endpoint OpenAI-compatible yang SAMA dipakai
fitur teks lain (AI_BASE_URL/AI_API_KEY/AI_MODEL). STT self-hosted (via
STT_BASE_URL ke faster-whisper-server). TTS **BUKAN** self-hosted --
dicoba `facebook/mms-tts-ind` self-hosted (service `tts-server/`) lebih
dulu, tapi kualitasnya dinilai jelek oleh Brian setelah didengar langsung
(2026-09-02), jadi diganti ke TTS OpenAI (`AI_BASE_URL` yang sama dengan
LLM) -- lihat `docs/02-product/PRD.md` §5 untuk riwayat keputusannya.

Agent TIDAK akses database/tenant-context langsung — cuma REST client ke
backend, pakai `invite_token` yang sama sebagai kredensial (diteruskan
lewat job/room dispatch metadata, lihat `backend/.../service.py::
start_voice_session`). Ini sengaja, bukan keterbatasan: `_score()`/
`set_tenant()` tetap satu-satunya sumber kebenaran di backend.

CATATAN KEJUJURAN (lihat plan file): wiring end-to-end (dispatch, room
join, sesi WebRTC, sintesis TTS) sudah diverifikasi jalan lewat
`docker compose --profile voice up` sungguhan. Latensi percakapan nyata
dan turn-taking masih BELUM PERNAH diuji nyata (butuh GPU yang tidak
tersedia saat pass ini ditulis) -- STT tetap self-hosted CPU-mode di dev.
Turn detector (2026-09-24) sama: model terpasang & termuat, tapi
kalibrasi `endpointing` belum diuji dengan kandidat sungguhan.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from interview_flow import InterviewFlow, build_instructions, format_transcript
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    cli,
    function_tool,
    get_job_context,
    inference,
    room_io,
)
from livekit.plugins import openai as lk_openai
from livekit.plugins import silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-interview-agent")

# Harus sama persis dengan `_VOICE_AGENT_NAME` di
# `backend/app/modules/ai_interview/service.py` — LiveKit mencocokkan
# dispatch eksplisit by name, bukan otomatis ke semua room.
AGENT_NAME = "ai-interview-agent"

BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://backend:8000/api/v1").rstrip("/")
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
# Kunci tanda tangan request agent -> backend (endpoint khusus agent:
# voice/context, voice/complete, voice/recording). Sama dengan yang dipakai
# backend (`ai_interview.service.agent_signature`); kandidat tidak punya.
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")
STT_BASE_URL = os.environ["STT_BASE_URL"]
# Bahasa dipaksa (bukan deteksi otomatis): Whisper lebih akurat untuk bahasa
# Indonesia kalau bahasanya diberi tahu, dan turn detector memakai bahasa
# ini untuk memilih cara menilai "kalimat sudah selesai atau belum".
STT_LANGUAGE = os.environ.get("STT_LANGUAGE") or "id"
# SENGAJA sama dengan backend's AI_BASE_URL/AI_API_KEY/AI_MODEL -- LLM
# TIDAK self-hosted terpisah, lihat catatan strategi AI di PRD §14. TTS
# JUGA lewat endpoint ini sekarang (lihat docstring di atas) -- bukan
# base_url terpisah lagi.
LLM_BASE_URL = os.environ["AI_BASE_URL"]
LLM_API_KEY = os.environ.get("AI_API_KEY") or "not-needed"
# AI_AGENT_MODEL opsional: model khusus agen suara. Simulasi alur Fase 4
# (2026-09-25, 6 run/model): gpt-4o-mini kadang mengarang pertanyaan atau
# bertanya susulan tanpa izin tool (4/6 bersih); gpt-4.1-mini 6/6 bersih.
LLM_MODEL = os.environ.get("AI_AGENT_MODEL") or os.environ.get("AI_MODEL") or "gpt-4o-mini"
TTS_MODEL = os.environ.get("AI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.environ.get("AI_TTS_VOICE", "ash")
TTS_INSTRUCTIONS = "Speak natural, professional Bahasa Indonesia with a warm interviewer tone."


def _agent_headers(token: str) -> dict[str, str]:
    sig = hmac.new(LIVEKIT_API_SECRET.encode(), token.encode(), hashlib.sha256).hexdigest()
    return {"X-Agent-Signature": sig}


def _recording_allowed() -> bool:
    """Rekaman HANYA kalau servernya self-hosted. Perekam bawaan LiveKit
    Agents mengunggah audio ke LiveKit Cloud bila LIVEKIT_URL mengarah ke
    *.livekit.cloud atau LIVEKIT_OBSERVABILITY_URL diisi -- rekaman suara
    kandidat (data biometrik, UU PDP) tidak boleh keluar ke pihak ketiga."""
    if os.environ.get("LIVEKIT_OBSERVABILITY_URL"):
        return False
    host = (urlparse(LIVEKIT_URL).hostname or "").lower()
    return not host.endswith("livekit.cloud")


class InterviewAgent(Agent):
    """Satu instance per sesi interview. Fase 4 roadmap: alur terstruktur --
    LLM hanya melihat satu pertanyaan aktif lewat tool `next_question`,
    kuota pertanyaan susulan & syarat penutupan dijaga `InterviewFlow`
    (lihat interview_flow.py untuk alasannya)."""

    def __init__(self, *, token: str, context: dict) -> None:
        super().__init__(instructions=build_instructions(context))
        self._token = token
        self.flow = InterviewFlow(questions=list(context.get("questions") or []))
        self.submitted = False

    def _user_turns(self) -> int:
        """Jumlah giliran bicara kandidat (penjagaan "sudah dijawab")."""
        return sum(
            1
            for item in self.session.history.items
            if getattr(item, "role", None) == "user" and getattr(item, "text_content", None)
        )

    @function_tool
    async def next_question(self) -> str:
        """Ambil pertanyaan interview berikutnya. Panggil setelah menyapa
        kandidat, dan setiap kali jawaban untuk pertanyaan aktif sudah cukup."""
        return self.flow.next_question(len(self.session.history.items), self._user_turns())

    @function_tool
    async def request_follow_up(self) -> str:
        """Minta izin mengajukan SATU pertanyaan susulan untuk pertanyaan
        aktif, bila jawaban kandidat kabur atau kurang contoh konkret."""
        return self.flow.request_follow_up(self._user_turns())

    @function_tool
    async def end_interview(
        self, context: RunContext, candidate_requested_stop: bool = False
    ) -> str:
        """Panggil SETELAH semua pertanyaan diajukan (next_question menyatakan
        selesai) -- menandai percakapan selesai, memicu penilaian, lalu
        mengucapkan penutup yang diberikan tool ini. `candidate_requested_stop=true`
        hanya bila kandidat sendiri minta berhenti di tengah jalan."""
        refusal = self.flow.end_refusal(candidate_requested_stop, self._user_turns())
        if refusal:
            return refusal
        transcript = _format_transcript(self.session, self.flow)
        try:
            await _submit_transcript(self._token, transcript)
            self.submitted = True
        except Exception:  # noqa: BLE001 - jangan sampai kegagalan submit bikin agent macet
            logger.exception("Gagal mengirim transkrip ke backend untuk token %s", self._token)

        # Pola `EndCallTool` bawaan LiveKit: balasan tool (kalimat penutup)
        # diputar di speech handle yang SAMA, jadi job baru dimatikan setelah
        # handle itu selesai. Dulu `room.disconnect()` langsung di sini --
        # apa pun yang diucapkan setelah tool terpotong.
        def _shutdown(_handle) -> None:
            get_job_context().shutdown(reason="interview_selesai")

        context.speech_handle.add_done_callback(_shutdown)
        return self.flow.closing_instruction(candidate_requested_stop)


async def _fetch_context(token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.get(
            f"{BACKEND_API_URL}/ai-interview/session/{token}/voice/context",
            headers=_agent_headers(token),
        )
        resp.raise_for_status()
        return resp.json()


async def _submit_transcript(token: str, transcript: str) -> None:
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            f"{BACKEND_API_URL}/ai-interview/session/{token}/voice/complete",
            json={"transcript": transcript},
            headers=_agent_headers(token),
        )
        resp.raise_for_status()


async def _upload_recording(token: str, path: Path) -> None:
    """Unggah rekaman sesi ke backend (disimpan di object storage), lalu
    HAPUS salinan lokal di agent -- rekaman biometrik tidak boleh
    menumpuk di disk worker. Dicoba 3x; gagal total tetap dihapus lokal
    (dicatat di log) daripada tersimpan tanpa kendali retensi."""
    try:
        data = path.read_bytes()
        if not data:
            return
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120) as http:
                    resp = await http.post(
                        f"{BACKEND_API_URL}/ai-interview/session/{token}/voice/recording",
                        content=data,
                        headers={**_agent_headers(token), "Content-Type": "audio/ogg"},
                    )
                    if resp.status_code == 409:
                        return  # sudah tersimpan sebelumnya
                    resp.raise_for_status()
                    return
            except Exception:  # noqa: BLE001
                logger.warning("Upload rekaman percobaan %d gagal", attempt + 1, exc_info=True)
                await asyncio.sleep(2 * (attempt + 1))
        logger.error("Rekaman sesi tidak terunggah setelah 3 percobaan -- salinan lokal dihapus")
    finally:
        path.unlink(missing_ok=True)


def _format_transcript(session: AgentSession, flow: InterviewFlow) -> str:
    items = [
        (getattr(item, "role", None) or "", getattr(item, "text_content", None) or "")
        for item in session.history.items
    ]
    return format_transcript(items, flow.markers)


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    token = ctx.job.metadata
    if not token:
        logger.error("Job tanpa metadata (invite_token) -- keluar tanpa mulai sesi")
        return

    context = await _fetch_context(token)

    session = AgentSession(
        stt=lk_openai.STT(base_url=STT_BASE_URL, api_key="not-needed", language=STT_LANGUAGE),
        llm=lk_openai.LLM(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, model=LLM_MODEL),
        tts=lk_openai.TTS(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            model=TTS_MODEL,
            voice=TTS_VOICE,
            instructions=TTS_INSTRUCTIONS,
        ),
        vad=silero.VAD.load(),
        # Roadmap Fase 1 #4. Dulu hanya VAD: begitu kandidat diam sesaat
        # (wajar saat berpikir di tengah jawaban interview), AI langsung
        # memotong. Turn detector menilai dari ISI kalimat apakah kandidat
        # memang sudah selesai bicara. `version="v1-mini"` DIPAKSA: model
        # lokal (~108 MB, mendukung "id"); tanpa ini library memilih "v1"
        # yang lewat gateway LiveKit Cloud di mode dev -- Aeos self-hosted.
        # (Plugin lama `livekit.plugins.turn_detector` deprecated di 1.7.)
        turn_handling={
            "turn_detection": inference.TurnDetector(version="v1-mini"),
            # Lebih sabar dari default (0.5/3.0 dtk): interview = jawaban
            # panjang dengan jeda berpikir, beda dari percakapan CS singkat.
            # max_delay = batas tunggu saat model menilai kalimat belum usai.
            "endpointing": {"min_delay": 0.8, "max_delay": 6.0},
        },
    )

    agent = InterviewAgent(token=token, context=context)

    record = _recording_allowed()
    if not record:
        logger.warning("LIVEKIT_URL mengarah ke LiveKit Cloud -- sesi TIDAK direkam")

    async def _finalize() -> None:
        """Jalan saat job selesai (kandidat menutup panggilan ATAU agent
        memanggil end_interview): tutup sesi supaya file rekaman selesai
        ditulis, kirim transkrip kalau belum terkirim (dulu interview yang
        diputus kandidat tidak pernah sampai ke backend), lalu unggah rekaman."""
        await session.aclose()
        if not agent.submitted:
            transcript = _format_transcript(session, agent.flow)
            if "Kandidat:" in transcript:
                try:
                    await _submit_transcript(token, transcript)
                    agent.submitted = True
                except Exception:  # noqa: BLE001
                    logger.exception("Gagal mengirim transkrip parsial saat sesi berakhir")
        audio = Path(ctx.session_directory) / "audio.ogg"
        if record and audio.exists() and agent.submitted:
            await _upload_recording(token, audio)
        else:
            audio.unlink(missing_ok=True)

    ctx.add_shutdown_callback(_finalize)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(),
        # Hanya audio (2 kanal: 0 = kandidat, 1 = pewawancara AI) ke file
        # lokal session_directory/audio.ogg; traces/log/transkrip ke cloud mati.
        record={"audio": record, "traces": False, "logs": False, "transcript": False},
    )
    # Pertanyaan pertama disisipkan kode (lihat InterviewFlow.opening_instruction).
    await session.generate_reply(
        instructions=agent.flow.opening_instruction(len(session.history.items))
    )


if __name__ == "__main__":
    cli.run_app(server)
