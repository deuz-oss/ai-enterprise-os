"""Benchmark latensi pipeline suara AI Interview (PRD Fase 30): STT -> LLM -> TTS.

Mengukur per giliran, dengan provider/model/parameter YANG SAMA dengan agen
(`agent/main.py`, `agent/whisper_stt.py`):

- stt_ms        POST WAV ke faster-whisper-server `{STT_BASE_URL}/audio/transcriptions`
                (model STT_MODEL, language STT_LANGUAGE, response_format verbose_json).
- llm_ttft_ms   chat completion streaming ke `{AI_BASE_URL}/chat/completions`
                (AI_AGENT_MODEL -> AI_MODEL), dari request pertama sampai token TEKS
                pertama yang bisa diucapkan. Bila model memanggil tool dulu (agen
                punya tool next_question dkk.), putaran kedua ikut dihitung --
                sama seperti agen yang harus menunggu putaran itu sebelum bicara.
- llm_first_sentence_ms  sampai kalimat pertama lengkap (lihat total_sentence_ms).
- llm_total_ms  sampai stream LLM selesai.
- tts_ttfb_ms / tts_total_ms  `{AI_BASE_URL}/audio/speech` (AI_TTS_MODEL, AI_TTS_VOICE,
                instructions & response_format mp3 & stream_format sse seperti plugin
                livekit-plugins-openai), sampai byte audio pertama / selesai. Input =
                kalimat pertama balasan LLM.

DEFINISI total_ms = stt_ms + llm_ttft_ms + tts_ttfb_ms: latensi pipeline sampai
byte audio pertama. TIDAK termasuk: jeda VAD/endpointing/turn detector (agen
menunggu VAD_MIN_SILENCE 1,2 dtk + ENDPOINTING_MIN_DELAY 1,0 dtk setelah
kandidat diam -- itu disengaja dan TIDAK diukur di sini), transport
WebRTC/jaringan ke browser, decode audio di klien, dan antrean avatar.

total_sentence_ms = stt_ms + llm_first_sentence_ms + tts_ttfb_ms lebih dekat ke
perilaku agen sebenarnya: TTS OpenAI di plugin LiveKit non-streaming, jadi
AgentSession baru mensintesis setelah KALIMAT pertama selesai, bukan token
pertama. Keduanya dilaporkan; ambang lulus default hanya untuk STT.

Konteks LLM hanya satu giliran (system prompt agen + pertanyaan + jawaban),
bukan riwayat interview yang memanjang. Byte mp3 pertama belum tentu bisa
langsung diputar (decoder butuh satu frame) -- selisihnya kecil, tidak diukur.

Contoh (env dibaca seperti agen; URL STT dari host lihat --stt-url):

    python scripts/bench_voice_latency.py --samples-dir /root/gpu-results/samples \
        --generate-samples --skip-llm --skip-tts --stt-p95-target-ms 500 \
        --out /root/gpu-results/voice-stt.csv

Dependensi: Python 3.10+, `pip install httpx` (opsional: agent/ di repo untuk
system prompt & filter halusinasi yang identik dengan agen).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
import wave
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_common import (  # noqa: E402
    REPO_ROOT,
    Check,
    base_metadata,
    check_max,
    env_or,
    load_env_file,
    percentile,
    stage_table,
    summarize,
    verdict,
    write_csv,
    write_json,
)

# Sama dengan default agen (agent/main.py) & plugin livekit-plugins-openai.
DEFAULT_STT_MODEL = "Systran/faster-whisper-small"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "ash"
TTS_INSTRUCTIONS = "Speak natural, professional Bahasa Indonesia with a warm interviewer tone."
TTS_AUDIO_STREAM_MODELS = {"tts-1", "tts-1-hd"}  # plugin: stream_format "audio", bukan "sse"
DEFAULT_NO_SPEECH_THRESHOLD = 0.6  # agent/whisper_filter.py

# Jawaban kandidat sintetis (bahasa Indonesia, 3-15 dtk) untuk --generate-samples.
SAMPLE_ANSWERS: dict[str, str] = {
    "jawab_01_singkat": "Saya sudah tiga tahun bekerja sebagai staf administrasi.",
    "jawab_02_motivasi": (
        "Saya tertarik dengan posisi ini karena ingin mengembangkan kemampuan "
        "analisis data dan bekerja di tim yang lebih besar."
    ),
    "jawab_03_konflik": (
        "Waktu itu ada perbedaan pendapat dengan rekan satu tim soal jadwal proyek. "
        "Saya mengajak dia diskusi berdua, kami membandingkan risikonya, lalu sepakat "
        "memundurkan satu tahap tanpa mengganggu tenggat akhir."
    ),
    "jawab_04_angka": (
        "Dalam satu bulan saya menangani sekitar dua ratus lima puluh transaksi, "
        "dengan tingkat kesalahan di bawah satu persen."
    ),
    "jawab_05_pelanggan": (
        "Di pekerjaan saya sebelumnya sebagai staf layanan pelanggan, saya menangani "
        "sekitar tiga puluh keluhan per hari. Saya mendengarkan dulu, mencatat "
        "masalahnya, lalu menawarkan solusi dan menindaklanjutinya dalam satu hari kerja."
    ),
    "jawab_06_ragu": "Hmm, sebentar ya. Mungkin contoh yang paling relevan adalah saat audit stok.",
    "jawab_07_teknis": (
        "Saya terbiasa memakai Excel untuk rekap penjualan, termasuk pivot table dan "
        "rumus VLOOKUP, dan sedikit belajar SQL untuk mengambil data dari sistem kasir."
    ),
    "jawab_08_penutup": "Tidak ada pertanyaan lagi dari saya, terima kasih atas kesempatannya.",
}
SAMPLE_VOICE = "alloy"  # bukan suara pewawancara (ash), seperti uji E2E Fase 66

# Pertanyaan yang "baru saja" diajukan pewawancara (konteks LLM satu giliran).
BENCH_CONTEXT = {
    "title": "Staf Administrasi Penjualan",
    "objective": "Menilai pengalaman kerja, komunikasi, dan ketelitian kandidat.",
    "questions": [
        {"text": "Ceritakan pengalaman kerja Anda yang paling relevan dengan posisi ini."},
        {"text": "Bagaimana Anda menangani perbedaan pendapat dengan rekan kerja?"},
        {"text": "Alat atau perangkat lunak apa yang biasa Anda pakai sehari-hari?"},
    ],
    "guidelines": [],
}
NEXT_QUESTION_RESULT = (
    "Pertanyaan 2 dari 3: Bagaimana Anda menangani perbedaan pendapat dengan rekan "
    "kerja? Ucapkan pertanyaan ini kepada kandidat."
)
FALLBACK_TTS_TEXT = "Baik, terima kasih atas jawabannya."
# Skema tool sama nama/parameternya dengan @function_tool di agent/main.py.
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "next_question",
            "description": "Ambil pertanyaan interview berikutnya.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_follow_up",
            "description": "Minta izin mengajukan SATU pertanyaan susulan.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_interview",
            "description": "Panggil SETELAH semua pertanyaan diajukan.",
            "parameters": {
                "type": "object",
                "properties": {"candidate_requested_stop": {"type": "boolean"}},
                "required": [],
            },
        },
    },
]

CSV_FIELDS = [
    "turn",
    "rep",
    "warmup",
    "sample",
    "audio_sec",
    "stt_ms",
    "stt_rtf",
    "llm_round1_ttft_ms",
    "llm_ttft_ms",
    "llm_first_sentence_ms",
    "llm_total_ms",
    "llm_tool_rounds",
    "tts_ttfb_ms",
    "tts_total_ms",
    "total_ms",
    "total_sentence_ms",
    "transcript",
    "reference_text",
    "wer",
    "llm_text",
    "tts_input_chars",
    "tts_bytes",
    "error",
]
STAGES = [
    "stt_ms",
    "llm_ttft_ms",
    "llm_first_sentence_ms",
    "llm_total_ms",
    "tts_ttfb_ms",
    "tts_total_ms",
    "total_ms",
    "total_sentence_ms",
]

_SENTENCE_END = re.compile(r"[.!?…](\s|$)")


# --------------------------------------------------------------------------- logika murni


def first_sentence(text: str) -> str | None:
    """Kalimat pertama lengkap (diakhiri . ! ? diikuti spasi/akhir), atau None."""
    m = _SENTENCE_END.search(text)
    return text[: m.end()].strip() if m else None


def normalize_words(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    """WER sederhana (Levenshtein kata / jumlah kata referensi). None bila ref kosong."""
    ref, hyp = normalize_words(reference), normalize_words(hypothesis)
    if not ref:
        return None
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def wav_duration(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / float(w.getframerate())


def pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def speech_text_fallback(body: Mapping[str, Any], threshold: float) -> str:
    """Salinan perilaku agent/whisper_filter.speech_text bila modul agen tidak
    ada: segmen dengan no_speech_prob >= ambang dibuang."""
    segments = body.get("segments")
    if not isinstance(segments, list) or threshold >= 1:
        return str(body.get("text") or "").strip()
    keep = [
        str(s.get("text") or "").strip()
        for s in segments
        if isinstance(s, Mapping) and float(s.get("no_speech_prob") or 0.0) < threshold
    ]
    return " ".join(t for t in keep if t).strip()


def compose_totals(row: dict[str, Any]) -> None:
    """Isi total_ms & total_sentence_ms hanya bila semua tahapnya terukur."""
    stt, ttft, sent, ttfb = (
        row.get("stt_ms"),
        row.get("llm_ttft_ms"),
        row.get("llm_first_sentence_ms"),
        row.get("tts_ttfb_ms"),
    )
    if None not in (stt, ttft, ttfb):
        row["total_ms"] = stt + ttft + ttfb
    if None not in (stt, sent, ttfb):
        row["total_sentence_ms"] = stt + sent + ttfb


def parse_sse_lines(lines: Sequence[str]) -> list[dict[str, Any]]:
    events = []
    for line in lines:
        if not line.startswith("data: "):
            continue
        data = line[6:].strip()
        if data == "[DONE]":
            break
        try:
            events.append(json.loads(data))
        except ValueError:
            continue
    return events


def summarize_turns(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    measured = [r for r in rows if not r.get("warmup")]
    errors = [r for r in measured if r.get("error")]
    stages = {s: summarize(r.get(s) for r in measured) for s in STAGES}
    rtfs = [r["stt_rtf"] for r in measured if r.get("stt_rtf") is not None]
    wers = [r["wer"] for r in measured if r.get("wer") is not None]
    return {
        "turns_total": len(rows),
        "turns_measured": len(measured),
        "turns_warmup": len(rows) - len(measured),
        "errors": len(errors),
        "error_rate": round(len(errors) / len(measured), 4) if measured else None,
        "tool_round_turns": sum(1 for r in measured if (r.get("llm_tool_rounds") or 0) > 0),
        "stages_ms": stages,
        "stt_rtf_p50": round(percentile(rtfs, 50) or 0, 3) if rtfs else None,
        "wer_mean": round(sum(wers) / len(wers), 4) if wers else None,
    }


def evaluate(summary: Mapping[str, Any], args: argparse.Namespace) -> list[Check]:
    st = summary["stages_ms"]
    checks = [
        check_max("stt_ms p95", st["stt_ms"]["p95"], args.stt_p95_target_ms),
        check_max(
            "error_rate", summary["error_rate"], args.max_error_rate, "giliran error / terukur"
        ),
    ]
    optional = [
        ("llm_ttft_ms p95", "llm_ttft_ms", args.llm_ttft_p95_target_ms),
        ("tts_ttfb_ms p95", "tts_ttfb_ms", args.tts_ttfb_p95_target_ms),
        ("total_ms p95", "total_ms", args.total_p95_target_ms),
    ]
    for name, key, target in optional:
        if target is not None:
            checks.append(check_max(name, st[key]["p95"], target))
    return checks


def resolve_out(out: Path) -> tuple[Path, Path]:
    """--out file.csv -> (file.csv, file.summary.json); --out DIR -> DIR/voice_turns.*"""
    if out.suffix.lower() == ".csv":
        return out, out.with_suffix(".summary.json")
    return out / "voice_turns.csv", out / "voice_summary.json"


# --------------------------------------------------------------------------- konfigurasi


@dataclass
class Config:
    stt_url: str
    stt_model: str
    stt_language: str
    stt_timeout: float
    no_speech_threshold: float
    llm_base_url: str | None
    api_key: str
    llm_model: str
    tts_model: str
    tts_voice: str
    stt_compute_type: str
    stt_device: str
    extras: dict[str, Any] = field(default_factory=dict)


def build_config(args: argparse.Namespace, environ: Mapping[str, str]) -> Config:
    """CLI menang atas env; nama env sama dengan yang dibaca agent/main.py."""
    stt_base = args.stt_url or env_or(environ, "STT_BASE_URL")
    if not stt_base:
        raise SystemExit("STT_BASE_URL kosong: set env STT_BASE_URL atau --stt-url")
    try:
        threshold = float(env_or(environ, "STT_NO_SPEECH_THRESHOLD") or "")
    except ValueError:
        threshold = DEFAULT_NO_SPEECH_THRESHOLD
    return Config(
        stt_url=f"{stt_base.rstrip('/')}/audio/transcriptions",
        stt_model=args.stt_model or env_or(environ, "STT_MODEL", default=DEFAULT_STT_MODEL),
        stt_language=args.stt_language or env_or(environ, "STT_LANGUAGE", default="id"),
        stt_timeout=float(env_or(environ, "STT_TIMEOUT_SEC", default="60") or 60),
        no_speech_threshold=threshold,
        llm_base_url=(args.llm_base_url or env_or(environ, "AI_BASE_URL") or "").rstrip("/")
        or None,
        api_key=env_or(environ, "AI_API_KEY", default="not-needed") or "not-needed",
        llm_model=args.llm_model
        or env_or(environ, "AI_AGENT_MODEL", "AI_MODEL", default=DEFAULT_LLM_MODEL),
        tts_model=args.tts_model or env_or(environ, "AI_TTS_MODEL", default=DEFAULT_TTS_MODEL),
        tts_voice=args.tts_voice or env_or(environ, "AI_TTS_VOICE", default=DEFAULT_TTS_VOICE),
        stt_compute_type=args.stt_compute_type
        or env_or(environ, "STT_COMPUTE_TYPE", default="tidak diketahui"),
        stt_device=args.stt_device or "tidak diketahui",
    )


def _agent_helpers() -> tuple[Callable[[Mapping[str, Any], float], str], str, str]:
    """Pakai kode agen asli bila checkout lengkap (system prompt & filter
    halusinasi identik); kalau tidak, salinan minimal di skrip ini."""
    agent_dir = REPO_ROOT / "agent"
    if agent_dir.is_dir():
        sys.path.insert(0, str(agent_dir))
        try:
            from interview_flow import build_instructions  # type: ignore[import-not-found]
            from whisper_filter import speech_text  # type: ignore[import-not-found]

            return speech_text, build_instructions(BENCH_CONTEXT), "agent/interview_flow.py"
        except Exception:  # noqa: BLE001
            pass
    prompt = (
        f'Anda pewawancara AI untuk posisi "{BENCH_CONTEXT["title"]}". Interview terstruktur, '
        "Bahasa Indonesia, nada profesional tapi hangat. Dapatkan pertanyaan berikutnya HANYA "
        "lewat tool next_question."
    )
    return speech_text_fallback, prompt, "fallback (agent/ tidak ditemukan)"


# --------------------------------------------------------------------------- jaringan


def generate_samples(http: Any, cfg: Config, samples_dir: Path, voice: str) -> list[str]:
    """Sintesis SAMPLE_ANSWERS lewat TTS yang dikonfigurasi (PCM 24 kHz -> WAV)
    + file .txt referensi untuk WER. File yang sudah ada tidak dibuat ulang."""
    if not cfg.llm_base_url:
        raise SystemExit("--generate-samples butuh AI_BASE_URL/AI_API_KEY (TTS)")
    samples_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for name, text in SAMPLE_ANSWERS.items():
        wav_path = samples_dir / f"{name}.wav"
        if wav_path.exists():
            continue
        resp = http.post(
            f"{cfg.llm_base_url}/audio/speech",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            json={
                "model": cfg.tts_model,
                "voice": voice,
                "input": text,
                "response_format": "pcm",  # int16 mono 24 kHz
            },
            timeout=60,
        )
        resp.raise_for_status()
        wav_path.write_bytes(pcm_to_wav(resp.content))
        (samples_dir / f"{name}.txt").write_text(text, encoding="utf-8")
        made.append(name)
    return made


def run_stt(http: Any, cfg: Config, wav: bytes, filter_fn: Callable) -> tuple[float, str]:
    t0 = time.perf_counter()
    resp = http.post(
        cfg.stt_url,
        files={"file": ("file.wav", wav, "audio/wav")},
        data={
            "model": cfg.stt_model,
            "language": cfg.stt_language,
            "response_format": "verbose_json",
        },
        timeout=cfg.stt_timeout,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    return elapsed, filter_fn(resp.json(), cfg.no_speech_threshold)


@dataclass
class LlmRound:
    first_at: float | None  # perf_counter delta pertama (teks ATAU tool call)
    text_at: float | None  # delta teks pertama
    sentence_at: float | None  # kalimat pertama lengkap
    text: str
    calls: list[dict[str, Any]]
    done_at: float


def stream_chat(http: Any, cfg: Config, messages: list[dict[str, Any]], tools: bool) -> LlmRound:
    """Satu putaran chat completion streaming (parameter seperti plugin
    LiveKit: stream + include_usage, tools agen). Waktu = perf_counter."""
    body: dict[str, Any] = {
        "model": cfg.llm_model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        body["tools"] = AGENT_TOOLS
    first: float | None = None
    text_at: float | None = None
    sentence_at: float | None = None
    text = ""
    calls: dict[int, dict[str, Any]] = {}
    with http.stream(
        "POST",
        f"{cfg.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {cfg.api_key}"},
        json=body,
        timeout=60,
    ) as resp:
        if resp.status_code >= 400:
            resp.read()
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        for line in resp.iter_lines():
            for ev in parse_sse_lines([line]):
                for choice in ev.get("choices") or []:
                    delta = choice.get("delta") or {}
                    now = time.perf_counter()
                    if delta.get("content"):
                        first = first or now
                        text_at = text_at or now
                        text += delta["content"]
                        if sentence_at is None and first_sentence(text) is not None:
                            sentence_at = now
                    for tc in delta.get("tool_calls") or []:
                        first = first or now
                        slot = calls.setdefault(
                            int(tc.get("index", 0)), {"id": "", "name": "", "args": ""}
                        )
                        slot["id"] = tc.get("id") or slot["id"]
                        fn = tc.get("function") or {}
                        slot["name"] += fn.get("name") or ""
                        slot["args"] += fn.get("arguments") or ""
        done = time.perf_counter()
    return LlmRound(first, text_at, sentence_at, text, [calls[k] for k in sorted(calls)], done)


def run_llm(
    http: Any, cfg: Config, system_prompt: str, transcript: str, tools: bool
) -> dict[str, Any]:
    """Maks. 2 putaran: bila putaran 1 hanya memanggil tool, hasil tool dikirim
    (seperti agen) dan waktu sampai teks pertama di putaran 2 yang dihitung."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": BENCH_CONTEXT["questions"][0]["text"]},
        {"role": "user", "content": transcript or "(tidak terdengar)"},
    ]
    t0 = time.perf_counter()

    def ms(t: float | None) -> float | None:
        return None if t is None else (t - t0) * 1000

    out: dict[str, Any] = {"llm_tool_rounds": 0}
    text = ""
    text_at: float | None = None
    sentence_at: float | None = None
    rnd: LlmRound | None = None
    for round_no in range(2):
        rnd = stream_chat(http, cfg, messages, tools)
        if round_no == 0:
            out["llm_round1_ttft_ms"] = ms(rnd.first_at)
        text += rnd.text
        text_at = text_at or rnd.text_at
        sentence_at = sentence_at or rnd.sentence_at
        if rnd.text or not rnd.calls:
            break
        out["llm_tool_rounds"] += 1
        ids = [c["id"] or f"call_{i}" for i, c in enumerate(rnd.calls)]
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": cid,
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["args"] or "{}"},
                    }
                    for cid, c in zip(ids, rnd.calls, strict=True)
                ],
            }
        )
        for cid, c in zip(ids, rnd.calls, strict=True):
            result = NEXT_QUESTION_RESULT if c["name"] == "next_question" else "OK"
            messages.append({"role": "tool", "tool_call_id": cid, "content": result})
    assert rnd is not None
    out["llm_total_ms"] = ms(rnd.done_at)
    out["llm_ttft_ms"] = ms(text_at)
    # Balasan tanpa tanda akhir kalimat: TTS baru jalan saat stream selesai.
    if sentence_at is not None:
        out["llm_first_sentence_ms"] = ms(sentence_at)
    else:
        out["llm_first_sentence_ms"] = ms(rnd.done_at) if text else None
    out["llm_text"] = text
    return out


def run_tts(http: Any, cfg: Config, text: str) -> dict[str, Any]:
    """Seperti livekit-plugins-openai TTS.ChunkedStream: mp3, instructions,
    stream_format sse (kecuali tts-1*). Server yang mengabaikan stream_format
    mengirim byte audio langsung -- dua-duanya ditangani lewat Content-Type."""
    body = {
        "model": cfg.tts_model,
        "voice": cfg.tts_voice,
        "input": text,
        "response_format": "mp3",
        "speed": 1.0,
        "instructions": TTS_INSTRUCTIONS,
        "stream_format": "audio" if cfg.tts_model in TTS_AUDIO_STREAM_MODELS else "sse",
    }
    t0 = time.perf_counter()
    first: float | None = None
    nbytes = 0
    with http.stream(
        "POST",
        f"{cfg.llm_base_url}/audio/speech",
        headers={"Authorization": f"Bearer {cfg.api_key}"},
        json=body,
        timeout=60,
    ) as resp:
        if resp.status_code >= 400:
            resp.read()
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype == "text/event-stream":
            for line in resp.iter_lines():
                for ev in parse_sse_lines([line]):
                    if ev.get("type") != "speech.audio.delta":
                        continue
                    chunk = base64.b64decode(ev.get("delta") or ev.get("audio") or "")
                    if chunk:
                        first = first or time.perf_counter()
                        nbytes += len(chunk)
        else:
            for chunk in resp.iter_bytes():
                if chunk:
                    first = first or time.perf_counter()
                    nbytes += len(chunk)
        done = time.perf_counter()
    if not nbytes:
        raise RuntimeError("TTS tidak mengirim audio")
    return {
        "tts_ttfb_ms": (first - t0) * 1000 if first else None,
        "tts_total_ms": (done - t0) * 1000,
        "tts_bytes": nbytes,
        "tts_input_chars": len(text),
    }


# --------------------------------------------------------------------------- utama


def load_samples(samples_dir: Path) -> list[tuple[str, bytes, str | None]]:
    out = []
    for path in sorted(samples_dir.glob("*.wav")):
        ref = path.with_suffix(".txt")
        text = ref.read_text(encoding="utf-8").strip() if ref.exists() else None
        out.append((path.name, path.read_bytes(), text))
    return out


def run_turn(
    http: Any,
    cfg: Config,
    args: argparse.Namespace,
    sample: tuple[str, bytes, str | None],
    helpers: tuple[Callable, str, str],
) -> dict[str, Any]:
    name, wav, ref = sample
    filter_fn, system_prompt, _ = helpers
    row: dict[str, Any] = {"sample": name, "reference_text": ref or ""}
    try:
        row["audio_sec"] = round(wav_duration(wav), 2)
    except (wave.Error, EOFError) as exc:
        row["error"] = f"wav: {exc}"
        return row
    stage = "stt"
    try:
        row["stt_ms"], row["transcript"] = run_stt(http, cfg, wav, filter_fn)
        row["stt_rtf"] = (
            round(row["stt_ms"] / 1000 / row["audio_sec"], 3) if row["audio_sec"] else None
        )
        if ref:
            row["wer"] = word_error_rate(ref, row["transcript"])
        tts_text = FALLBACK_TTS_TEXT
        if not args.skip_llm:
            stage = "llm"
            row.update(run_llm(http, cfg, system_prompt, row["transcript"], not args.llm_no_tools))
            tts_text = first_sentence(row["llm_text"]) or row["llm_text"].strip() or tts_text
        if not args.skip_tts:
            stage = "tts"
            row.update(run_tts(http, cfg, tts_text))
    except Exception as exc:  # noqa: BLE001 - dicatat per giliran, bench jalan terus
        row["error"] = f"{stage}: {type(exc).__name__}: {exc}"[:300]
    compose_totals(row)
    return row


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Benchmark latensi STT -> LLM -> TTS AI Interview (lihat docstring skrip).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    a = p.add_argument
    a("--samples-dir", type=Path, required=True, help="folder *.wav (+ .txt = teks referensi/WER)")
    a("--out", type=Path, required=True, help="file .csv (+ <nama>.summary.json) atau folder")
    a(
        "--generate-samples",
        action="store_true",
        help="sintesis jawaban Indonesia via TTS ke --samples-dir (file yang ada dilewati)",
    )
    a("--sample-voice", default=SAMPLE_VOICE, help="suara TTS untuk sampel kandidat")
    a("--repeats", type=int, default=3, help="berapa kali seluruh sampel diputar")
    a("--warmup", type=int, default=2, help="giliran awal yang TIDAK dihitung di statistik")
    a("--skip-llm", action="store_true", help="tanpa tahap LLM (tidak butuh API key)")
    a("--skip-tts", action="store_true", help="tanpa tahap TTS (tidak butuh API key)")
    a("--llm-no-tools", action="store_true", help="LLM tanpa tool agen (default: dengan tool)")
    a("--env-file", type=Path, help="muat KEY=VALUE (tidak menimpa env yang sudah ada)")
    a("--stt-url", help="base URL STT, mis. http://127.0.0.1:8001/v1 (default env STT_BASE_URL)")
    a("--stt-model", help=f"default env STT_MODEL atau {DEFAULT_STT_MODEL}")
    a("--stt-language", help="default env STT_LANGUAGE atau id")
    a("--stt-compute-type", help="label metadata (default env STT_COMPUTE_TYPE)")
    a("--stt-device", help="label metadata, mis. 'cuda RTX 4090' (tidak bisa ditanya ke server)")
    a("--llm-base-url", help="default env AI_BASE_URL (dipakai juga untuk TTS, seperti agen)")
    a("--llm-model", help=f"default env AI_AGENT_MODEL -> AI_MODEL -> {DEFAULT_LLM_MODEL}")
    a("--tts-model", help=f"default env AI_TTS_MODEL atau {DEFAULT_TTS_MODEL}")
    a("--tts-voice", help=f"default env AI_TTS_VOICE atau {DEFAULT_TTS_VOICE}")
    a("--stt-p95-target-ms", type=float, default=500.0, help="GAGAL bila p95 STT melebihi ini")
    a("--max-error-rate", type=float, default=0.05, help="GAGAL bila rasio giliran error > ini")
    a("--llm-ttft-p95-target-ms", type=float, help="ambang opsional")
    a("--tts-ttfb-p95-target-ms", type=float, help="ambang opsional")
    a("--total-p95-target-ms", type=float, help="ambang opsional (total_ms)")
    a("--label", help="catatan bebas di metadata, mis. 'large-v3 fp16 RTX4090'")
    return p


def main(argv: Sequence[str] | None = None, environ: dict[str, str] | None = None) -> int:
    import httpx  # di sini supaya logika murni bisa dites tanpa httpx

    args = build_parser().parse_args(argv)
    env: dict[str, str] = dict(os.environ) if environ is None else environ
    if args.env_file:
        load_env_file(args.env_file, env)
    cfg = build_config(args, env)
    needs_api = args.generate_samples or not (args.skip_llm and args.skip_tts)
    if needs_api and not cfg.llm_base_url:
        raise SystemExit("AI_BASE_URL kosong: set env/--llm-base-url, atau --skip-llm --skip-tts")
    helpers = _agent_helpers()
    csv_path, json_path = resolve_out(args.out)

    with httpx.Client() as http:
        if args.generate_samples:
            made = generate_samples(http, cfg, args.samples_dir, args.sample_voice)
            print(f"Sampel dibuat: {len(made)} baru di {args.samples_dir}")
        samples = load_samples(args.samples_dir)
        if not samples:
            raise SystemExit(f"Tidak ada *.wav di {args.samples_dir} (pakai --generate-samples?)")

        meta = base_metadata(args.label)
        meta.update(
            {
                "script": "bench_voice_latency.py",
                "stt_url": cfg.stt_url,
                "stt_model": cfg.stt_model,
                "stt_language": cfg.stt_language,
                "stt_compute_type": cfg.stt_compute_type,
                "stt_device": cfg.stt_device,
                "stt_no_speech_threshold": cfg.no_speech_threshold,
                "llm_model": None if args.skip_llm else cfg.llm_model,
                "llm_tools": None if args.skip_llm else not args.llm_no_tools,
                "llm_system_prompt_source": helpers[2],
                "tts_model": None if args.skip_tts else cfg.tts_model,
                "tts_voice": None if args.skip_tts else cfg.tts_voice,
                "samples": [s[0] for s in samples],
                "repeats": args.repeats,
                "warmup": args.warmup,
                "total_ms_definition": (
                    "stt_ms + llm_ttft_ms + tts_ttfb_ms; TANPA VAD/endpointing/turn detector "
                    "dan transport WebRTC"
                ),
            }
        )
        print(f"GPU mesin bench: {meta['bench_host_gpu']}")
        print(
            f"STT: {cfg.stt_model} @ {cfg.stt_url} "
            f"(compute_type: {cfg.stt_compute_type}, device: {cfg.stt_device})"
        )
        rows: list[dict[str, Any]] = []
        turn = 0
        for rep in range(args.repeats):
            for sample in samples:
                row = run_turn(http, cfg, args, sample, helpers)
                row.update({"turn": turn, "rep": rep, "warmup": turn < args.warmup})
                rows.append(row)
                print(
                    f"  #{turn:<3} {sample[0]:<26} audio={row.get('audio_sec')}s "
                    f"stt={_f(row.get('stt_ms'))} llm_ttft={_f(row.get('llm_ttft_ms'))} "
                    f"tts_ttfb={_f(row.get('tts_ttfb_ms'))} total={_f(row.get('total_ms'))}"
                    f"{'  WARMUP' if row['warmup'] else ''}"
                    f"{'  ERROR ' + row['error'] if row.get('error') else ''}",
                    flush=True,
                )
                turn += 1

    summary = summarize_turns(rows)
    checks = evaluate(summary, args)
    passed = verdict(checks, skipped_is_failure=("stt_ms p95", "error_rate"))
    write_csv(csv_path, rows, CSV_FIELDS)
    write_json(
        json_path,
        {
            "metadata": meta,
            "summary": summary,
            "checks": [c.as_dict() for c in checks],
            "passed": passed,
        },
    )
    print()
    print(stage_table(summary["stages_ms"]))
    print(
        f"giliran terukur {summary['turns_measured']} (warmup {summary['turns_warmup']}), "
        f"error {summary['errors']}, STT RTF p50 {summary['stt_rtf_p50']}, "
        f"WER rata-rata {summary['wer_mean']}, "
        f"giliran dengan putaran tool {summary['tool_round_turns']}"
    )
    if not meta["bench_host_has_gpu"]:
        print(
            "CATATAN: mesin bench TANPA GPU (nvidia-smi tidak ada). Angka ini BUKAN angka GPU, "
            "kecuali stt-server berjalan di mesin lain yang ber-GPU."
        )
    for c in checks:
        print(c.line())
    print(f"HASIL: {'LULUS' if passed else 'GAGAL'}  -> {csv_path} , {json_path}")
    return 0 if passed else 1


def _f(v: float | None) -> str:
    return "-" if v is None else f"{v:.0f}ms"


if __name__ == "__main__":
    sys.exit(main())
