"""Adapter AvatarRenderer -> `VideoGenerator` LiveKit Agents 1.7.1.

`AvatarRunner` memanggil `push_audio(frame | AudioSegmentEnd)`,
`clear_buffer()`, dan membaca `async for` berisi VideoFrame, AudioFrame, atau
AudioSegmentEnd (kontrak di `livekit/agents/voice/avatar/_types.py`). Urutan
yang dikirim: video lalu audio pasangannya, sehingga AVSynchronizer menjaga
keduanya sejalan pada fps renderer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import numpy as np
from livekit import rtc
from livekit.agents.voice.avatar import AudioSegmentEnd, VideoGenerator
from renderers import AvatarRenderer, SegmentEnd, resample


def to_video_frame(image: np.ndarray) -> rtc.VideoFrame:
    h, w = image.shape[:2]
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = image
    rgba[..., 3] = 255
    return rtc.VideoFrame(w, h, rtc.VideoBufferType.RGBA, rgba.tobytes())


def to_pcm(frame: rtc.AudioFrame, target_rate: int) -> np.ndarray:
    pcm = np.frombuffer(bytes(frame.data), dtype=np.int16)
    if frame.num_channels > 1:
        pcm = pcm.reshape(-1, frame.num_channels).mean(axis=1).astype(np.int16)
    return resample(pcm, frame.sample_rate, target_rate)


class RendererVideoGenerator(VideoGenerator):
    def __init__(self, renderer: AvatarRenderer) -> None:
        self._renderer = renderer

    async def push_audio(self, frame: rtc.AudioFrame | AudioSegmentEnd) -> None:
        if isinstance(frame, AudioSegmentEnd):
            await self._renderer.end_segment()
            return
        await self._renderer.push_audio(to_pcm(frame, self._renderer.sample_rate))

    def clear_buffer(self) -> None:
        self._renderer.clear()

    def __aiter__(self) -> AsyncIterator[rtc.VideoFrame | rtc.AudioFrame | AudioSegmentEnd]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[rtc.VideoFrame | rtc.AudioFrame | AudioSegmentEnd]:
        rate = self._renderer.sample_rate
        async for item in self._renderer.frames():
            if isinstance(item, SegmentEnd):
                yield AudioSegmentEnd()
                continue
            yield to_video_frame(item.image)
            if item.audio is not None:
                yield rtc.AudioFrame(
                    data=item.audio.tobytes(),
                    sample_rate=rate,
                    num_channels=1,
                    samples_per_channel=len(item.audio),
                )
