"""Renderer avatar yang bisa ditukar (AVATAR_RENDERER=static|flashhead).

Satu interface, `AvatarRenderer`: `start(reference_image)` -> `push_audio(pcm)`
/ `end_segment()` -> `frames()`. Renderer yang menentukan pasangan audio-video:
tiap `RenderedFrame` membawa satu frame video dan potongan audio TTS yang
harus diputar bersamaannya (None = frame diam). `AvatarRunner` LiveKit yang
mengatur laju (fps) dan sinkronisasi pemutaran -- renderer tidak perlu tidur.

- `StaticRenderer`: foto statis + cincin indikator bicara (dari RMS audio),
  murni CPU. Untuk menguji wiring end-to-end di mesin tanpa GPU.
- `FlashHeadRenderer`: klien WebSocket ke `flashhead-server` (SoulX-FlashHead
  di server GPU terpisah). Bila server putus/lambat, renderer TURUN ke
  StaticRenderer di tengah sesi -- audio tetap sampai ke kandidat, hanya
  wajah yang berhenti bergerak. Tanpa ini, agen menunggu laporan selesai
  putar yang tidak pernah datang dan sesi menggantung.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger("avatar-worker.renderer")

FPS = 25
WIDTH = HEIGHT = 512  # resolusi keluaran SoulX-FlashHead (infer_params.yaml)
SAMPLE_RATE = 24000  # audio TTS dari agen (DataStreamAudioOutput)
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS  # 960 sampel = 40 ms per frame video

# Label tetap di video: avatar TIDAK boleh tampil seolah manusia.
AVATAR_LABEL = "Pewawancara AI - avatar, bukan orang sungguhan"


@dataclass
class RenderedFrame:
    image: np.ndarray  # (HEIGHT, WIDTH, 3) uint8 RGB
    audio: np.ndarray | None  # int16 mono SAMPLES_PER_FRAME sampel; None = diam


class SegmentEnd:
    """Akhir satu ucapan agen (dipetakan ke AudioSegmentEnd LiveKit)."""


SEGMENT_END = SegmentEnd()


class RendererUnavailable(RuntimeError):
    """Renderer tidak bisa dipakai untuk sesi ini (worker menjawab 503 ->
    agen jalan voice-only)."""


class AvatarRenderer(ABC):
    width = WIDTH
    height = HEIGHT
    fps = FPS
    sample_rate = SAMPLE_RATE

    @abstractmethod
    async def start(self, reference_image: Path | None) -> None:
        """Siapkan renderer untuk satu sesi. Raise RendererUnavailable bila gagal."""

    @abstractmethod
    async def push_audio(self, pcm: np.ndarray) -> None:
        """Audio TTS int16 mono SAMPLE_RATE, boleh lebih cepat dari real-time."""

    @abstractmethod
    async def end_segment(self) -> None:
        """Ucapan saat ini selesai (setelah audio terakhirnya didorong)."""

    @abstractmethod
    def clear(self) -> None:
        """Kandidat memotong: buang audio yang belum diputar."""

    @abstractmethod
    def frames(self) -> AsyncIterator[RenderedFrame | SegmentEnd]:
        """Aliran frame tanpa akhir sampai aclose(); frame diam saat tidak bicara."""

    async def aclose(self) -> None:  # noqa: B027 - opsional untuk subclass
        pass


class AudioFifo:
    """Antrean audio + penanda akhir segmen, diambil per potongan tetap."""

    def __init__(self) -> None:
        self._items: deque[np.ndarray | SegmentEnd] = deque()

    def push(self, pcm: np.ndarray) -> None:
        if len(pcm):
            self._items.append(np.asarray(pcm, dtype=np.int16))

    def end(self) -> None:
        self._items.append(SEGMENT_END)

    def clear(self) -> None:
        self._items.clear()

    def drain(self) -> list[np.ndarray | SegmentEnd]:
        items = list(self._items)
        self._items.clear()
        return items

    def take(self, n: int) -> tuple[np.ndarray | None, bool]:
        """Ambil tepat `n` sampel. Bila penanda akhir segmen datang lebih dulu,
        sisa audio dipad hening dan `ended=True`. (None, False) = belum cukup."""
        avail, end_seen = 0, False
        for item in self._items:
            if isinstance(item, SegmentEnd):
                end_seen = True
                break
            avail += len(item)
            if avail >= n:
                break
        if avail < n and not end_seen:
            return None, False

        parts: list[np.ndarray] = []
        count = 0
        while count < n and self._items and not isinstance(self._items[0], SegmentEnd):
            item = self._items[0]
            need = n - count
            if len(item) <= need:
                parts.append(item)
                count += len(item)
                self._items.popleft()
            else:
                parts.append(item[:need])
                self._items[0] = item[need:]
                count += need
        if count == n:
            return np.concatenate(parts), False
        self._items.popleft()  # penanda akhir segmen
        if count == 0:
            return None, True
        parts.append(np.zeros(n - count, dtype=np.int16))
        return np.concatenate(parts), True


def resample(pcm: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample linear sederhana (cukup untuk fitur wav2vec & indikator)."""
    if src_rate == dst_rate or not len(pcm):
        return pcm.astype(np.int16, copy=False)
    n_out = int(round(len(pcm) * dst_rate / src_rate))
    x_old = np.arange(len(pcm), dtype=np.float64)
    x_new = np.arange(n_out, dtype=np.float64) * (src_rate / dst_rate)
    return np.interp(x_new, x_old, pcm.astype(np.float64)).astype(np.int16)


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow lama tanpa parameter size
        return ImageFont.load_default()


def load_portrait(reference_image: Path | None) -> np.ndarray:
    """Foto referensi dipotong persegi WIDTHxHEIGHT + label avatar. Tanpa foto:
    siluet netral (cukup untuk uji wiring; FlashHead tetap butuh foto)."""
    if reference_image is not None and reference_image.is_file():
        img = ImageOps.fit(Image.open(reference_image).convert("RGB"), (WIDTH, HEIGHT))
    else:
        img = Image.new("RGB", (WIDTH, HEIGHT), (30, 41, 59))
        draw = ImageDraw.Draw(img)
        draw.ellipse((176, 110, 336, 270), fill=(100, 116, 139))
        draw.ellipse((96, 290, 416, 610), fill=(100, 116, 139))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((0, HEIGHT - 36, WIDTH, HEIGHT), fill=(0, 0, 0, 170))
    draw.text((12, HEIGHT - 28), AVATAR_LABEL, fill=(255, 255, 255), font=_font(16))
    return np.asarray(img, dtype=np.uint8).copy()


def _ring_mask(thickness: int = 10) -> np.ndarray:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    edge = np.minimum.reduce([yy, xx, HEIGHT - 1 - yy, WIDTH - 1 - xx])
    return (edge < thickness).astype(np.float32)[..., None]


class StaticRenderer(AvatarRenderer):
    # Warna cincin = --accent tema gelap (frontend/src/index.css).
    RING_COLOR = np.array([93, 202, 165], dtype=np.float32)

    def __init__(self) -> None:
        self._fifo = AudioFifo()
        self._closed = False
        self._level = 0.0
        self._base: np.ndarray | None = None
        self._ring = _ring_mask()

    async def start(self, reference_image: Path | None) -> None:
        self._base = load_portrait(reference_image)

    @property
    def idle_image(self) -> np.ndarray:
        assert self._base is not None, "start() belum dipanggil"
        return self._base

    async def push_audio(self, pcm: np.ndarray) -> None:
        self._fifo.push(pcm)

    async def end_segment(self) -> None:
        self._fifo.end()

    def clear(self) -> None:
        self._fifo.clear()
        self._level = 0.0

    def _compose(self, chunk: np.ndarray) -> np.ndarray:
        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        self._level = 0.6 * self._level + 0.4 * min(1.0, rms / 3000.0)
        alpha = self._ring * (0.35 + 0.65 * self._level)
        out = self.idle_image * (1 - alpha) + self.RING_COLOR * alpha
        return out.astype(np.uint8)

    async def frames(self) -> AsyncIterator[RenderedFrame | SegmentEnd]:
        while not self._closed:
            chunk, ended = self._fifo.take(SAMPLES_PER_FRAME)
            if chunk is not None:
                yield RenderedFrame(self._compose(chunk), chunk)
            if ended:
                self._level = 0.0
                yield SEGMENT_END
            if chunk is None and not ended:
                yield RenderedFrame(self.idle_image, None)
            await asyncio.sleep(0)

    async def aclose(self) -> None:
        self._closed = True


@dataclass
class _Pending:
    audio: np.ndarray  # audio 24 kHz yang dipasangkan dengan frame hasil chunk ini
    sent_at: float
    generation: int


class FlashHeadRenderer(AvatarRenderer):
    """Klien `flashhead-server` (protokol: lihat flashhead-server/server.py).

    Audio dikirim per potongan `slice_frames` frame (28 frame = 1,12 dtk,
    dari parameter resmi frame_num=33 dikurangi motion frames) -- itulah
    latensi minimum bawaan model sebelum wajah mulai bicara. Saat diam,
    frame terakhir diulang (tidak ada inferensi idle -> GPU hanya bekerja
    saat agen bicara; konsekuensinya wajah diam membeku)."""

    def __init__(
        self,
        url: str,
        *,
        ready_timeout: float = 60.0,
        chunk_timeout: float = 5.0,
        max_backlog: int = 3,
        seed: int = 9999,
    ) -> None:
        self._url = url
        self._ready_timeout = ready_timeout
        self._chunk_timeout = chunk_timeout
        self._max_backlog = max_backlog
        self._seed = seed
        self._fifo = AudioFifo()
        self._inflight: deque[_Pending | SegmentEnd] = deque()
        self._out: deque[RenderedFrame | SegmentEnd] = deque()
        self._fallback = StaticRenderer()
        self._degraded = False
        self._closed = False
        self._generation = 0
        self._slice_frames = 28
        self._last: np.ndarray | None = None
        self._http: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reader: asyncio.Task[None] | None = None
        self._send_lock = asyncio.Lock()
        self._bg: set[asyncio.Task[None]] = set()

    @property
    def degraded(self) -> bool:
        return self._degraded

    async def start(self, reference_image: Path | None) -> None:
        if reference_image is None or not reference_image.is_file():
            raise RendererUnavailable("FlashHead butuh foto referensi (AVATAR_REFERENCE_IMAGE)")
        await self._fallback.start(reference_image)
        self._http = aiohttp.ClientSession()
        try:
            self._ws = await self._http.ws_connect(self._url, heartbeat=20, max_msg_size=0)
            await self._ws.send_json(
                {
                    "type": "start",
                    "image": base64.b64encode(reference_image.read_bytes()).decode(),
                    "seed": self._seed,
                }
            )
            msg = await asyncio.wait_for(self._ws.receive(), self._ready_timeout)
            data = json.loads(msg.data) if msg.type == aiohttp.WSMsgType.TEXT else {}
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            await self._close_transport()
            raise RendererUnavailable(f"flashhead-server tidak siap: {exc!r}") from exc
        if data.get("type") != "ready":
            await self._close_transport()
            raise RendererUnavailable(f"flashhead-server menolak: {data.get('detail') or data}")
        self._slice_frames = int(data.get("slice_frames") or self._slice_frames)
        self._reader = asyncio.create_task(self._read_loop())

    async def push_audio(self, pcm: np.ndarray) -> None:
        if self._degraded:
            await self._fallback.push_audio(pcm)
            return
        self._fifo.push(pcm)
        await self._send_ready_blocks()

    async def end_segment(self) -> None:
        if self._degraded:
            await self._fallback.end_segment()
            return
        self._fifo.end()
        await self._send_ready_blocks()

    async def _send_ready_blocks(self) -> None:
        n = self._slice_frames * SAMPLES_PER_FRAME
        async with self._send_lock:
            while not self._degraded:
                block, ended = self._fifo.take(n)
                if block is not None:
                    pending = sum(isinstance(p, _Pending) for p in self._inflight)
                    if pending >= self._max_backlog:
                        # GPU tidak mengejar real-time (mis. varian Pro di 1x 4090).
                        self._fifo_prepend(block, ended)
                        await self._degrade("antrean GPU tertinggal dari real-time")
                        return
                    self._inflight.append(_Pending(block, time.monotonic(), self._generation))
                    try:
                        assert self._ws is not None
                        await self._ws.send_bytes(resample(block, SAMPLE_RATE, 16000).tobytes())
                    except (aiohttp.ClientError, ConnectionError, RuntimeError):
                        if ended:
                            self._inflight.append(SEGMENT_END)
                        await self._degrade("gagal mengirim audio ke flashhead-server")
                        return
                if ended:
                    self._inflight.append(SEGMENT_END)
                    self._drain_ends()
                if block is None and not ended:
                    return

    def _fifo_prepend(self, block: np.ndarray, ended: bool) -> None:
        rest = self._fifo.drain()
        self._fifo.push(block)
        if ended:
            self._fifo.end()
        for item in rest:
            if isinstance(item, SegmentEnd):
                self._fifo.end()
            else:
                self._fifo.push(item)

    def _drain_ends(self) -> None:
        while self._inflight and isinstance(self._inflight[0], SegmentEnd):
            self._inflight.popleft()
            self._out.append(SEGMENT_END)

    async def _read_loop(self) -> None:
        assert self._ws is not None
        frames: list[np.ndarray] = []
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    frames.append(_decode_jpeg(msg.data))
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "chunk_done":
                        self._on_chunk(frames)
                        frames = []
                    elif data.get("type") == "error":
                        logger.warning("flashhead-server error: %s", data.get("detail"))
                        break
                else:
                    break
        except Exception:  # noqa: BLE001
            logger.warning("Koneksi flashhead-server bermasalah", exc_info=True)
        if not self._closed:
            await self._degrade("koneksi flashhead-server putus")

    def _on_chunk(self, frames: list[np.ndarray]) -> None:
        self._drain_ends()
        if not self._inflight:
            return
        pending = self._inflight.popleft()
        assert isinstance(pending, _Pending)
        if pending.generation == self._generation and frames:
            for i in range(self._slice_frames):
                audio = pending.audio[i * SAMPLES_PER_FRAME : (i + 1) * SAMPLES_PER_FRAME]
                self._out.append(RenderedFrame(frames[min(i, len(frames) - 1)], audio))
            self._last = frames[-1]
        self._drain_ends()

    async def _degrade(self, reason: str) -> None:
        if self._degraded or self._closed:
            return
        self._degraded = True
        logger.warning("FlashHead turun ke StaticRenderer: %s", reason)
        # Audio yang belum jadi frame dipindah ke StaticRenderer, urutan dijaga.
        for item in list(self._inflight):
            if isinstance(item, SegmentEnd):
                await self._fallback.end_segment()
            elif item.generation == self._generation:
                await self._fallback.push_audio(item.audio)
        self._inflight.clear()
        for item in self._fifo.drain():
            if isinstance(item, SegmentEnd):
                await self._fallback.end_segment()
            else:
                await self._fallback.push_audio(item)
        await self._close_transport()

    def clear(self) -> None:
        self._generation += 1
        self._fifo.clear()
        self._out.clear()
        # Chunk yang sedang diproses GPU tetap dihitung (urutan balasan), tapi
        # hasilnya dibuang karena generasinya sudah lewat.
        self._inflight = deque(p for p in self._inflight if isinstance(p, _Pending))
        self._fallback.clear()
        if not self._degraded and self._ws is not None and not self._ws.closed:
            # Server mengosongkan konteks audio 8 dtk-nya: ucapan berikutnya
            # tidak dianimasikan dengan sisa ucapan yang dipotong.
            task = asyncio.create_task(self._send_reset())
            self._bg.add(task)
            task.add_done_callback(self._bg.discard)

    async def _send_reset(self) -> None:
        async with self._send_lock:
            try:
                assert self._ws is not None
                await self._ws.send_json({"type": "reset"})
            except (aiohttp.ClientError, ConnectionError, RuntimeError):
                pass  # putus -> _read_loop yang menurunkan ke StaticRenderer

    async def frames(self) -> AsyncIterator[RenderedFrame | SegmentEnd]:
        while not self._closed:
            if self._out:
                yield self._out.popleft()
                continue
            if self._degraded:
                async for item in self._fallback.frames():
                    yield item
                return
            head = next((p for p in self._inflight if isinstance(p, _Pending)), None)
            if head is not None and time.monotonic() - head.sent_at > self._chunk_timeout:
                await self._degrade(f"chunk lebih dari {self._chunk_timeout:.0f} dtk")
                continue
            yield RenderedFrame(
                self._last if self._last is not None else self._fallback.idle_image, None
            )
            await asyncio.sleep(0)

    async def _close_transport(self) -> None:
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._http is not None and not self._http.closed:
            await self._http.close()

    async def aclose(self) -> None:
        self._closed = True
        if self._reader is not None:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self._close_transport()
        await self._fallback.aclose()


def _decode_jpeg(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if img.size != (WIDTH, HEIGHT):
        img = img.resize((WIDTH, HEIGHT))
    return np.asarray(img, dtype=np.uint8).copy()


def make_renderer(env: Mapping[str, str] = os.environ) -> AvatarRenderer:
    kind = (env.get("AVATAR_RENDERER") or "static").strip().lower()
    if kind == "flashhead":
        return FlashHeadRenderer(
            env.get("FLASHHEAD_URL") or "ws://flashhead-server:8010/stream",
            ready_timeout=float(env.get("FLASHHEAD_READY_TIMEOUT") or 60),
            chunk_timeout=float(env.get("FLASHHEAD_CHUNK_TIMEOUT") or 5),
            max_backlog=int(env.get("FLASHHEAD_MAX_BACKLOG") or 3),
        )
    if kind != "static":
        logger.warning("AVATAR_RENDERER=%r tidak dikenal -- dipakai 'static'", kind)
    return StaticRenderer()
