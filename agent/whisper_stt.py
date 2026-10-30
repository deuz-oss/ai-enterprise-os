"""STT faster-whisper-server dengan filter halusinasi (lihat whisper_filter.py).

Pengganti `livekit.plugins.openai.STT`: plugin itu meminta
`response_format="json"` untuk semua model selain `whisper-1`, jadi
`no_speech_prob` per segmen tidak pernah sampai ke agen, dan batas waktu
bacanya terkunci 30 dtk (STT_TIMEOUT_SEC tidak pernah berlaku). Non-streaming,
sama seperti plugin untuk model non-realtime: AgentSession memotong audio
dengan VAD lalu memanggil `recognize()` per segmen.

Transkrip kosong (semua segmen bukan ucapan) diabaikan AgentSession
(`audio_recognition`: `if not transcript: return`) -- tidak ada giliran
kosong yang dikirim ke LLM.
"""

from __future__ import annotations

import json
import logging

import httpx
import numpy as np
from livekit import rtc
from livekit.agents import (
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    LanguageCode,
    stt,
)
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from livekit.agents.utils import AudioBuffer
from whisper_filter import segment_stats, speech_text

logger = logging.getLogger("ai-interview-agent.stt")


class WhisperSTT(stt.STT):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        language: str,
        no_speech_threshold: float,
        min_rms: float = 0.0,
        log_stats: bool = False,
    ) -> None:
        super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))
        self._url = f"{base_url.rstrip('/')}/audio/transcriptions"
        self._model = model
        self._language = language
        self._threshold = no_speech_threshold
        self._min_rms = min_rms
        self._log_stats = log_stats

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "faster-whisper-server"

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        frame = rtc.combine_audio_frames(buffer)
        pcm = np.frombuffer(bytes(frame.data), dtype=np.int16).astype(np.float32) / 32768
        rms = float(np.sqrt(np.mean(pcm**2))) if pcm.size else 0.0
        if rms < self._min_rms:
            # Derau yang memicu VAD -- jangan beri Whisper kesempatan
            # mengarang teks (lihat DEFAULT_MIN_RMS). Transkrip kosong
            # diabaikan AgentSession.
            self._log("skipped", frame.duration, rms, [])
            return _event("", self._language)
        data = frame.to_wav_bytes()
        try:
            async with httpx.AsyncClient(timeout=conn_options.timeout) as http:
                resp = await http.post(
                    self._url,
                    files={"file": ("file.wav", data, "audio/wav")},
                    data={
                        "model": self._model,
                        "language": self._language,
                        "response_format": "verbose_json",
                    },
                )
        except httpx.TimeoutException:
            raise APITimeoutError() from None
        except httpx.HTTPError as exc:
            raise APIConnectionError() from exc
        if resp.status_code >= 400:
            raise APIStatusError(
                "faster-whisper-server gagal", status_code=resp.status_code, body=resp.text
            )
        try:
            body = resp.json()
            text = speech_text(body, self._threshold)
        except ValueError as exc:
            raise APIConnectionError() from exc
        self._log("transcribed", frame.duration, rms, segment_stats(body, self._threshold))
        return _event(text, self._language)

    def _log(self, action: str, duration: float, rms: float, segments: list) -> None:
        if not self._log_stats:
            return
        # Satu baris JSON per potongan VAD; tanpa teks (data pribadi).
        logger.info(
            "stt-stats %s",
            json.dumps(
                {
                    "action": action,
                    "audio_sec": round(duration, 2),
                    "rms": round(rms, 4),
                    "segments": segments,
                }
            ),
        )


def _event(text: str, language: str) -> stt.SpeechEvent:
    return stt.SpeechEvent(
        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
        alternatives=[stt.SpeechData(language=LanguageCode(language), text=text)],
    )
