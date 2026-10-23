"""Logika kapasitas (AVATAR_MAX_SESSIONS) dan endpoint worker."""

import asyncio

import numpy as np
from aiohttp.test_utils import TestClient, TestServer
from capacity import SessionSlots
from livekit import rtc
from livekit.agents.voice.avatar import AudioSegmentEnd
from renderers import SAMPLES_PER_FRAME, RendererUnavailable, StaticRenderer
from server import AVATAR_IDENTITY, AvatarService, WorkerSettings, create_app, sign
from video_gen import RendererVideoGenerator

SETTINGS = WorkerSettings(livekit_url="ws://x", api_key="k", api_secret="rahasia", max_sessions=1)


def test_slots_full_then_released():
    slots = SessionSlots(2)
    assert slots.try_acquire("a") and slots.try_acquire("b")
    assert not slots.try_acquire("c")
    assert slots.try_acquire("a")  # room yang sama tidak memakan slot baru
    slots.release("a")
    assert slots.try_acquire("c")
    assert SessionSlots(0).try_acquire("x") is False


class FailingRenderer(StaticRenderer):
    async def start(self, reference_image):
        raise RendererUnavailable("GPU mati")


def make_service(renderer_cls=StaticRenderer):
    service = AvatarService(SETTINGS, renderer_factory=renderer_cls)
    ended = {}

    async def fake_run(room, agent_identity, renderer):
        ended[room] = asyncio.Event()
        try:
            await ended[room].wait()
        finally:
            await renderer.aclose()
            service.slots.release(room)

    service._run = fake_run  # tanpa server LiveKit
    return service, ended


def test_service_full_returns_503_and_frees_slot_after_session():
    async def run():
        service, ended = make_service()
        assert (await service.start_session("r1", "agent"))[0] == 201
        status, body = await service.start_session("r2", "agent")
        assert status == 503 and "penuh" in body["detail"]
        await asyncio.sleep(0)  # beri giliran task sesi r1 untuk mulai
        ended["r1"].set()
        await asyncio.sleep(0.01)
        assert service.slots.active == 0
        assert (await service.start_session("r2", "agent"))[0] == 201
        await service.stop_session("r2")

    asyncio.run(run())


def test_renderer_failure_returns_503_without_leaking_slot():
    async def run():
        service, _ = make_service(FailingRenderer)
        status, body = await service.start_session("r1", "agent")
        assert status == 503 and "GPU mati" in body["detail"]
        assert service.slots.active == 0

    asyncio.run(run())


def test_http_signature_and_identity():
    async def run():
        service, _ = make_service()
        async with TestClient(TestServer(create_app(service))) as client:
            body = {"room": "r1", "agent_identity": "agent"}
            resp = await client.post("/sessions", json=body)
            assert resp.status == 401
            resp = await client.post(
                "/sessions", json=body, headers={"X-Avatar-Signature": sign("rahasia", "r1")}
            )
            assert resp.status == 201
            assert (await resp.json())["identity"] == AVATAR_IDENTITY
            health = await (await client.get("/health")).json()
            assert health["active"] == 1 and health["max_sessions"] == 1
            resp = await client.delete(
                "/sessions/r1", headers={"X-Avatar-Signature": sign("rahasia", "r1")}
            )
            assert resp.status == 204
            assert service.slots.active == 0

    asyncio.run(run())


def test_video_generator_maps_to_livekit_frames():
    async def run():
        renderer = StaticRenderer()
        await renderer.start(None)
        gen = RendererVideoGenerator(renderer)
        pcm = np.full(SAMPLES_PER_FRAME, 3000, np.int16)
        await gen.push_audio(
            rtc.AudioFrame(
                data=pcm.tobytes(),
                sample_rate=24000,
                num_channels=1,
                samples_per_channel=SAMPLES_PER_FRAME,
            )
        )
        await gen.push_audio(AudioSegmentEnd())
        out = []
        async for item in gen:
            out.append(item)
            if isinstance(item, AudioSegmentEnd):
                break
        await renderer.aclose()
        return out

    out = asyncio.run(run())
    assert isinstance(out[0], rtc.VideoFrame) and out[0].width == 512
    assert isinstance(out[1], rtc.AudioFrame) and out[1].samples_per_channel == SAMPLES_PER_FRAME
    assert isinstance(out[2], AudioSegmentEnd)
