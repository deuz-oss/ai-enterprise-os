"""Filter halusinasi Whisper (whisper_filter.py). Angka no_speech_prob di
bawah diambil dari kalibrasi faster-whisper-small 2026-10-29, bukan karangan.
Jalan tanpa LiveKit: `python -m pytest agent/tests`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from whisper_filter import (  # noqa: E402
    DEFAULT_NO_SPEECH_THRESHOLD,
    parse_threshold,
    speech_text,
)


def _body(*segments: tuple[str, float]) -> dict:
    return {
        "text": " ".join(t for t, _ in segments),
        "segments": [{"text": t, "no_speech_prob": p, "avg_logprob": -0.6} for t, p in segments],
    }


def test_silence_and_noise_hallucinations_are_dropped():
    # Hening 0.90, derau putih 0.91/0.92, napas 0.78 -- avg_logprob -0.56..-0.74,
    # jadi aturan bawaan Whisper (logprob < -1.0) tidak menangkapnya.
    for text, prob in [
        ("Terima kasih kerana menonton.", 0.90),
        ("Terima kasih.", 0.91),
        ("Terima kasih kerana menonton.", 0.78),
    ]:
        assert speech_text(_body((text, prob)), DEFAULT_NO_SPEECH_THRESHOLD) == ""


def test_real_speech_kept_including_genuine_thanks():
    # Kandidat yang sungguh bilang "terima kasih" (0.13-0.27) dan jawaban
    # sangat pendek yang pelan ("Sudah" 0.47 = ucapan terburuk) tetap lolos.
    assert speech_text(_body(("Terima kasih.", 0.27)), 0.6) == "Terima kasih."
    assert speech_text(_body(("Sudah", 0.47)), 0.6) == "Sudah"


def test_only_non_speech_segments_dropped_from_mixed_answer():
    body = _body(
        ("Saya pernah menangani pelanggan yang marah.", 0.01),
        ("Terima kasih kerana menonton.", 0.88),
    )
    assert speech_text(body, 0.6) == "Saya pernah menangani pelanggan yang marah."


def test_repetition_loop_dropped_but_natural_repetition_kept():
    # Uji mikrofon 2026-10-29: "saya akan melakukannya" x26 -> cr 14.18.
    # Ucapan sungguhan terpanjang/terulang: cr maks 1.73 ("Ya, ya, ya" 1.39).
    loop = {"text": "saya akan melakukannya", "no_speech_prob": 0.07, "compression_ratio": 14.18}
    natural = {"text": "Ya, ya, betul, betul.", "no_speech_prob": 0.05, "compression_ratio": 1.39}
    assert speech_text({"segments": [loop]}, 0.6) == ""
    assert speech_text({"segments": [natural, loop]}, 0.6) == "Ya, ya, betul, betul."


def test_response_without_segments_is_returned_as_is():
    # Server yang tidak mendukung verbose_json: tidak ada sinyal, jangan buang.
    assert speech_text({"text": " Halo. "}, 0.6) == "Halo."
    assert speech_text({"text": "x", "segments": [{"text": "x"}]}, 0.6) == "x"


def test_threshold_parsing():
    assert parse_threshold(None) == DEFAULT_NO_SPEECH_THRESHOLD
    assert parse_threshold("") == DEFAULT_NO_SPEECH_THRESHOLD
    assert parse_threshold("abc") == DEFAULT_NO_SPEECH_THRESHOLD
    assert parse_threshold("0.7") == 0.7
    assert parse_threshold("5") == 1.0  # >= 1 = filter mati


def test_segment_stats_has_numbers_but_never_text():
    from whisper_filter import segment_stats

    body = {
        "segments": [
            {
                "start": 0.0,
                "end": 1.5,
                "text": " Terima kasih.",
                "no_speech_prob": 0.62,
                "compression_ratio": 0.62,
                "avg_logprob": -0.6,
            },
            {
                "start": 1.5,
                "end": 4.0,
                "text": "Saya menangani keluhan rahasia pribadi.",
                "no_speech_prob": 0.05,
                "compression_ratio": 1.3,
                "avg_logprob": -0.3,
            },
        ]
    }
    stats = segment_stats(body, 0.6)
    assert [(s["known"], s["kept"]) for s in stats] == [(True, False), (False, True)]
    assert stats[0]["dur"] == 1.5 and stats[1]["chars"] == len(
        "Saya menangani keluhan rahasia pribadi."
    )
    assert "rahasia" not in repr(stats) and "Terima" not in repr(stats)


def test_energy_gate_skips_whisper_for_quiet_noise():
    """Derau mikrofon sungguhan (RMS 0.0036-0.0098) tidak dikirim ke Whisper;
    ucapan (RMS ~0.05) dikirim. Server sengaja di port tertutup: panggilan
    yang benar-benar terjadi = error koneksi."""
    import asyncio

    import numpy as np
    import pytest
    from livekit import rtc
    from livekit.agents import APIConnectionError, APIConnectOptions
    from whisper_filter import DEFAULT_MIN_RMS, parse_min_rms
    from whisper_stt import WhisperSTT

    stt = WhisperSTT(
        base_url="http://127.0.0.1:9/v1",
        model="m",
        language="id",
        no_speech_threshold=0.6,
        min_rms=DEFAULT_MIN_RMS,
    )
    opts = APIConnectOptions(max_retry=0, timeout=2)

    def frame(rms: float) -> rtc.AudioFrame:
        x = (np.random.default_rng(0).normal(0, rms, 16000) * 32768).astype(np.int16)
        return rtc.AudioFrame(x.tobytes(), 16000, 1, len(x))

    quiet = asyncio.run(stt.recognize([frame(0.0098)], conn_options=opts))
    assert quiet.alternatives[0].text == ""
    with pytest.raises(APIConnectionError):
        asyncio.run(stt.recognize([frame(0.047)], conn_options=opts))
    assert parse_min_rms(None) == DEFAULT_MIN_RMS and parse_min_rms("0") == 0.0
    assert parse_min_rms("x") == DEFAULT_MIN_RMS
