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
