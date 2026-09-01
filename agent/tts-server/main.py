"""Wrapper OpenAI-compatible `/v1/audio/speech` di sekitar `facebook/mms-tts-ind`
(AI Interview Fase 2, PRD "Berikutnya" §5).

Kenapa model ini, bukan Kokoro: Kokoro TIDAK mendukung Bahasa Indonesia sama
sekali (issue GitHub terbuka sejak Jan 2025, belum dijawab) — ditemukan
lewat riset langsung saat mendesain fitur ini, bukan asumsi dari riset
arsitektur awal. `facebook/mms-tts-ind` adalah model VITS resmi dari
proyek Meta MMS khusus Bahasa Indonesia.

Endpoint sengaja meniru skema `POST {base_url}/audio/speech` OpenAI (dipanggil
`livekit-plugins-openai`'s `TTS` class dengan `base_url` custom) — model
tunggal (satu suara, tidak ada pilihan voice sungguhan), field `voice`/`speed`
diterima tapi diabaikan.

CATATAN KEJUJURAN: wiring/skema endpoint ini benar, TAPI kualitas suara
Bahasa Indonesia dari model ini belum pernah didengar langsung di sesi ini
(butuh mengunduh model + GPU/CPU nyata) -- lihat plan file.
"""

from __future__ import annotations

import io
import logging
from contextlib import asynccontextmanager

import numpy as np
import scipy.io.wavfile
import torch
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from transformers import AutoTokenizer, VitsModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts-mms-id")

MODEL_NAME = "facebook/mms-tts-ind"

_model: VitsModel | None = None
_tokenizer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _tokenizer
    logger.info("Memuat model %s ...", MODEL_NAME)
    _model = VitsModel.from_pretrained(MODEL_NAME)
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    _model.eval()
    logger.info("Model %s siap (sampling_rate=%s)", MODEL_NAME, _model.config.sampling_rate)
    yield


app = FastAPI(title="AEOS TTS (facebook/mms-tts-ind)", lifespan=lifespan)


class SpeechIn(BaseModel):
    input: str
    model: str | None = None  # diabaikan -- satu model tetap
    voice: str | None = None  # diabaikan -- MMS-TTS-IND satu suara
    response_format: str | None = None  # selalu balikin WAV terlepas nilai ini
    speed: float | None = None  # belum didukung


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "loaded": _model is not None}


@app.post("/v1/audio/speech")
def synthesize(payload: SpeechIn) -> Response:
    if _model is None or _tokenizer is None:
        raise HTTPException(status_code=503, detail="Model belum selesai dimuat")
    text = payload.input.strip()
    if not text:
        raise HTTPException(status_code=422, detail="input tidak boleh kosong")

    inputs = _tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        waveform = _model(**inputs).waveform

    audio = waveform.squeeze().cpu().numpy().astype(np.float32)
    # livekit-agents' WAV decoder cuma dukung PCM 16-bit -- scipy.io.wavfile.write
    # dengan array float32 langsung menulis WAV format float 32-bit (IEEE), yang
    # ditolak decoder itu (ValueError: "Unsupported WAV bits per sample: 32").
    # Konversi eksplisit ke int16 PCM, ditemukan lewat pengujian nyata (bukan
    # dugaan) saat verifikasi wiring docker compose --profile voice up.
    pcm16 = np.clip(audio, -1.0, 1.0)
    pcm16 = (pcm16 * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    scipy.io.wavfile.write(buf, rate=_model.config.sampling_rate, data=pcm16)
    return Response(content=buf.getvalue(), media_type="audio/wav")
