"""FlashHeadRenderer terhadap flashhead-server PALSU (protokol yang sama,
tanpa GPU): pasangan frame-audio, penolakan saat penuh, dan turun ke
StaticRenderer saat server putus/lambat -- audio TIDAK boleh hilang, karena
agen menunggu laporan selesai putar untuk tiap ucapan."""

import asyncio
import io
import json

import numpy as np
import pytest
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer
from PIL import Image
from renderers import (
    SAMPLES_PER_FRAME,
    SEGMENT_END,
    FlashHeadRenderer,
    RenderedFrame,
    RendererUnavailable,
)

SLICE_FRAMES = 4  # server palsu memakai chunk kecil supaya tes cepat
RECEIVED: list[dict] = []  # pesan teks klien -> server palsu


def jpeg(color) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (512, 512), color).save(buf, "JPEG")
    return buf.getvalue()


def fake_server(mode: str) -> web.Application:
    async def stream(request):
        ws = web.WebSocketResponse(max_msg_size=0)
        await ws.prepare(request)
        start = json.loads((await ws.receive()).data)
        assert start["type"] == "start" and start["image"]
        if mode == "busy":
            await ws.send_json({"type": "error", "code": "busy", "detail": "slot GPU penuh"})
            await ws.close()
            return ws
        await ws.send_json({"type": "ready", "slice_frames": SLICE_FRAMES, "fps": 25})
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                RECEIVED.append(json.loads(msg.data))
                continue
            if msg.type != WSMsgType.BINARY:
                continue
            # audio 16 kHz: SLICE_FRAMES * 640 sampel int16
            assert len(msg.data) == SLICE_FRAMES * 640 * 2
            if mode == "drop":
                await ws.close()
                break
            if mode == "stall":
                continue
            for i in range(SLICE_FRAMES):
                await ws.send_bytes(jpeg((10 * i, 0, 0)))
            await ws.send_json({"type": "chunk_done"})
        return ws

    app = web.Application()
    app.router.add_get("/stream", stream)
    return app


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "foto.png"
    Image.new("RGB", (512, 512), (120, 120, 120)).save(p)
    return p


async def collect_until(renderer, predicate, limit=2000):
    out = []
    async for item in renderer.frames():
        out.append(item)
        if predicate(out) or len(out) >= limit:
            break
        await asyncio.sleep(0.001)
    return out


def segments_done(out):
    return any(item is SEGMENT_END for item in out)


def spoken_audio(out) -> np.ndarray:
    parts = [f.audio for f in out if isinstance(f, RenderedFrame) and f.audio is not None]
    return np.concatenate(parts) if parts else np.zeros(0, np.int16)


def run_with_server(mode, body):
    async def run():
        server = TestServer(fake_server(mode))
        await server.start_server()
        try:
            return await body(f"ws://127.0.0.1:{server.port}/stream")
        finally:
            await server.close()

    return asyncio.run(run())


def test_frames_paired_with_audio_in_order(photo):
    n = SLICE_FRAMES * SAMPLES_PER_FRAME
    audio = np.arange(n * 2, dtype=np.int16)

    async def body(url):
        r = FlashHeadRenderer(url)
        await r.start(photo)
        await r.push_audio(audio)
        await r.end_segment()
        out = await collect_until(r, segments_done)
        await r.aclose()
        return r, out

    r, out = run_with_server("ok", body)
    assert not r.degraded
    assert np.array_equal(spoken_audio(out), audio)
    speech = [f for f in out if isinstance(f, RenderedFrame) and f.audio is not None]
    assert len(speech) == 2 * SLICE_FRAMES
    assert speech[1].image[0, 0, 0] > speech[0].image[0, 0, 0]  # frame dari server, urut


def test_busy_server_is_unavailable(photo):
    async def body(url):
        await FlashHeadRenderer(url).start(photo)

    with pytest.raises(RendererUnavailable):
        run_with_server("busy", body)


def test_unreachable_server_is_unavailable(photo):
    async def run():
        await FlashHeadRenderer("ws://127.0.0.1:9/stream", ready_timeout=2).start(photo)

    with pytest.raises(RendererUnavailable):
        asyncio.run(run())


@pytest.mark.parametrize("mode", ["drop", "stall"])
def test_server_failure_degrades_without_losing_audio(photo, mode):
    n = SLICE_FRAMES * SAMPLES_PER_FRAME
    audio = (np.arange(int(n * 1.5)) % 1000 + 1).astype(np.int16)

    async def body(url):
        r = FlashHeadRenderer(url, chunk_timeout=0.3)
        await r.start(photo)
        await r.push_audio(audio)
        await r.end_segment()
        out = await asyncio.wait_for(collect_until(r, segments_done), 10)
        await r.aclose()
        return r, out

    r, out = run_with_server(mode, body)
    assert r.degraded
    assert segments_done(out)  # agen tetap menerima akhir ucapan -> tidak menggantung
    got = spoken_audio(out)
    assert np.array_equal(got[: len(audio)], audio)


def test_backlog_degrades(photo):
    n = SLICE_FRAMES * SAMPLES_PER_FRAME

    async def body(url):
        r = FlashHeadRenderer(url, chunk_timeout=30, max_backlog=1)
        await r.start(photo)
        await r.push_audio(np.ones(n * 3, np.int16))
        await r.end_segment()
        out = await asyncio.wait_for(collect_until(r, segments_done), 10)
        await r.aclose()
        return r, out

    r, out = run_with_server("stall", body)
    assert r.degraded
    assert len(spoken_audio(out)) >= n * 3


def test_clear_drops_audio_and_resets_server_context(photo):
    n = SLICE_FRAMES * SAMPLES_PER_FRAME
    RECEIVED.clear()

    async def body(url):
        r = FlashHeadRenderer(url)
        await r.start(photo)
        await r.push_audio(np.ones(n // 2, np.int16))  # belum cukup satu chunk
        r.clear()
        await asyncio.sleep(0.2)
        await r.end_segment()
        out = await collect_until(r, segments_done)
        await r.aclose()
        return r, out

    r, out = run_with_server("ok", body)
    assert not r.degraded
    assert len(spoken_audio(out)) == 0  # audio terpotong tidak diputar
    assert {"type": "reset"} in RECEIVED
