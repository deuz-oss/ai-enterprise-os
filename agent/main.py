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
"""

from __future__ import annotations

import logging
import os

import httpx
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, function_tool, room_io
from livekit.plugins import openai as lk_openai
from livekit.plugins import silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-interview-agent")

# Harus sama persis dengan `_VOICE_AGENT_NAME` di
# `backend/app/modules/ai_interview/service.py` — LiveKit mencocokkan
# dispatch eksplisit by name, bukan otomatis ke semua room.
AGENT_NAME = "ai-interview-agent"

BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://backend:8000/api/v1").rstrip("/")
STT_BASE_URL = os.environ["STT_BASE_URL"]
# SENGAJA sama dengan backend's AI_BASE_URL/AI_API_KEY/AI_MODEL -- LLM
# TIDAK self-hosted terpisah, lihat catatan strategi AI di PRD §14. TTS
# JUGA lewat endpoint ini sekarang (lihat docstring di atas) -- bukan
# base_url terpisah lagi.
LLM_BASE_URL = os.environ["AI_BASE_URL"]
LLM_API_KEY = os.environ.get("AI_API_KEY") or "not-needed"
LLM_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
TTS_MODEL = os.environ.get("AI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.environ.get("AI_TTS_VOICE", "ash")
TTS_INSTRUCTIONS = (
    "Speak natural, professional Bahasa Indonesia with a warm interviewer tone."
)


class InterviewAgent(Agent):
    """Satu instance per sesi interview. `end_interview` adalah tool yang
    LLM panggil sendiri setelah menilai semua topik sudah tergali dan sudah
    menyampaikan penutup ke kandidat -- bukan dipicu kode Python."""

    def __init__(
        self, *, token: str, room, title: str, objective: str | None, topics: list[dict]
    ) -> None:
        topic_lines = "\n".join(f"- {t['prompt']}" for t in topics) or "(tidak ada topik spesifik)"
        instructions = (
            f'Anda pewawancara AI untuk posisi terkait "{title}". {objective or ""}\n\n'
            "Ajukan topik-topik berikut secara natural dalam percakapan (boleh tidak "
            "berurutan kaku, boleh tanya susulan yang relevan), dalam Bahasa Indonesia, "
            "nada profesional tapi hangat:\n"
            f"{topic_lines}\n\n"
            "Setelah semua topik cukup tergali, ucapkan penutup yang sopan ke kandidat, "
            "LALU panggil tool `end_interview`. Jangan menilai kandidat secara lisan "
            "(itu dilakukan sistem terpisah setelah percakapan selesai). Jangan mengarang "
            "informasi tentang posisi/perusahaan di luar yang diberikan."
        )
        super().__init__(instructions=instructions)
        self._token = token
        self._room = room

    @function_tool
    async def end_interview(self) -> str:
        """Panggil SETELAH semua topik sudah digali DAN Anda sudah
        mengucapkan salam penutup ke kandidat -- menandai percakapan selesai,
        memicu penilaian, dan mengakhiri panggilan."""
        transcript = _format_transcript(self.session)
        try:
            await _submit_transcript(self._token, transcript)
        except Exception:  # noqa: BLE001 - jangan sampai kegagalan submit bikin agent macet
            logger.exception("Gagal mengirim transkrip ke backend untuk token %s", self._token)
        await self._room.disconnect()
        return "Interview ditutup, terima kasih atas waktunya."


async def _fetch_context(token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.get(f"{BACKEND_API_URL}/ai-interview/session/{token}/voice/context")
        resp.raise_for_status()
        return resp.json()


async def _submit_transcript(token: str, transcript: str) -> None:
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            f"{BACKEND_API_URL}/ai-interview/session/{token}/voice/complete",
            json={"transcript": transcript},
        )
        resp.raise_for_status()


def _format_transcript(session: AgentSession) -> str:
    lines: list[str] = []
    for item in session.history.items:
        role = getattr(item, "role", None)
        text = getattr(item, "text_content", None)
        if role and text:
            speaker = "Kandidat" if role == "user" else "Pewawancara AI"
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    token = ctx.job.metadata
    if not token:
        logger.error("Job tanpa metadata (invite_token) -- keluar tanpa mulai sesi")
        return

    context = await _fetch_context(token)

    session = AgentSession(
        stt=lk_openai.STT(base_url=STT_BASE_URL, api_key="not-needed"),
        llm=lk_openai.LLM(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, model=LLM_MODEL),
        tts=lk_openai.TTS(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            model=TTS_MODEL,
            voice=TTS_VOICE,
            instructions=TTS_INSTRUCTIONS,
        ),
        vad=silero.VAD.load(),
    )

    agent = InterviewAgent(
        token=token,
        room=ctx.room,
        title=context["title"],
        objective=context.get("objective"),
        topics=context["questions"],
    )

    await session.start(room=ctx.room, agent=agent, room_options=room_io.RoomOptions())
    await session.generate_reply(
        instructions=(
            "Sapa kandidat, perkenalkan diri singkat sebagai pewawancara AI, "
            "lalu mulai interview."
        )
    )


if __name__ == "__main__":
    cli.run_app(server)
