"""Batas sesi suara (session_limits.py). Jalan tanpa LiveKit:
`python -m pytest agent/tests`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from session_limits import (  # noqa: E402
    DEFAULT_MAX_MINUTES,
    TIME_UP_LINE,
    parse_max_minutes,
    retryable_status,
)


def test_upload_not_retried_for_permanent_rejections():
    # Uji 2026-10-29: rekaman sesi 2 jam ditolak 413 tiga kali berturut-turut.
    for status in (400, 401, 403, 404, 413, 422):
        assert retryable_status(status) is False
    for status in (408, 429, 500, 502, 503, 504):
        assert retryable_status(status) is True


def test_max_minutes_default_stays_under_backend_recording_limit():
    # Backend menolak rekaman > 60 MB (~60 menit ogg/opus 2 kanal).
    assert parse_max_minutes(None) == DEFAULT_MAX_MINUTES < 60
    assert parse_max_minutes("") == DEFAULT_MAX_MINUTES
    assert parse_max_minutes("abc") == DEFAULT_MAX_MINUTES
    assert parse_max_minutes("30") == 30.0
    assert parse_max_minutes("0") == 0.0  # 0 = tanpa batas


def test_time_up_line_tells_candidate_answers_are_kept():
    assert "waktu interview sudah habis" in TIME_UP_LINE
    assert "tersimpan" in TIME_UP_LINE
