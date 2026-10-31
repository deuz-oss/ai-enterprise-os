"""bench_voice_latency: logika murni + E2E terhadap server OpenAI-compatible
PALSU (STT faster-whisper verbose_json, chat SSE dengan tool call, TTS SSE)."""

import asyncio
import base64
import csv
import json
import threading
from argparse import Namespace

import pytest
from aiohttp import web
from bench_voice_latency import (
    compose_totals,
    evaluate,
    first_sentence,
    main,
    pcm_to_wav,
    resolve_out,
    speech_text_fallback,
    summarize_turns,
    wav_duration,
    word_error_rate,
)


def test_first_sentence():
    assert first_sentence("Baik, terima kasih. Pertanyaan berikutnya") == "Baik, terima kasih."
    assert first_sentence("Apa kabar? Baik") == "Apa kabar?"
    assert first_sentence("versi 1.5 belum selesai") is None  # titik desimal bukan akhir
    assert first_sentence("Selesai.") == "Selesai."


def test_word_error_rate():
    assert word_error_rate("Saya tiga tahun", "saya tiga tahun.") == 0
    assert word_error_rate("a b c d", "a x c") == pytest.approx(0.5)  # 1 ganti + 1 hapus
    assert word_error_rate("", "apa") is None


def test_wav_roundtrip_duration():
    wav = pcm_to_wav(b"\x00\x00" * 24000 * 2)
    assert wav_duration(wav) == pytest.approx(2.0)


def test_speech_text_fallback_drops_no_speech_segments():
    body = {
        "text": "Halo semua. Terima kasih kerana menonton.",
        "segments": [
            {"text": " Halo semua.", "no_speech_prob": 0.1},
            {"text": " Terima kasih kerana menonton.", "no_speech_prob": 0.9},
        ],
    }
    assert speech_text_fallback(body, 0.6) == "Halo semua."
    assert speech_text_fallback(body, 1.0) == body["text"]


def test_totals_only_when_all_stages_present():
    row = {"stt_ms": 300.0, "llm_ttft_ms": 400.0, "tts_ttfb_ms": 200.0}
    compose_totals(row)
    assert row["total_ms"] == 900.0 and "total_sentence_ms" not in row
    row = {"stt_ms": 300.0}
    compose_totals(row)
    assert "total_ms" not in row


def test_summary_excludes_warmup_and_evaluates_thresholds():
    rows = [
        {"warmup": True, "stt_ms": 9000.0},
        {"warmup": False, "stt_ms": 400.0},
        {"warmup": False, "stt_ms": 450.0},
        {"warmup": False, "stt_ms": None, "error": "stt: timeout"},
    ]
    s = summarize_turns(rows)
    assert s["turns_measured"] == 3 and s["errors"] == 1
    assert s["stages_ms"]["stt_ms"]["max"] == 450  # warmup 9000 tidak ikut
    args = Namespace(
        stt_p95_target_ms=500,
        max_error_rate=0.05,
        llm_ttft_p95_target_ms=None,
        tts_ttfb_p95_target_ms=None,
        total_p95_target_ms=1500,
    )
    checks = {c.name: c for c in evaluate(s, args)}
    assert checks["stt_ms p95"].ok is True
    assert checks["error_rate"].ok is False  # 1/3 > 5%
    assert checks["total_ms p95"].ok is None  # tidak ada data -> dilewati


def test_resolve_out(tmp_path):
    assert resolve_out(tmp_path / "v.csv") == (tmp_path / "v.csv", tmp_path / "v.summary.json")
    assert resolve_out(tmp_path / "dir")[0].name == "voice_turns.csv"


# --------------------------------------------------------------------------- server palsu


class FakeOpenAI:
    def __init__(self, stt_status: int = 200) -> None:
        self.stt_status = stt_status
        self.requests: list[tuple[str, dict]] = []
        self.port = 0
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runner: web.AppRunner | None = None

    async def stt(self, request: web.Request) -> web.Response:
        form = await request.post()
        fields = {k: form[k] for k in ("model", "language", "response_format")}
        assert form["file"].filename == "file.wav"
        self.requests.append(("stt", fields))
        if self.stt_status != 200:
            return web.Response(status=self.stt_status, text="model belum dimuat")
        return web.json_response(
            {
                "text": "Saya sudah tiga tahun bekerja. Terima kasih kerana menonton.",
                "segments": [
                    {"text": " Saya sudah tiga tahun bekerja.", "no_speech_prob": 0.05},
                    {"text": " Terima kasih kerana menonton.", "no_speech_prob": 0.95},
                ],
            }
        )

    async def chat(self, request: web.Request) -> web.StreamResponse:
        body = await request.json()
        self.requests.append(("chat", body))
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await resp.prepare(request)

        async def send(delta: dict) -> None:
            chunk = {"choices": [{"index": 0, "delta": delta}]}
            await resp.write(f"data: {json.dumps(chunk)}\n\n".encode())
            await asyncio.sleep(0.01)

        if not any(m["role"] == "tool" for m in body["messages"]):
            await send(
                {
                    "tool_calls": [
                        {"index": 0, "id": "call_1", "function": {"name": "next_", "arguments": ""}}
                    ]
                }
            )
            await send({"tool_calls": [{"index": 0, "function": {"name": "question"}}]})
        else:
            for part in ["Baik, ", "terima kasih. ", "Pertanyaan ", "berikutnya?"]:
                await send({"content": part})
        await resp.write(b'data: {"choices": [], "usage": {"total_tokens": 9}}\n\n')
        await resp.write(b"data: [DONE]\n\n")
        return resp

    async def speech(self, request: web.Request) -> web.StreamResponse:
        body = await request.json()
        self.requests.append(("tts", body))
        if body.get("response_format") == "pcm":  # --generate-samples
            return web.Response(body=b"\x01\x00" * 24000, content_type="audio/pcm")
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await resp.prepare(request)
        for _ in range(3):
            delta = base64.b64encode(b"\xff\xfb" + b"\x00" * 100).decode()
            ev = {"type": "speech.audio.delta", "audio": delta}
            await resp.write(f"data: {json.dumps(ev)}\n\n".encode())
            await asyncio.sleep(0.01)
        await resp.write(b'data: {"type": "speech.audio.done", "usage": {}}\n\n')
        return resp

    def __enter__(self) -> "FakeOpenAI":
        def serve() -> None:
            self._loop = asyncio.new_event_loop()
            app = web.Application()
            app.router.add_post("/v1/audio/transcriptions", self.stt)
            app.router.add_post("/v1/chat/completions", self.chat)
            app.router.add_post("/v1/audio/speech", self.speech)
            self._runner = web.AppRunner(app)
            self._loop.run_until_complete(self._runner.setup())
            site = web.TCPSite(self._runner, "127.0.0.1", 0)
            self._loop.run_until_complete(site.start())
            self.port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
            self._ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=serve, daemon=True)
        self._thread.start()
        self._ready.wait(10)
        return self

    def __exit__(self, *exc: object) -> None:
        assert self._loop is not None and self._runner is not None
        asyncio.run_coroutine_threadsafe(self._runner.cleanup(), self._loop).result(10)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(10)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"


def _env(server: FakeOpenAI) -> dict[str, str]:
    return {
        "STT_BASE_URL": server.url,
        "STT_MODEL": "Systran/faster-whisper-large-v3",
        "AI_BASE_URL": server.url,
        "AI_API_KEY": "sk-palsu",
        "AI_MODEL": "gpt-4o-mini",
        "AI_AGENT_MODEL": "gpt-4.1-mini",
    }


def test_full_pipeline_against_fake_server(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "voice.csv"
    with FakeOpenAI() as server:
        code = main(
            [
                "--samples-dir",
                str(samples),
                "--generate-samples",
                "--repeats",
                "1",
                "--warmup",
                "1",
                "--out",
                str(out),
            ],
            environ=_env(server),
        )
        reqs = list(server.requests)
    assert code == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 8 and not any(r["error"] for r in rows)
    r = rows[1]
    assert r["transcript"] == "Saya sudah tiga tahun bekerja."  # halusinasi dibuang
    assert r["llm_tool_rounds"] == "1"  # tool call dulu, lalu putaran teks
    assert r["llm_text"].startswith("Baik, terima kasih.")
    assert float(r["llm_ttft_ms"]) >= float(r["llm_round1_ttft_ms"])
    assert float(r["llm_first_sentence_ms"]) >= float(r["llm_ttft_ms"])
    assert int(r["tts_input_chars"]) == len("Baik, terima kasih.")
    total = float(r["stt_ms"]) + float(r["llm_ttft_ms"]) + float(r["tts_ttfb_ms"])
    assert float(r["total_ms"]) == pytest.approx(total, abs=0.05)
    assert r["wer"] != ""  # .txt referensi dari --generate-samples

    stt_req = next(b for kind, b in reqs if kind == "stt")
    assert stt_req == {
        "model": "Systran/faster-whisper-large-v3",
        "language": "id",
        "response_format": "verbose_json",
    }
    chat = next(b for kind, b in reqs if kind == "chat")
    assert chat["model"] == "gpt-4.1-mini" and chat["stream"] is True
    assert {t["function"]["name"] for t in chat["tools"]} == {
        "next_question",
        "request_follow_up",
        "end_interview",
    }
    tts = [b for kind, b in reqs if kind == "tts" and b["response_format"] == "mp3"][0]
    assert tts["model"] == "gpt-4o-mini-tts" and tts["voice"] == "ash"
    assert tts["stream_format"] == "sse" and "Bahasa Indonesia" in tts["instructions"]

    summary = json.loads((tmp_path / "voice.summary.json").read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["summary"]["turns_measured"] == 7
    assert summary["metadata"]["stt_model"] == "Systran/faster-whisper-large-v3"
    assert "bench_host_gpu" in summary["metadata"]


def test_stt_only_needs_no_api_key_and_fails_on_target(tmp_path):
    samples = tmp_path / "s"
    samples.mkdir()
    (samples / "a.wav").write_bytes(pcm_to_wav(b"\x00\x00" * 16000, 16000))
    with FakeOpenAI() as server:
        env = {"STT_BASE_URL": server.url}
        args = ["--samples-dir", str(samples), "--skip-llm", "--skip-tts", "--warmup", "0"]
        out = tmp_path / "o.csv"
        assert main([*args, "--out", str(out)], environ=dict(env)) == 0
        # Target mustahil -> exit 1 (dipakai runbook sebagai lulus/gagal).
        assert main([*args, "--out", str(out), "--stt-p95-target-ms", "0.001"], environ=env) == 1


def test_stt_errors_fail_run(tmp_path):
    samples = tmp_path / "s"
    samples.mkdir()
    (samples / "a.wav").write_bytes(pcm_to_wav(b"\x00\x00" * 16000, 16000))
    with FakeOpenAI(stt_status=500) as server:
        code = main(
            [
                "--samples-dir",
                str(samples),
                "--skip-llm",
                "--skip-tts",
                "--warmup",
                "0",
                "--out",
                str(tmp_path / "o.csv"),
            ],
            environ={"STT_BASE_URL": server.url},
        )
    assert code == 1
    rows = list(csv.DictReader((tmp_path / "o.csv").open(encoding="utf-8")))
    assert rows[0]["error"].startswith("stt: RuntimeError: HTTP 500")
