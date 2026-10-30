"""Buang halusinasi Whisper dari respons `verbose_json` faster-whisper-server.

Modul ini TANPA import LiveKit supaya bisa dites tanpa infra suara (pola
sama dengan interview_flow.py). Kelas STT-nya ada di `whisper_stt.py`.

Masalah (uji di browser 2026-10-29): VAD agen kadang memotong segmen yang
isinya bukan ucapan -- hening, desis, dengung, napas, klik keyboard, sisa
gema suara AI. Whisper tetap "mengisi" segmen seperti itu dengan teks dari
data latih subtitle YouTube: untuk bahasa Indonesia hampir selalu "Terima
kasih." / "Terima kasih kerana menonton." (Melayu). Agen lalu menganggapnya
jawaban kandidat; di template satu pertanyaan interview langsung ditutup.

Sinyalnya `no_speech_prob` per segmen. Kalibrasi faster-whisper-small, bahasa
id, 2026-10-29 (suara OpenAI TTS bersih / berderau / pelan):
- ucapan sungguhan, termasuk "Terima kasih.", "Ya", "Sudah": 0.01 - 0.47
- hening, derau putih, dengung 100 Hz, napas, klik: 0.78 - 0.92
Ambang 0.6 memisahkan keduanya dengan jarak di kedua sisi. Aturan bawaan
Whisper (no_speech_prob > 0.6 DAN avg_logprob < -1.0) TIDAK menangkapnya:
avg_logprob halusinasi ini -0.56 s.d. -0.74. Ganti model STT = kalibrasi ulang.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger("ai-interview-agent.stt")

DEFAULT_NO_SPEECH_THRESHOLD = 0.6
# Halusinasi jenis kedua: decoding berulang ("saya akan melakukannya" x26,
# "cuket-cuket-cuket..."), terlihat di uji mikrofon sungguhan 2026-10-29
# dengan compression_ratio 14.18 (ucapan sungguhan di rekaman yang sama
# 0.79-1.95). 2.4 = `compression_ratio_threshold` bawaan Whisper sendiri
# untuk menandai decoding gagal. Tidak bisa diatur lewat env: ini batas
# baku Whisper, bukan hasil kalibrasi per model.
MAX_COMPRESSION_RATIO = 2.4


# Gerbang energi: potongan VAD yang lebih pelan dari ini tidak dikirim ke
# Whisper sama sekali. Kalibrasi mikrofon sungguhan 2026-10-29 (Chrome,
# peredam derau + AGC bawaan browser, satu ruangan, satu pembicara):
# derau non-ucapan (ketukan, napas, batuk, kursi) RMS 0.0036-0.0098 --
# dua di antaranya lolos filter no_speech_prob ("Tunggu" 0.589, "Selamat
# tinggal" 0.353, rentang ucapan); ucapan sungguhan termasuk "Ya." pelan
# RMS 0.047-0.052. 0.02 = jarak ~2x ke kedua sisi. Data masih sedikit --
# kalibrasi ulang dengan STT_LOG_STATS=1 di ruangan/perangkat lain.
DEFAULT_MIN_RMS = 0.02


def parse_min_rms(raw: str | None) -> float:
    """STT_MIN_RMS; 0 mematikan gerbang."""
    try:
        value = float(raw) if raw else DEFAULT_MIN_RMS
    except ValueError:
        logger.warning("STT_MIN_RMS=%r bukan angka -- dipakai default", raw)
        return DEFAULT_MIN_RMS
    return max(value, 0.0)


def parse_threshold(raw: str | None) -> float:
    try:
        value = float(raw) if raw else DEFAULT_NO_SPEECH_THRESHOLD
    except ValueError:
        logger.warning("STT_NO_SPEECH_THRESHOLD=%r bukan angka -- dipakai default", raw)
        return DEFAULT_NO_SPEECH_THRESHOLD
    # >= 1 mematikan filter (tidak ada segmen dengan no_speech_prob >= 1).
    return min(max(value, 0.0), 1.0)


def speech_text(body: Mapping[str, Any], threshold: float) -> str:
    """Teks dari segmen yang memang ucapan (bukan hening/derau, bukan
    decoding berulang). Respons tanpa `segments` (server tidak mendukung
    verbose_json) dikembalikan apa adanya."""
    segments = body.get("segments")
    if not isinstance(segments, list):
        return str(body.get("text") or "").strip()
    kept: list[str] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        try:
            no_speech = float(seg.get("no_speech_prob", 0.0))
            compression = float(seg.get("compression_ratio", 0.0))
        except (TypeError, ValueError):
            no_speech, compression = 0.0, 0.0
        if no_speech >= threshold or compression > MAX_COMPRESSION_RATIO:
            # Isi teks sengaja TIDAK dicatat: bila ambang meleset, itu ucapan
            # kandidat sungguhan (data pribadi) yang tidak boleh masuk log.
            logger.info(
                "Segmen halusinasi dibuang (no_speech_prob %.2f, compression_ratio %.2f, "
                "%d karakter)",
                no_speech,
                compression,
                len(text),
            )
            continue
        if text:
            kept.append(text)
    return " ".join(kept)


# Frasa halusinasi Whisper yang sudah terlihat (subtitle YouTube). HANYA
# dipakai untuk kalibrasi (boolean di log), bukan untuk membuang teks:
# kandidat sungguhan boleh bilang "terima kasih".
_KNOWN_HALLUCINATION = re.compile(
    r"^(terima kasih( (kerana|karena|telah|sudah) menonton)?|sampai jumpa)[.!]?$",
    re.IGNORECASE,
)


def segment_stats(body: Mapping[str, Any], threshold: float) -> list[dict[str, Any]]:
    """Statistik per segmen untuk kalibrasi ambang dengan mikrofon sungguhan
    (2026-10-29: "Terima kasih." lolos filter setelah pertanyaan diulang).
    SENGAJA tanpa teks -- yang dicatat hanya angka, panjang teks, dan apakah
    teksnya frasa halusinasi yang dikenal."""
    stats: list[dict[str, Any]] = []
    for seg in body.get("segments") or []:
        text = str(seg.get("text") or "").strip()
        try:
            no_speech = float(seg.get("no_speech_prob", 0.0))
            compression = float(seg.get("compression_ratio", 0.0))
            logprob = float(seg.get("avg_logprob", 0.0))
            duration = float(seg.get("end", 0.0)) - float(seg.get("start", 0.0))
        except (TypeError, ValueError):
            continue
        stats.append(
            {
                "nsp": round(no_speech, 3),
                "cr": round(compression, 2),
                "lp": round(logprob, 2),
                "dur": round(duration, 2),
                "chars": len(text),
                "known": bool(_KNOWN_HALLUCINATION.match(text)),
                "kept": no_speech < threshold and compression <= MAX_COMPRESSION_RATIO,
            }
        )
    return stats
