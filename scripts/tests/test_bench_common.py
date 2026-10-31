import csv

import pytest
from bench_common import (
    check_max,
    check_min,
    env_or,
    gpu_label,
    load_env_file,
    parse_nvidia_smi_csv,
    percentile,
    summarize,
    verdict,
    write_csv,
)


def test_percentile_matches_linear_interpolation():
    data = [10, 20, 30, 40, 50]
    assert percentile(data, 50) == 30
    assert percentile(data, 95) == pytest.approx(48.0)  # numpy.percentile linear
    assert percentile(data, 0) == 10
    assert percentile(data, 100) == 50
    assert percentile([7], 95) == 7
    assert percentile([], 50) is None
    assert percentile([None, 3.0, float("nan")], 50) == 3.0  # type: ignore[list-item]


def test_summarize_ignores_none_and_reports_empty():
    s = summarize([100, None, 300, 200])
    assert s["n"] == 3 and s["p50"] == 200 and s["max"] == 300 and s["mean"] == 200
    assert summarize([None])["p95"] is None


def test_checks_and_verdict():
    over = check_max("stt_ms p95", 620, 500)
    under = check_min("fps", 26, 25)
    missing = check_max("stt_ms p95", None, 500)
    assert over.ok is False and under.ok is True and missing.ok is None
    assert "GAGAL" in over.line() and "DILEWATI" in missing.line()
    assert verdict([under]) is True
    assert verdict([under, over]) is False
    assert verdict([under, missing]) is True
    # Semua giliran STT error -> p95 None: tidak boleh dianggap lulus.
    assert verdict([under, missing], skipped_is_failure=["stt_ms p95"]) is False


def test_load_env_file_does_not_override(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "# komentar\nSTT_MODEL=Systran/faster-whisper-large-v3\nAI_API_KEY='rahasia'\n"
        'export AI_BASE_URL="https://x/v1"\nKOSONG=\n',
        encoding="utf-8",
    )
    env = {"STT_MODEL": "dari-shell"}
    loaded = load_env_file(f, env)
    assert env["STT_MODEL"] == "dari-shell"  # shell menang
    assert env["AI_API_KEY"] == "rahasia" and env["AI_BASE_URL"] == "https://x/v1"
    assert "STT_MODEL" not in loaded
    # Kosong = tidak diset, seperti `os.environ.get(X) or default` di agen.
    assert env_or(env, "KOSONG", "AI_BASE_URL") == "https://x/v1"
    assert env_or(env, "TIDAK_ADA", default="d") == "d"


def test_parse_nvidia_smi_csv():
    out = "0, 10240, 24564, 87\n1, 512, 24564, [N/A]\nrusak\n"
    rows = parse_nvidia_smi_csv(out, ("index", "memory.used", "memory.total", "utilization.gpu"))
    assert len(rows) == 2
    assert rows[0]["memory.used"] == "10240" and rows[1]["utilization.gpu"] == "[N/A]"
    assert gpu_label(None).startswith("none/CPU")
    label = gpu_label(
        [{"index": "0", "name": "RTX 4090", "memory.total": "24564", "driver_version": "570"}]
    )
    assert "RTX 4090" in label


def test_write_csv_blank_for_none(tmp_path):
    p = tmp_path / "a" / "x.csv"
    write_csv(p, [{"a": 1.23456, "b": None, "c": "skip"}], ["a", "b"])
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert rows == [{"a": "1.23", "b": ""}]
