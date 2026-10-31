"""Foto avatar per tenant: agen mengirim `reference_image_b64`, worker
menulisnya ke file sementara untuk renderer dan menghapusnya di semua jalur
(sesi selesai, dibatalkan, start gagal). Tanpa/rusak -> foto env."""

import asyncio
import base64
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer
from renderers import RendererUnavailable, StaticRenderer
from server import (
    AvatarService,
    WorkerSettings,
    create_app,
    decode_reference_image,
    sign,
)

ENV_IMAGE = Path("/foto/bawaan-env.jpg")
SETTINGS = WorkerSettings(
    livekit_url="ws://x",
    api_key="k",
    api_secret="rahasia",
    max_sessions=1,
    reference_image=ENV_IMAGE,
)
PHOTO = b"\xff\xd8\xff\xe0" + b"foto-tenant" * 50


class RecordingRenderer(StaticRenderer):
    """Mencatat path yang diterima & isi file saat start."""

    seen: list[tuple[Path | None, bytes | None]] = []
    fail = False

    async def start(self, reference_image):
        content = None
        if reference_image is not None and reference_image.is_file():
            content = reference_image.read_bytes()
        RecordingRenderer.seen.append((reference_image, content))
        if RecordingRenderer.fail:
            raise RendererUnavailable("GPU mati")
        await super().start(None)


def make_service():
    RecordingRenderer.seen = []
    RecordingRenderer.fail = False
    service = AvatarService(SETTINGS, renderer_factory=RecordingRenderer)
    ended: dict[str, asyncio.Event] = {}

    async def fake_run(room, agent_identity, renderer):
        ended[room] = asyncio.Event()
        try:
            await ended[room].wait()
        finally:
            await renderer.aclose()
            service.slots.release(room)

    service._run = fake_run  # tanpa server LiveKit
    return service, ended


def test_decode_reference_image():
    assert decode_reference_image(None) is None
    assert decode_reference_image("") is None
    assert decode_reference_image(123) is None
    assert decode_reference_image("bukan base64!!") is None
    assert decode_reference_image(base64.b64encode(PHOTO).decode()) == PHOTO
    too_big = base64.b64encode(b"\x00" * (6 * 1024 * 1024 + 10)).decode()
    assert decode_reference_image(too_big) is None


def test_temp_file_passed_to_renderer_and_removed_after_session():
    async def run():
        service, ended = make_service()
        status, _ = await service.start_session("r1", "agent", PHOTO)
        assert status == 201
        path, content = RecordingRenderer.seen[0]
        assert path != ENV_IMAGE and content == PHOTO
        assert path.exists()  # masih dipakai selama sesi
        await asyncio.sleep(0)
        ended["r1"].set()
        await asyncio.sleep(0.01)
        assert not path.exists()
        assert service.slots.active == 0

    asyncio.run(run())


def test_temp_file_removed_when_session_cancelled():
    async def run():
        service, _ = make_service()
        assert (await service.start_session("r1", "agent", PHOTO))[0] == 201
        path = RecordingRenderer.seen[0][0]
        await service.release_session("r1")
        assert not path.exists()

    asyncio.run(run())


def test_temp_file_removed_when_cancelled_before_task_starts():
    async def run():
        service, _ = make_service()
        assert (await service.start_session("r1", "agent", PHOTO))[0] == 201
        path = RecordingRenderer.seen[0][0]
        # Tanpa memberi giliran: coroutine _run belum pernah masuk.
        service.tasks["r1"].cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not path.exists()

    asyncio.run(run())


def test_temp_file_removed_when_start_fails():
    async def run():
        service, _ = make_service()
        RecordingRenderer.fail = True
        status, _ = await service.start_session("r1", "agent", PHOTO)
        assert status == 503
        path, content = RecordingRenderer.seen[0]
        assert content == PHOTO and not path.exists()
        assert service.slots.active == 0

    asyncio.run(run())


def test_no_temp_file_when_slots_full():
    async def run():
        service, _ = make_service()
        assert (await service.start_session("r1", "agent"))[0] == 201
        status, _ = await service.start_session("r2", "agent", PHOTO)
        assert status == 503
        assert len(RecordingRenderer.seen) == 1  # r2 tidak sampai ke renderer
        await service.stop_session("r1")

    asyncio.run(run())


def test_without_image_uses_env_path():
    async def run():
        service, _ = make_service()
        assert (await service.start_session("r1", "agent"))[0] == 201
        assert RecordingRenderer.seen[0][0] == ENV_IMAGE
        await service.stop_session("r1")

    asyncio.run(run())


def _post(client, body):
    return client.post(
        "/sessions", json=body, headers={"X-Avatar-Signature": sign("rahasia", body["room"])}
    )


def test_http_corrupt_b64_falls_back_to_env():
    async def run():
        service, _ = make_service()
        async with TestClient(TestServer(create_app(service))) as client:
            body = {"room": "r1", "agent_identity": "agent", "reference_image_b64": "%%rusak%%"}
            resp = await _post(client, body)
            assert resp.status == 201
            assert RecordingRenderer.seen[0][0] == ENV_IMAGE
            await service.stop_session("r1")

    asyncio.run(run())


def test_http_accepts_5mb_photo_body():
    """Default aiohttp menolak body > 1 MB (413); foto 5 MB (~6,7 MB base64)
    harus tetap diterima."""
    big = b"\xff\xd8" + b"\x7f" * (5 * 1024 * 1024)

    async def run():
        service, _ = make_service()
        async with TestClient(TestServer(create_app(service))) as client:
            body = {
                "room": "r1",
                "agent_identity": "agent",
                "reference_image_b64": base64.b64encode(big).decode(),
            }
            resp = await _post(client, body)
            assert resp.status == 201, await resp.text()
            path, content = RecordingRenderer.seen[0]
            assert content == big
            await service.stop_session("r1")
            assert not path.exists()

    asyncio.run(run())
