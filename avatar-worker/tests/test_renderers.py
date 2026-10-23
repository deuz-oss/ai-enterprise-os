"""Kontrak interface AvatarRenderer (StaticRenderer) dan antrean audio."""

import asyncio

import numpy as np
import pytest
from PIL import Image
from renderers import (
    HEIGHT,
    SAMPLES_PER_FRAME,
    SEGMENT_END,
    WIDTH,
    AudioFifo,
    FlashHeadRenderer,
    RenderedFrame,
    RendererUnavailable,
    SegmentEnd,
    StaticRenderer,
    make_renderer,
    resample,
)


def tone(n: int, amp: int = 8000) -> np.ndarray:
    return (amp * np.sin(np.arange(n) / 5)).astype(np.int16)


async def take(renderer, n):
    out = []
    async for item in renderer.frames():
        out.append(item)
        if len(out) >= n:
            break
    return out


def test_fifo_exact_chunks_and_segment_end_padding():
    fifo = AudioFifo()
    assert fifo.take(10) == (None, False)
    fifo.push(np.ones(15, np.int16))
    chunk, ended = fifo.take(10)
    assert len(chunk) == 10 and not ended
    assert fifo.take(10) == (None, False)  # 5 sampel belum cukup, belum ada akhir
    fifo.end()
    chunk, ended = fifo.take(10)
    assert ended and len(chunk) == 10
    assert chunk[:5].tolist() == [1] * 5 and chunk[5:].tolist() == [0] * 5


def test_fifo_end_on_boundary_and_clear():
    fifo = AudioFifo()
    fifo.push(np.ones(10, np.int16))
    fifo.end()
    assert fifo.take(10)[1] is False
    assert fifo.take(10) == (None, True)
    fifo.push(np.ones(30, np.int16))
    fifo.clear()
    assert fifo.take(10) == (None, False)


def test_resample_length():
    assert len(resample(np.zeros(2400, np.int16), 24000, 16000)) == 1600
    assert resample(np.zeros(5, np.int16), 16000, 16000).dtype == np.int16


def test_static_idle_frames_without_photo():
    async def run():
        r = StaticRenderer()
        await r.start(None)  # siluet placeholder
        frames = await take(r, 3)
        await r.aclose()
        return frames

    frames = asyncio.run(run())
    assert all(isinstance(f, RenderedFrame) and f.audio is None for f in frames)
    assert frames[0].image.shape == (HEIGHT, WIDTH, 3)
    assert frames[0].image.dtype == np.uint8


def test_static_speech_frames_pair_audio_then_segment_end(tmp_path):
    photo = tmp_path / "foto.png"
    Image.new("RGB", (640, 480), (200, 150, 120)).save(photo)

    async def run():
        r = StaticRenderer()
        await r.start(photo)
        idle = r.idle_image.copy()
        await r.push_audio(tone(int(SAMPLES_PER_FRAME * 2.5)))
        await r.end_segment()
        frames = await take(r, 5)
        await r.aclose()
        return idle, frames

    idle, frames = asyncio.run(run())
    speech = [f for f in frames[:3]]
    assert all(isinstance(f, RenderedFrame) and len(f.audio) == SAMPLES_PER_FRAME for f in speech)
    assert frames[3] is SEGMENT_END
    assert frames[4].audio is None  # kembali diam
    # indikator bicara terlihat: frame bicara berbeda dari frame diam
    assert not np.array_equal(speech[0].image, idle)
    # sisa setengah frame dipad hening, total audio utuh tidak hilang
    total = np.concatenate([f.audio for f in speech])
    assert np.count_nonzero(total[int(SAMPLES_PER_FRAME * 2.5) :]) == 0


def test_static_clear_drops_pending_audio():
    async def run():
        r = StaticRenderer()
        await r.start(None)
        await r.push_audio(tone(SAMPLES_PER_FRAME * 10))
        r.clear()
        frames = await take(r, 2)
        await r.aclose()
        return frames

    assert all(f.audio is None for f in asyncio.run(run()))


def test_frames_stop_after_aclose():
    async def run():
        r = StaticRenderer()
        await r.start(None)
        await r.aclose()
        return [f async for f in r.frames()]

    assert asyncio.run(run()) == []


def test_flashhead_requires_photo():
    async def run():
        await FlashHeadRenderer("ws://127.0.0.1:1/stream").start(None)

    with pytest.raises(RendererUnavailable):
        asyncio.run(run())


def test_make_renderer_flag():
    assert isinstance(make_renderer({}), StaticRenderer)
    assert isinstance(make_renderer({"AVATAR_RENDERER": "flashhead"}), FlashHeadRenderer)
    assert isinstance(make_renderer({"AVATAR_RENDERER": "aneh"}), StaticRenderer)
    assert isinstance(SEGMENT_END, SegmentEnd)
