"""Benchmark flashhead-server (PRD Fase 67, avatar video) langsung lewat WebSocket.

Melewati LiveKit/avatar-worker: skrip ini berbicara protokol `/stream` milik
`flashhead-server/server.py` (klien produksinya `avatar-worker/renderers.py`
FlashHeadRenderer -- TIDAK di-import karena ikut membawa PIL/StaticRenderer
dan menyembunyikan waktu per chunk; diimplementasi ulang minimal di sini):

  -> {"type":"start","image":<base64>,"seed":int}
  <- {"type":"ready","slice_frames":n,"fps":25,"sample_rate":16000,...}
     atau {"type":"error","code":"busy"|"bad_image",...}
  -> biner PCM int16 mono 16 kHz, tepat slice_frames*640 sampel (1 chunk)
  <- slice_frames buah JPEG, lalu {"type":"chunk_done","seconds":<waktu inferensi>}

Server memproses chunk satu per satu per koneksi, dan panggilan GPU semua sesi
diserialkan satu kunci. Skrip mengirim audio bicara dengan pola bicara/diam
(AI bicara -> kandidat menjawab), dipacu real-time (`--pacing realtime`: chunk
dikirim begitu audionya "selesai diucapkan", 1 chunk = slice_frames/fps dtk),
lalu mengukur:

- ready_ms: koneksi -> "ready" (get_base_data; varian lite: torch.compile).
- first_frame_ms: chunk PERTAMA tiap ucapan dikirim -> JPEG pertama diterima.
  Ini tambahan jeda suara AI: AvatarRunner menahan audio sampai frame siap.
  utt_first_frame_ms = awal ucapan -> frame pertama (termasuk menunggu satu
  chunk audio penuh terkumpul, ~1,12 dtk di mode realtime).
- service_fps per chunk = frame / (selesai - max(dikirim, chunk sebelumnya
  selesai)): laju render saat server sibuk untuk sesi ini. overall_fps =
  total frame / total waktu layanan. Real-time butuh >= fps target (25).
- lag_ms = chunk dikirim -> chunk_done; bertambah terus = tertinggal.
- in-flight (backlog): chunk terkirim yang belum selesai, dibandingkan dengan
  FLASHHEAD_MAX_BACKLOG avatar-worker (default 3): worker TURUN ke
  StaticRenderer bila mengirim chunk saat in-flight sudah >= batas itu.
- VRAM/utilisasi: `nvidia-smi` di MESIN YANG MENJALANKAN SKRIP (jalankan di
  host GPU), puncak + pertumbuhan (baseline setelah warmup vs akhir) untuk
  deteksi kebocoran.
- error/putus/busy, dan `GET /health` sebelum-sesudah (slot harus kembali).

Default --max-first-frame-ms 1000: satu chunk = 28 frame = 1120 ms audio
(varian pro/Wan). Server baru mengirim frame setelah SELURUH chunk
diinferensi, jadi first_frame ~ waktu inferensi satu chunk; di atas 1120 ms
GPU pasti tidak real-time, dan 1000 ms menyisakan ~10% ruang serta membatasi
tambahan jeda suara AI di bawah 1 dtk (di atas itu jeda giliran bicara terasa
janggal, di atas jeda endpointing ~2 dtk yang sudah ada).

TIDAK diukur: kualitas lip-sync (lihat frame contoh <out>.frame.jpg dan uji
manual), audio Indonesia sungguhan bila --audio-file tidak diberikan (default
sinyal mirip ucapan sintetis -- beban GPU sama, isi tidak), transport LiveKit,
dan decode JPEG di worker.

Dependensi: Python 3.10+, `pip install aiohttp numpy`.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import random
import statistics
import struct
import sys
import time
import wave
import zlib
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_common import (  # noqa: E402
    GPU_SAMPLE_FIELDS,
    REPO_ROOT,
    Check,
    _to_float,
    base_metadata,
    check_max,
    check_min,
    parse_nvidia_smi_csv,
    percentile,
    summarize,
    verdict,
    write_csv,
    write_json,
)

SAMPLE_RATE = 16000
SAMPLES_PER_FRAME = 640  # 16 kHz / 25 fps (server: slice_frames*640 sampel)
DEFAULT_SLICE_FRAMES = 28  # 33 - 5 (Wan VAE), dari README; server mengirim nilai aslinya

INTERVAL_FIELDS = [
    "t_start",
    "t_end",
    "session",
    "chunks_sent",
    "chunks_done",
    "frames",
    "fps_wall",
    "fps_demand",
    "service_fps_mean",
    "lag_ms_max",
    "inflight_max",
    "vram_used_mb_max",
    "gpu_util_pct_mean",
]
CHUNK_FIELDS = [
    "session",
    "utterance",
    "chunk",
    "warmup",
    "sent_t",
    "first_frame_t",
    "done_t",
    "frames",
    "first_frame_ms",
    "lag_ms",
    "service_ms",
    "service_fps",
    "server_infer_ms",
    "inflight_at_send",
]
GPU_FIELDS = ["t", "gpu_index", "memory_used_mb", "memory_total_mb", "utilization_pct"]


# --------------------------------------------------------------------------- logika murni


def parse_range(text: str) -> tuple[float, float]:
    """'3:12' -> (3.0, 12.0); '5' -> (5.0, 5.0)."""
    parts = text.split(":")
    lo = float(parts[0])
    hi = float(parts[1]) if len(parts) > 1 else lo
    if lo < 0 or hi < lo:
        raise argparse.ArgumentTypeError(f"rentang tidak valid: {text!r}")
    return lo, hi


def make_schedule(
    duration: float,
    talk: tuple[float, float],
    silence: tuple[float, float],
    rng: random.Random,
) -> list[tuple[float, float]]:
    """Daftar (mulai, durasi) ucapan AI dalam [0, duration). Mulai dengan bicara;
    ucapan terakhir dipotong di batas durasi."""
    out: list[tuple[float, float]] = []
    t = 0.0
    while t < duration:
        dur = min(rng.uniform(*talk), duration - t)
        if dur <= 0:
            break
        out.append((round(t, 3), round(dur, 3)))
        t += dur + rng.uniform(*silence)
    return out


def chunk_count(dur_sec: float, slice_samples: int) -> int:
    """Jumlah chunk untuk satu ucapan; sisa terakhir dipad hening (seperti
    AudioFifo.take saat akhir segmen)."""
    return max(1, math.ceil(round(dur_sec * SAMPLE_RATE) / slice_samples))


def chunk_send_offsets(n: int, slice_sec: float, pacing: str) -> list[float]:
    """Kapan chunk ke-k dikirim relatif awal ucapan. realtime: saat audionya
    lengkap ((k+1)*slice); burst: semua di awal (TTS lebih cepat dari real-time)."""
    if pacing == "burst":
        return [0.0] * n
    return [(k + 1) * slice_sec for k in range(n)]


def synth_speech(n: int, rng: random.Random) -> list[int]:
    """Sinyal mirip ucapan (harmonik f0 bervariasi + amplop suku kata ~4 Hz +
    derau), int16. Bukan bahasa sungguhan; beban inferensi sama."""
    out = []
    f0 = 140.0
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        if i % 1600 == 0:
            f0 = min(220.0, max(100.0, f0 + rng.uniform(-15, 15)))
        phase += 2 * math.pi * f0 / SAMPLE_RATE
        env = 0.5 + 0.5 * math.sin(2 * math.pi * 4.0 * t) ** 2
        s = sum(math.sin(h * phase) / h for h in (1, 2, 3, 4))
        out.append(int(max(-1.0, min(1.0, 0.25 * env * s + rng.gauss(0, 0.01))) * 32767))
    return out


def chunk_metrics(chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Lengkapi metrik turunan per chunk (urut per sesi): lag, first frame,
    service time (antre di belakang chunk sebelumnya tidak dihitung)."""
    out = []
    prev_done: dict[Any, float] = {}
    for c in sorted(chunks, key=lambda c: (c["session"], c["sent_t"])):
        row = dict(c)
        sent, done, ff = c.get("sent_t"), c.get("done_t"), c.get("first_frame_t")
        if ff is not None:
            row["first_frame_ms"] = (ff - sent) * 1000
        if done is not None:
            start = max(sent, prev_done.get(c["session"], sent))
            row["lag_ms"] = (done - sent) * 1000
            row["service_ms"] = (done - start) * 1000
            if row["service_ms"] > 0 and c.get("frames"):
                row["service_fps"] = c["frames"] / (done - start)
            prev_done[c["session"]] = done
        out.append(row)
    return out


def overall_fps(chunks: Sequence[Mapping[str, Any]]) -> float | None:
    """Total frame / total waktu layanan (hanya chunk selesai)."""
    frames = sum(c.get("frames") or 0 for c in chunks if c.get("service_ms"))
    secs = sum(c["service_ms"] for c in chunks if c.get("service_ms")) / 1000
    return frames / secs if secs > 0 else None


def vram_growth(
    samples: Sequence[Mapping[str, Any]], t_from: float, window: float
) -> dict[str, float | None]:
    """Pertumbuhan VRAM: median `window` dtk pertama setelah t_from (baseline,
    setelah warmup) vs median `window` dtk terakhir. Bila run terlalu pendek,
    jendela menyusut ke sepertiga rentang."""
    pts = [
        (s["t"], s["memory_used_mb"])
        for s in samples
        if s.get("memory_used_mb") is not None and s["t"] >= t_from
    ]
    allv = [s["memory_used_mb"] for s in samples if s.get("memory_used_mb") is not None]
    peak = max(allv) if allv else None
    if len(pts) < 2:
        return {"baseline_mb": None, "end_mb": None, "growth_mb": None, "peak_mb": peak}
    t0, t1 = pts[0][0], pts[-1][0]
    w = min(window, (t1 - t0) / 3) if t1 > t0 else 0
    base = [v for t, v in pts if t <= t0 + w] or [pts[0][1]]
    end = [v for t, v in pts if t >= t1 - w] or [pts[-1][1]]
    b, e = statistics.median(base), statistics.median(end)
    return {"baseline_mb": b, "end_mb": e, "growth_mb": e - b, "peak_mb": peak}


def interval_rows(
    chunks: Sequence[Mapping[str, Any]],
    frame_times: Mapping[Any, Sequence[float]],
    gpu: Sequence[Mapping[str, Any]],
    sessions: Sequence[Any],
    fps: float,
    slice_sec: float,
    interval: float,
    t_end: float,
) -> list[dict[str, Any]]:
    """Deret waktu per interval, per sesi + gabungan ("all")."""
    rows = []
    n = max(1, math.ceil(t_end / interval))
    for i in range(n):
        a, b = i * interval, min((i + 1) * interval, t_end)
        span = b - a
        if span <= 0:
            continue
        gpu_in = [g for g in gpu if a <= g["t"] < b]
        vram = [g["memory_used_mb"] for g in gpu_in if g.get("memory_used_mb") is not None]
        util = [g["utilization_pct"] for g in gpu_in if g.get("utilization_pct") is not None]
        for sid in [*sessions, "all"]:
            cs = [c for c in chunks if sid == "all" or c["session"] == sid]
            sent = [c for c in cs if a <= c["sent_t"] < b]
            done = [c for c in cs if c.get("done_t") is not None and a <= c["done_t"] < b]
            ftimes = (
                [t for s in sessions for t in frame_times.get(s, ())]
                if sid == "all"
                else frame_times.get(sid, ())
            )
            frames = sum(1 for t in ftimes if a <= t < b)
            sfps = [c["service_fps"] for c in done if c.get("service_fps")]
            lags = [c["lag_ms"] for c in done if c.get("lag_ms") is not None]
            infl = [c["inflight_at_send"] for c in sent]
            rows.append(
                {
                    "t_start": a,
                    "t_end": b,
                    "session": sid,
                    "chunks_sent": len(sent),
                    "chunks_done": len(done),
                    "frames": frames,
                    "fps_wall": frames / span,
                    "fps_demand": len(sent) * slice_sec * fps / span,
                    "service_fps_mean": sum(sfps) / len(sfps) if sfps else None,
                    "lag_ms_max": max(lags) if lags else None,
                    "inflight_max": max(infl) if infl else None,
                    "vram_used_mb_max": max(vram) if vram else None,
                    "gpu_util_pct_mean": sum(util) / len(util) if util else None,
                }
            )
    return rows


def health_url(ws_url: str) -> str:
    parts = urlsplit(ws_url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    path = parts.path.rsplit("/", 1)[0] + "/health"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def resolve_out(out: Path) -> dict[str, Path]:
    if out.suffix.lower() == ".csv":
        stem = out.with_suffix("")
        return {
            "intervals": out,
            "chunks": stem.with_name(stem.name + ".chunks.csv"),
            "gpu": stem.with_name(stem.name + ".gpu.csv"),
            "summary": stem.with_name(stem.name + ".summary.json"),
            "frame": stem.with_name(stem.name + ".frame.jpg"),
        }
    return {
        "intervals": out / "avatar_intervals.csv",
        "chunks": out / "avatar_chunks.csv",
        "gpu": out / "avatar_gpu.csv",
        "summary": out / "avatar_summary.json",
        "frame": out / "avatar_frame.jpg",
    }


def placeholder_png(size: int = 512) -> bytes:
    """PNG abu-abu dengan oval terang (tanpa PIL). Hanya untuk dry-run: model
    sungguhan butuh foto wajah (--image)."""
    rows = []
    c, rx, ry = size / 2, size * 0.28, size * 0.36
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            inside = ((x - c) / rx) ** 2 + ((y - c * 0.95) / ry) ** 2 <= 1
            row += bytes([224, 186, 160] if inside else [90, 100, 110])
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
        + chunk(b"IEND", b"")
    )


def resolve_image(arg: Path | None, environ: Mapping[str, str]) -> tuple[bytes, str]:
    candidates: list[Path] = []
    if arg:
        if not arg.is_file():
            raise SystemExit(f"--image tidak ditemukan: {arg}")
        candidates.append(arg)
    env_img = environ.get("AVATAR_REFERENCE_IMAGE")
    if env_img:
        candidates.append(Path(env_img))
        candidates.append(REPO_ROOT / "deploy" / "avatar" / Path(env_img).name)
    deploy = REPO_ROOT / "deploy" / "avatar"
    if deploy.is_dir():
        candidates += sorted(p for p in deploy.iterdir() if p.suffix.lower() in (".jpg", ".png"))
    for p in candidates:
        if p.is_file():
            return p.read_bytes(), str(p)
    return placeholder_png(), "placeholder sintetis (BUKAN foto wajah -- pakai --image)"


def load_audio(path: Path) -> list[int]:
    """WAV PCM 16-bit -> mono 16 kHz (resample linear)."""
    import numpy as np

    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            raise SystemExit("--audio-file harus WAV PCM 16-bit")
        ch, sr = w.getnchannels(), w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    if sr != SAMPLE_RATE:
        n = int(len(pcm) * SAMPLE_RATE / sr)
        pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm)
    return np.asarray(pcm, dtype=np.int16).tolist()


def evaluate(summary: Mapping[str, Any], args: argparse.Namespace) -> list[Check]:
    ff = summary["first_frame_ms"]["p95"]
    checks = [
        check_min(
            "overall_fps (sesi terburuk)",
            summary["overall_fps_min"],
            args.min_fps,
            "frame / waktu layanan",
        ),
        check_max("first_frame_ms p95", ff, args.max_first_frame_ms, "chunk pertama ucapan"),
        check_max(
            "inflight maks",
            summary["inflight_max"],
            args.max_backlog,
            "avatar-worker turun ke StaticRenderer di atas FLASHHEAD_MAX_BACKLOG",
        ),
        check_max("error/putus", summary["errors"], 0),
        Check(
            "sesi busy",
            summary["busy"],
            args.expect_busy,
            "==",
            summary["busy"] == args.expect_busy,
            "jumlah sesi yang ditolak server harus sama dengan --expect-busy",
        ),
    ]
    vg = summary["vram"]["growth_mb"]
    checks.append(
        check_max(
            "vram_growth_mb",
            vg,
            args.max_vram_growth_mb,
            "nvidia-smi tidak ada / data kurang" if vg is None else "baseline pascawarmup vs akhir",
        )
    )
    slots = summary.get("health_free_slots_before"), summary.get("health_free_slots_after")
    if None not in slots:
        checks.append(
            Check(
                "slot kembali (/health free_slots)",
                slots[1],
                slots[0],
                "==",
                slots[0] == slots[1],
            )
        )
    return checks


# --------------------------------------------------------------------------- sesi


@dataclass
class SessionResult:
    sid: int
    status: str = "pending"  # ok | busy | error
    ready_ms: float | None = None
    server_info: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    frame_times: list[float] = field(default_factory=list)
    utterances: list[dict[str, Any]] = field(default_factory=list)
    bad_frames: int = 0
    first_jpeg: bytes | None = None


class Session:
    def __init__(
        self,
        sid: int,
        args: argparse.Namespace,
        image_b64: str,
        audio: list[int],
        t0: float,
    ) -> None:
        self.sid = sid
        self.args = args
        self.image_b64 = image_b64
        self.audio = audio
        self.audio_pos = (sid * 7919 * SAMPLES_PER_FRAME) % max(1, len(audio))
        self.t0 = t0
        self.res = SessionResult(sid)
        self.pending: deque[dict[str, Any]] = deque()
        self.ws: Any = None
        self.closing = False

    def now(self) -> float:
        return time.monotonic() - self.t0

    def next_audio(self, n_real: int, n_total: int) -> bytes:
        out = []
        for _ in range(n_real):
            out.append(self.audio[self.audio_pos])
            self.audio_pos = (self.audio_pos + 1) % len(self.audio)
        out += [0] * (n_total - n_real)
        return struct.pack(f"<{n_total}h", *out)

    async def run(self, http: Any) -> SessionResult:
        import aiohttp

        a = self.args
        await asyncio.sleep(self.sid * a.stagger_sec)
        t_conn = self.now()
        try:
            self.ws = await http.ws_connect(a.url, heartbeat=20, max_msg_size=0)
            await self.ws.send_json(
                {"type": "start", "image": self.image_b64, "seed": a.seed + self.sid}
            )
            msg = await asyncio.wait_for(self.ws.receive(), a.ready_timeout)
            data = json.loads(msg.data) if msg.type == aiohttp.WSMsgType.TEXT else {}
        except (aiohttp.ClientError, TimeoutError, ValueError, OSError) as exc:
            self.res.status = "error"
            self.res.errors.append(f"connect/ready: {type(exc).__name__}: {exc}")
            await self._close()
            return self.res
        if data.get("type") != "ready":
            code = data.get("code") or "unknown"
            self.res.status = "busy" if code == "busy" else "error"
            if code != "busy":
                self.res.errors.append(f"ditolak: {data or msg.type}")
            await self._close()
            return self.res
        self.res.ready_ms = (self.now() - t_conn) * 1000
        self.res.server_info = data
        self.res.status = "ok"
        reader = asyncio.create_task(self._read_loop())
        try:
            await self._send_loop(data)
            await self._drain()
        finally:
            self.closing = True
            await self._close()
            reader.cancel()
            try:
                await reader
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self.res.errors:
            self.res.status = "error"
        return self.res

    async def _send_loop(self, ready: Mapping[str, Any]) -> None:
        a = self.args
        slice_frames = int(ready.get("slice_frames") or DEFAULT_SLICE_FRAMES)
        slice_samples = slice_frames * SAMPLES_PER_FRAME
        slice_sec = slice_samples / SAMPLE_RATE
        rng = random.Random(a.seed * 1000 + self.sid)
        schedule = make_schedule(a.duration_sec, a.talk_sec, a.silence_sec, rng)
        base = self.now()
        for u, (start, dur) in enumerate(schedule):
            n = chunk_count(dur, slice_samples)
            real_total = round(dur * SAMPLE_RATE)
            offsets = chunk_send_offsets(n, slice_sec, a.pacing)
            utt = {
                "session": self.sid,
                "utterance": u,
                "start_t": base + start,
                "duration_sec": dur,
                "chunks": n,
                "warmup": u < a.warmup_utterances,
            }
            self.res.utterances.append(utt)
            for k, off in enumerate(offsets):
                due = base + start + off
                while (wait := due - self.now()) > 0:
                    if self._stalled() or self.res.errors:
                        return
                    await asyncio.sleep(min(wait, 0.25))
                if self._stalled() or self.res.errors:
                    return
                n_real = max(0, min(slice_samples, real_total - k * slice_samples))
                rec = {
                    "session": self.sid,
                    "utterance": u,
                    "chunk": k,
                    "warmup": utt["warmup"],
                    "sent_t": self.now(),
                    "first_frame_t": None,
                    "done_t": None,
                    "frames": 0,
                    "server_infer_ms": None,
                    "inflight_at_send": len(self.pending) + 1,
                }
                self.pending.append(rec)
                self.res.chunks.append(rec)
                try:
                    await self.ws.send_bytes(self.next_audio(n_real, slice_samples))
                except Exception as exc:  # noqa: BLE001
                    self.res.errors.append(f"kirim: {type(exc).__name__}: {exc}")
                    return

    def _stalled(self) -> bool:
        if self.pending and self.now() - self.pending[0]["sent_t"] > self.args.chunk_timeout:
            self.res.errors.append(
                f"stall: chunk tanpa balasan > {self.args.chunk_timeout:.0f} dtk"
            )
            return True
        return False

    async def _drain(self) -> None:
        while self.pending and not self.res.errors and not self.ws.closed:
            if self._stalled():
                return
            await asyncio.sleep(0.05)

    async def _read_loop(self) -> None:
        import aiohttp

        try:
            async for msg in self.ws:
                t = self.now()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    if not self.pending:
                        self.res.errors.append("frame tanpa chunk yang ditunggu")
                        continue
                    rec = self.pending[0]
                    if rec["first_frame_t"] is None:
                        rec["first_frame_t"] = t
                    rec["frames"] += 1
                    self.res.frame_times.append(t)
                    if not msg.data.startswith(b"\xff\xd8"):
                        self.res.bad_frames += 1
                    elif self.res.first_jpeg is None:
                        self.res.first_jpeg = bytes(msg.data)
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "chunk_done":
                        if not self.pending:
                            self.res.errors.append("chunk_done tanpa chunk yang ditunggu")
                            continue
                        rec = self.pending.popleft()
                        rec["done_t"] = t
                        if data.get("seconds") is not None:
                            rec["server_infer_ms"] = float(data["seconds"]) * 1000
                        expected = int(self.res.server_info.get("slice_frames") or 0)
                        if expected and rec["frames"] != expected:
                            self.res.errors.append(
                                f"chunk {rec['utterance']}/{rec['chunk']}: {rec['frames']} frame,"
                                f" harusnya {expected}"
                            )
                    elif data.get("type") == "error":
                        self.res.errors.append(f"server error: {data}")
                        return
                else:
                    break
        except Exception as exc:  # noqa: BLE001
            if not self.closing:
                self.res.errors.append(f"baca: {type(exc).__name__}: {exc}")
            return
        if not self.closing:
            self.res.errors.append("koneksi ditutup server")

    async def _close(self) -> None:
        if self.ws is not None and not self.ws.closed:
            try:
                await self.ws.close()
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------- GPU & health


async def poll_gpu(
    args: argparse.Namespace, t0: float, out: list[dict[str, Any]], stop: asyncio.Event
) -> None:
    exe = args.nvidia_smi
    while not stop.is_set():
        try:
            proc = await asyncio.create_subprocess_exec(
                exe,
                f"--query-gpu={','.join(GPU_SAMPLE_FIELDS)}",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), 10)
        except (OSError, TimeoutError):
            return  # nvidia-smi tidak ada: VRAM tidak diukur
        t = time.monotonic() - t0
        for row in parse_nvidia_smi_csv(stdout.decode(errors="replace"), GPU_SAMPLE_FIELDS):
            if args.gpu_index is not None and row["index"] != str(args.gpu_index):
                continue
            out.append(
                {
                    "t": t,
                    "gpu_index": row["index"],
                    "memory_used_mb": _to_float(row["memory.used"]),
                    "memory_total_mb": _to_float(row["memory.total"]),
                    "utilization_pct": _to_float(row["utilization.gpu"]),
                }
            )
        try:
            await asyncio.wait_for(stop.wait(), args.gpu_poll_sec)
        except TimeoutError:
            pass


async def get_health(http: Any, url: str) -> dict[str, Any] | None:
    try:
        async with http.get(url, timeout=10) as resp:
            return await resp.json() if resp.status == 200 else None
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- ringkasan


def build_summary(
    results: Sequence[SessionResult],
    gpu: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
    health_before: Mapping[str, Any] | None,
    health_after: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = [c for r in results for c in r.chunks]
    chunks = chunk_metrics(raw)
    measured = [c for c in chunks if not c["warmup"]]
    firsts = [c["first_frame_ms"] for c in measured if c["chunk"] == 0 and c.get("first_frame_ms")]
    utt_ff = []
    for r in results:
        by_utt = {(c["utterance"]): c for c in chunks if c["session"] == r.sid and c["chunk"] == 0}
        for u in r.utterances:
            c = by_utt.get(u["utterance"])
            if not u["warmup"] and c and c.get("first_frame_t") is not None:
                utt_ff.append((c["first_frame_t"] - u["start_t"]) * 1000)
    per_session = {}
    for r in results:
        cs = [c for c in measured if c["session"] == r.sid]
        per_session[str(r.sid)] = {
            "status": r.status,
            "ready_ms": r.ready_ms,
            "errors": r.errors,
            "chunks": len(cs),
            "frames": sum(c["frames"] for c in cs),
            "overall_fps": overall_fps(cs),
            "service_fps": summarize(c.get("service_fps") for c in cs),
            "bad_frames": r.bad_frames,
        }
    ok = [s for s in per_session.values() if s["status"] != "busy" and s["chunks"]]
    fps_vals = [s["overall_fps"] for s in ok if s["overall_fps"] is not None]
    # Baseline VRAM: setelah ucapan warmup terakhir semua sesi selesai.
    warm_end = max(
        (c["done_t"] for c in chunks if c["warmup"] and c.get("done_t") is not None),
        default=0.0,
    )
    sfps = [c.get("service_fps") for c in measured if c.get("service_fps")]
    lags = [c["lag_ms"] for c in measured if c.get("lag_ms") is not None]
    summary = {
        "sessions_requested": len(results),
        "sessions_ok": sum(1 for r in results if r.status == "ok"),
        "busy": sum(1 for r in results if r.status == "busy"),
        "errors": sum(len(r.errors) for r in results),
        "error_messages": [f"sesi {r.sid}: {e}" for r in results for e in r.errors][:50],
        "ready_ms": summarize(r.ready_ms for r in results),
        "first_frame_ms": summarize(firsts),
        "utt_first_frame_ms": summarize(utt_ff),
        "chunk_first_frame_ms": summarize(c.get("first_frame_ms") for c in measured),
        "server_infer_ms": summarize(c.get("server_infer_ms") for c in measured),
        "lag_ms": summarize(lags),
        "service_fps": summarize(sfps),
        "service_fps_p05": percentile(sfps, 5),
        "overall_fps_min": min(fps_vals) if fps_vals else None,
        "inflight_max": max((c["inflight_at_send"] for c in measured), default=None),
        "frames_total": sum(c["frames"] for c in chunks),
        "bad_frames": sum(r.bad_frames for r in results),
        "vram": vram_growth(gpu, warm_end, args.vram_window_sec),
        "gpu_util_pct": summarize(g.get("utilization_pct") for g in gpu),
        "gpu_samples": len(gpu),
        "health_before": health_before,
        "health_after": health_after,
        "health_free_slots_before": (health_before or {}).get("free_slots"),
        "health_free_slots_after": (health_after or {}).get("free_slots"),
        "per_session": per_session,
    }
    return summary, chunks


def print_summary(summary: Mapping[str, Any], checks: Sequence[Check], meta: Mapping) -> None:
    def ms(s: Mapping[str, Any]) -> str:
        return f"p50 {s['p50']} / p95 {s['p95']} / maks {s['max']} (n={s['n']})"

    print()
    print(f"GPU mesin bench : {meta['bench_host_gpu']}")
    print(f"server          : {meta.get('server_ready')}")
    print(
        f"sesi            : {summary['sessions_ok']} ok, {summary['busy']} busy, "
        f"{summary['errors']} error (diminta {summary['sessions_requested']})"
    )
    print(f"ready_ms        : {ms(summary['ready_ms'])}")
    print(f"first_frame_ms  : {ms(summary['first_frame_ms'])}  [chunk pertama ucapan]")
    print(f"utt_first_frame : {ms(summary['utt_first_frame_ms'])}  [awal ucapan -> frame]")
    print(f"server_infer_ms : {ms(summary['server_infer_ms'])}")
    print(f"lag_ms          : {ms(summary['lag_ms'])}")
    print(
        f"service_fps     : {ms(summary['service_fps'])}, p05 "
        f"{_r(summary['service_fps_p05'])}; overall_fps sesi terburuk "
        f"{_r(summary['overall_fps_min'])}"
    )
    print(f"inflight maks   : {summary['inflight_max']}")
    v = summary["vram"]
    print(
        f"VRAM (MiB)      : puncak {v['peak_mb']}, baseline {v['baseline_mb']}, akhir "
        f"{v['end_mb']}, tumbuh {v['growth_mb']} ({summary['gpu_samples']} sampel)"
    )
    for sid, s in summary["per_session"].items():
        print(
            f"  sesi {sid}: {s['status']}, ready {_r(s['ready_ms'])} ms, {s['chunks']} chunk, "
            f"overall_fps {_r(s['overall_fps'])}"
            + (f", error: {s['errors'][0]}" if s["errors"] else "")
        )
    for c in checks:
        print(c.line())


def _r(v: float | None) -> str:
    return "-" if v is None else f"{v:.1f}"


# --------------------------------------------------------------------------- utama


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Benchmark flashhead-server lewat WebSocket /stream (lihat docstring skrip).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    a = p.add_argument
    a("--url", required=True, help="ws://HOST:8010/stream")
    a("--duration-sec", type=float, default=600.0, help="durasi pola bicara per sesi")
    a("--sessions", type=int, default=1, help="sesi paralel (uji FLASHHEAD_MAX_SESSIONS)")
    a("--out", type=Path, required=True, help="file .csv (+ .chunks.csv/.gpu.csv/.summary.json)")
    a(
        "--image",
        type=Path,
        help="foto referensi (default env AVATAR_REFERENCE_IMAGE/deploy/avatar)",
    )
    a("--audio-file", type=Path, help="WAV ucapan (diputar berulang); default sinyal sintetis")
    a("--talk-sec", type=parse_range, default="3:12", help="rentang durasi ucapan AI (dtk)")
    a("--silence-sec", type=parse_range, default="4:15", help="rentang diam (0:0 = terus bicara)")
    a("--pacing", choices=("realtime", "burst"), default="realtime", help="laju kirim audio")
    a("--warmup-utterances", type=int, default=1, help="ucapan awal tiap sesi yang tidak dihitung")
    a("--stagger-sec", type=float, default=2.0, help="jeda mulai antarsesi")
    a("--seed", type=int, default=9999, help="seed pola & seed server (+id sesi)")
    a("--ready-timeout", type=float, default=600.0, help="batas tunggu 'ready' (lite: compile)")
    a("--chunk-timeout", type=float, default=30.0, help="chunk tanpa balasan > ini = stall/error")
    a("--interval-sec", type=float, default=10.0, help="lebar interval deret waktu CSV")
    a("--gpu-poll-sec", type=float, default=2.0, help="periode polling nvidia-smi")
    a("--gpu-index", type=int, help="hanya GPU indeks ini (default semua)")
    a("--nvidia-smi", default="nvidia-smi", help="path nvidia-smi")
    a("--vram-window-sec", type=float, default=60.0, help="jendela median baseline/akhir VRAM")
    a("--min-fps", type=float, default=25.0, help="GAGAL bila overall_fps sesi terburuk < ini")
    a("--max-first-frame-ms", type=float, default=1000.0, help="GAGAL bila p95 first frame > ini")
    a("--max-vram-growth-mb", type=float, default=300.0, help="GAGAL bila VRAM tumbuh > ini")
    a("--max-backlog", type=int, default=3, help="= FLASHHEAD_MAX_BACKLOG avatar-worker")
    a("--expect-busy", type=int, default=0, help="jumlah sesi yang memang harus ditolak 'busy'")
    a("--label", help="catatan bebas di metadata, mis. 'lite, MAX_SESSIONS=3, RTX 4090'")
    return p


async def run(args: argparse.Namespace) -> int:
    import aiohttp

    paths = resolve_out(args.out)
    image, image_src = resolve_image(args.image, os.environ)
    audio = (
        load_audio(args.audio_file)
        if args.audio_file
        else synth_speech(SAMPLE_RATE * 20, random.Random(args.seed))
    )
    meta = base_metadata(args.label, args.nvidia_smi)
    meta.update(
        {
            "script": "bench_avatar.py",
            "url": args.url,
            "image": image_src,
            "audio": str(args.audio_file) if args.audio_file else "sintetis (mirip ucapan)",
            "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        }
    )
    print(f"GPU mesin bench: {meta['bench_host_gpu']}")
    print(f"Foto referensi : {image_src}")
    if not meta["bench_host_has_gpu"]:
        print("CATATAN: nvidia-smi tidak ada di mesin ini -> VRAM/utilisasi TIDAK diukur.")

    t0 = time.monotonic()
    gpu: list[dict[str, Any]] = []
    stop = asyncio.Event()
    async with aiohttp.ClientSession() as http:
        h_url = health_url(args.url)
        health_before = await get_health(http, h_url)
        print(f"/health sebelum: {health_before}")
        poller = asyncio.create_task(poll_gpu(args, t0, gpu, stop))
        b64 = base64.b64encode(image).decode()
        sessions = [Session(i, args, b64, audio, t0) for i in range(args.sessions)]
        progress = asyncio.create_task(_progress(sessions, t0))
        results = await asyncio.gather(*(s.run(http) for s in sessions))
        progress.cancel()
        stop.set()
        await poller
        await asyncio.sleep(2)  # server melepas slot di `finally` setelah close
        health_after = await get_health(http, h_url)
        print(f"/health sesudah: {health_after}")
    t_end = time.monotonic() - t0

    meta["server_ready"] = next((r.server_info for r in results if r.server_info), None)
    summary, chunks = build_summary(results, gpu, args, health_before, health_after)
    info = meta["server_ready"] or {}
    slice_frames = int(info.get("slice_frames") or DEFAULT_SLICE_FRAMES)
    fps = float(info.get("fps") or 25)
    intervals = interval_rows(
        chunks,
        {r.sid: r.frame_times for r in results},
        gpu,
        [r.sid for r in results],
        fps,
        slice_frames * SAMPLES_PER_FRAME / SAMPLE_RATE,
        args.interval_sec,
        t_end,
    )
    checks = evaluate(summary, args)
    passed = verdict(checks, skipped_is_failure=("overall_fps (sesi terburuk)",))
    write_csv(paths["intervals"], intervals, INTERVAL_FIELDS)
    write_csv(paths["chunks"], chunks, CHUNK_FIELDS)
    write_csv(paths["gpu"], gpu, GPU_FIELDS)
    write_json(
        paths["summary"],
        {
            "metadata": meta,
            "summary": summary,
            "checks": [c.as_dict() for c in checks],
            "passed": passed,
        },
    )
    jpeg = next((r.first_jpeg for r in results if r.first_jpeg), None)
    if jpeg:
        paths["frame"].write_bytes(jpeg)
    print_summary(summary, checks, meta)
    if summary["busy"] and not args.expect_busy:
        print("Petunjuk: sesi 'busy' disengaja (uji N+1)? Ulangi dengan --expect-busy N.")
    print(f"HASIL: {'LULUS' if passed else 'GAGAL'} -> {', '.join(str(p) for p in paths.values())}")
    return 0 if passed else 1


async def _progress(sessions: Sequence[Session], t0: float) -> None:
    while True:
        await asyncio.sleep(30)
        done = sum(1 for s in sessions for c in s.res.chunks if c["done_t"] is not None)
        sent = sum(len(s.res.chunks) for s in sessions)
        print(
            f"  t={time.monotonic() - t0:6.0f}s chunk terkirim {sent}, selesai {done}, "
            f"error {sum(len(s.res.errors) for s in sessions)}",
            flush=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sessions < 1:
        raise SystemExit("--sessions minimal 1")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
