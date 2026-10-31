"""Tes avatar video PoC di sisi agent: flag, keputusan fallback ke
voice-only, dan titik tukar sink audio LiveKit untuk fallback di tengah sesi.
Jalan tanpa server LiveKit: `python -m pytest agent/tests`."""

import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from avatar_fallback import (  # noqa: E402
    AVATAR_IDENTITY,
    SIGNATURE_HEADER,
    AvatarSettings,
    fetch_reference_image,
    parse_provider,
    release_avatar,
    request_avatar,
    sign,
    wait_ready,
)

SETTINGS = AvatarSettings(provider="self", worker_url="http://avatar-worker:8090")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _request(handler):
    async with _client(handler) as http:
        return await request_avatar(
            http, SETTINGS, room="ai-interview-1", agent_identity="agent-1", secret="rahasia"
        )


def test_provider_default_none_and_unknown_falls_back():
    assert parse_provider(None) == "none"
    assert parse_provider("") == "none"
    assert parse_provider(" SELF ") == "self"
    # Tavus belum ada di repo -> nilai itu tidak boleh diam-diam dianggap aktif.
    assert parse_provider("tavus") == "none"


def test_settings_from_env():
    s = AvatarSettings.from_env({"AVATAR_PROVIDER": "self", "AVATAR_JOIN_TIMEOUT": "abc"})
    assert s.enabled
    assert s.worker_url == "http://avatar-worker:8090"
    assert s.join_timeout == 15.0  # nilai rusak -> default, bukan crash
    assert not AvatarSettings.from_env({}).enabled
    assert AvatarSettings.from_env({}).candidate_timeout == 120.0
    assert AvatarSettings.from_env({"AVATAR_CANDIDATE_TIMEOUT": "30"}).candidate_timeout == 30.0


def test_request_signed_and_accepted():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["sig"] = request.headers[SIGNATURE_HEADER]
        seen["body"] = request.content
        return httpx.Response(201, json={"identity": "ai-interview-avatar"})

    decision = asyncio.run(_request(handler))
    assert decision.enabled and decision.identity == AVATAR_IDENTITY
    assert seen["sig"] == sign("rahasia", "ai-interview-1")
    assert b'"agent_identity":"agent-1"' in seen["body"].replace(b" ", b"")


def test_request_without_reference_image_omits_field():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"identity": AVATAR_IDENTITY})

    asyncio.run(_request(handler))
    assert "reference_image_b64" not in seen["body"]


def test_request_sends_reference_image_b64():
    seen = {}
    photo = b"\xff\xd8\xff\xe0 foto-tenant \x00\x01"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["sig"] = request.headers[SIGNATURE_HEADER]
        return httpx.Response(201, json={"identity": AVATAR_IDENTITY})

    async def run():
        async with _client(handler) as http:
            return await request_avatar(
                http,
                SETTINGS,
                room="ai-interview-1",
                agent_identity="agent-1",
                secret="rahasia",
                reference_image=photo,
            )

    assert asyncio.run(run()).enabled
    assert base64.b64decode(seen["body"]["reference_image_b64"]) == photo
    # Tanda tangan tetap atas nama room saja.
    assert seen["sig"] == sign("rahasia", "ai-interview-1")


async def _fetch(handler):
    async with _client(handler) as http:
        return await fetch_reference_image(
            http, "http://backend/x/voice/avatar-image", headers={"X-Agent-Signature": "sig"}
        )


def test_fetch_reference_image_ok_sends_signature():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["sig"] = request.headers.get("X-Agent-Signature")
        return httpx.Response(200, content=b"jpeg-bytes")

    assert asyncio.run(_fetch(handler)) == b"jpeg-bytes"
    assert seen["sig"] == "sig"


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(404, json={"detail": "belum ada"}),
        lambda r: httpx.Response(500, text="boom"),
        lambda r: httpx.Response(401, json={"detail": "salah"}),
        lambda r: httpx.Response(200, content=b""),
    ],
)
def test_fetch_reference_image_failure_is_none(handler):
    assert asyncio.run(_fetch(handler)) is None


@pytest.mark.parametrize("exc", [httpx.ConnectError, httpx.ReadTimeout])
def test_fetch_reference_image_network_error_is_none(exc):
    def handler(request):
        raise exc("gagal", request=request)

    assert asyncio.run(_fetch(handler)) is None


@pytest.mark.parametrize(
    ("handler", "reason_part"),
    [
        (lambda r: httpx.Response(503, json={"detail": "kapasitas penuh"}), "kapasitas penuh"),
        (lambda r: httpx.Response(500, text="boom"), "HTTP 500"),
    ],
)
def test_worker_refusal_means_voice_only(handler, reason_part):
    decision = asyncio.run(_request(handler))
    assert not decision.enabled
    assert reason_part in decision.reason


def test_unreachable_worker_means_voice_only():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    decision = asyncio.run(_request(handler))
    assert not decision.enabled
    assert "tidak terjangkau" in decision.reason


def test_release_never_raises():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    async def run():
        async with _client(handler) as http:
            await release_avatar(http, SETTINGS, room="r", secret="s")

    asyncio.run(run())


def test_wait_ready_timeout_and_error_are_false():
    async def never():
        await asyncio.sleep(10)

    async def boom():
        raise RuntimeError("x")

    async def ok():
        return None

    assert asyncio.run(wait_ready(never(), 0.05)) is False
    assert asyncio.run(wait_ready(boom(), 1)) is False
    assert asyncio.run(wait_ready(ok(), 1)) is True


# ---- titik tukar sink LiveKit (kelas privat, dikunci ke 1.7.1) ----

livekit_agents = pytest.importorskip("livekit.agents")


def _leaf_class():
    from livekit.agents.voice.io import AudioOutput, AudioOutputCapabilities

    class Leaf(AudioOutput):
        def __init__(self, label: str) -> None:
            super().__init__(label=label, capabilities=AudioOutputCapabilities(pause=False))
            self.cleared = 0

        async def capture_frame(self, frame) -> None:
            await super().capture_frame(frame)

        def flush(self) -> None:
            super().flush()

        def clear_buffer(self) -> None:
            self.cleared += 1

    return Leaf


def test_private_livekit_classes_still_exist():
    """Fallback di tengah sesi bergantung pada keduanya -- upgrade
    livekit-agents yang menghapusnya harus gagal di sini, bukan di produksi."""
    from livekit.agents.voice.io import _AudioSinkProxy  # noqa: F401
    from livekit.agents.voice.room_io._output import _ParticipantAudioOutput  # noqa: F401


def test_find_proxy_and_swap_finishes_pending_segment():
    from avatar import find_sink_proxy
    from livekit import rtc

    leaf_cls = _leaf_class()
    avatar_sink, room_sink = leaf_cls("avatar"), leaf_cls("room")

    async def run():
        # Wrapper (spt perekam/sinkronisasi transkrip) membungkus sink daun:
        # LiveKit otomatis menyisipkan _AudioSinkProxy di antaranya.
        from livekit.agents.voice.io import AudioOutput, AudioOutputCapabilities

        class Wrapper(AudioOutput):
            async def capture_frame(self, frame) -> None:
                await super().capture_frame(frame)
                await self.next_in_chain.capture_frame(frame)

            def flush(self) -> None:
                super().flush()
                self.next_in_chain.flush()

            def clear_buffer(self) -> None:
                self.next_in_chain.clear_buffer()

        top = Wrapper(
            label="top",
            capabilities=AudioOutputCapabilities(pause=False),
            next_in_chain=avatar_sink,
        )
        proxy = find_sink_proxy(top)
        assert proxy is not None and proxy.next_in_chain is avatar_sink

        frame = rtc.AudioFrame(
            data=b"\x00\x00" * 240, sample_rate=24000, num_channels=1, samples_per_channel=240
        )
        await top.capture_frame(frame)
        top.flush()  # segmen terkirim ke avatar, belum dilaporkan selesai

        proxy.set_next_in_chain(room_sink)
        assert proxy.next_in_chain is room_sink
        assert avatar_sink.cleared == 1
        # Segmen yatim ditandai selesai (terputus) -> agen tidak menggantung.
        ev = await asyncio.wait_for(top.wait_for_playout(), 1)
        assert ev.interrupted

    asyncio.run(run())


def test_find_proxy_none_without_chain():
    from avatar import find_sink_proxy

    assert find_sink_proxy(None) is None
    assert find_sink_proxy(_leaf_class()("solo")) is None
