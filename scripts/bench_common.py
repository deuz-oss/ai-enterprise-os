"""Utilitas bersama skrip benchmark (bench_voice_latency.py, bench_avatar.py).

Murni stdlib supaya bisa dites tanpa GPU/jaringan: persentil, ringkasan per
tahap, evaluasi ambang (exit code), CSV/JSON, pembaca file .env, dan metadata
lingkungan (GPU via nvidia-smi). Tidak ada efek samping saat di-import.
"""

from __future__ import annotations

import csv
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- statistik


def percentile(values: Sequence[float], p: float) -> float | None:
    """Persentil dengan interpolasi linear (sama dengan numpy default).
    None bila tidak ada data."""
    data = sorted(v for v in values if v is not None and not math.isnan(v))
    if not data:
        return None
    if not 0 <= p <= 100:
        raise ValueError("p harus 0..100")
    if len(data) == 1:
        return float(data[0])
    rank = (len(data) - 1) * p / 100
    lo = math.floor(rank)
    hi = math.ceil(rank)
    frac = rank - lo
    return float(data[lo] + (data[hi] - data[lo]) * frac)


def summarize(values: Iterable[float | None]) -> dict[str, float | int | None]:
    """Ringkasan satu metrik: n, min, mean, p50, p95, max (None bila kosong)."""
    data = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not data:
        return {"n": 0, "min": None, "mean": None, "p50": None, "p95": None, "max": None}
    return {
        "n": len(data),
        "min": round(min(data), 1),
        "mean": round(sum(data) / len(data), 1),
        "p50": round(percentile(data, 50) or 0.0, 1),
        "p95": round(percentile(data, 95) or 0.0, 1),
        "max": round(max(data), 1),
    }


# --------------------------------------------------------------------------- ambang


@dataclass
class Check:
    """Satu syarat lulus. `ok=None` = tidak dievaluasi (data tidak ada)."""

    name: str
    actual: float | None
    target: float
    op: str  # "<=" atau ">="
    ok: bool | None
    note: str = ""

    def line(self) -> str:
        status = {True: "LULUS", False: "GAGAL", None: "DILEWATI"}[self.ok]
        actual = "-" if self.actual is None else f"{self.actual:g}"
        extra = f" ({self.note})" if self.note else ""
        return f"[{status}] {self.name}: {actual} {self.op} {self.target:g}{extra}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "actual": self.actual,
            "target": self.target,
            "op": self.op,
            "ok": self.ok,
            "note": self.note,
        }


def check_max(name: str, actual: float | None, target: float, note: str = "") -> Check:
    ok = None if actual is None else actual <= target
    return Check(name, actual, target, "<=", ok, note)


def check_min(name: str, actual: float | None, target: float, note: str = "") -> Check:
    ok = None if actual is None else actual >= target
    return Check(name, actual, target, ">=", ok, note)


def verdict(checks: Sequence[Check], *, skipped_is_failure: Sequence[str] = ()) -> bool:
    """True bila semua syarat lulus. Syarat bernama di `skipped_is_failure`
    yang tidak bisa dievaluasi (data kosong) dihitung GAGAL -- mis. STT yang
    semua gilirannya error tidak boleh dianggap lulus karena p95-nya None."""
    for c in checks:
        if c.ok is False:
            return False
        if c.ok is None and c.name in skipped_is_failure:
            return False
    return True


# --------------------------------------------------------------------------- I/O


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in fields})


def _csv_value(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, float):
        return round(v, 2)
    return v


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_env_file(path: Path, environ: dict[str, str] | None = None) -> dict[str, str]:
    """Baca KEY=VALUE (format .env compose) ke `environ` TANPA menimpa variabel
    yang sudah ada -- env shell/CLI tetap menang. Kembalikan yang dimuat."""
    env = os.environ if environ is None else environ
    loaded: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in env:
            env[key] = value
            loaded[key] = value
    return loaded


def env_or(environ: Mapping[str, str], *names: str, default: str | None = None) -> str | None:
    """Nilai env pertama yang TIDAK kosong (kosong = tidak diset, sama dengan
    `os.environ.get(X) or ...` di agen)."""
    for name in names:
        value = environ.get(name)
        if value:
            return value
    return default


# --------------------------------------------------------------------------- GPU


def parse_nvidia_smi_csv(text: str, fields: Sequence[str]) -> list[dict[str, str]]:
    """Parse keluaran `nvidia-smi --query-gpu=... --format=csv,noheader,nounits`
    (satu baris per GPU)."""
    rows = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(fields):
            continue
        rows.append(dict(zip(fields, parts, strict=True)))
    return rows


def _to_float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "", "[N/A]", "N/A") else None
    except ValueError:
        return None


GPU_INFO_FIELDS = ("index", "name", "driver_version", "memory.total")
GPU_SAMPLE_FIELDS = ("index", "memory.used", "memory.total", "utilization.gpu")


def gpu_info(nvidia_smi: str = "nvidia-smi") -> list[dict[str, str]] | None:
    """Daftar GPU di MESIN YANG MENJALANKAN SKRIP. None bila nvidia-smi tidak
    ada/gagal (= CPU, atau skrip jalan di container tanpa GPU)."""
    exe = shutil.which(nvidia_smi) or (nvidia_smi if Path(nvidia_smi).is_file() else None)
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [
                exe,
                f"--query-gpu={','.join(GPU_INFO_FIELDS)}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_nvidia_smi_csv(out, GPU_INFO_FIELDS) or None


def gpu_label(gpus: list[dict[str, str]] | None) -> str:
    if not gpus:
        return "none/CPU (nvidia-smi tidak ada di mesin ini)"
    return "; ".join(
        f"GPU{g['index']} {g['name']} ({g['memory.total']} MiB, driver {g['driver_version']})"
        for g in gpus
    )


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def base_metadata(label: str | None, nvidia_smi: str = "nvidia-smi") -> dict[str, Any]:
    gpus = gpu_info(nvidia_smi)
    return {
        "label": label or "",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
        "git_commit": git_commit(),
        "bench_host_gpu": gpu_label(gpus),
        "bench_host_gpus": gpus or [],
        "bench_host_has_gpu": bool(gpus),
    }


def fmt_ms(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def stage_table(stages: Mapping[str, Mapping[str, Any]]) -> str:
    """Tabel teks p50/p95/max per tahap untuk ringkasan di konsol."""
    head = f"{'tahap':<26}{'n':>5}{'p50':>9}{'p95':>9}{'max':>9}{'mean':>9}"
    lines = [head, "-" * len(head)]
    for name, s in stages.items():
        lines.append(
            f"{name:<26}{s['n']:>5}{fmt_ms(s['p50']):>9}{fmt_ms(s['p95']):>9}"
            f"{fmt_ms(s['max']):>9}{fmt_ms(s['mean']):>9}"
        )
    return "\n".join(lines)
