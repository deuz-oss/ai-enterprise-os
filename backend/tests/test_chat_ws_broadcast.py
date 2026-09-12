"""Regresi: ChatWSManager.broadcast() dulu mengirim ke SEMUA tenant tanpa
filter (kebocoran konten pesan chat antar tenant) dan tidak pernah dipanggil
untuk pesan biasa (hanya kartu interaktif). Tes ini mengunci:

1. broadcast() ter-scope ke tenant target, tidak bocor ke tenant lain.
2. Jika `user_ids` diberikan, hanya koneksi user itu yang menerima.
3. `_channel_audience_ids` = staff tenant + member eksplisit non-staff saja.
"""

import asyncio

from app.modules.chat.ws_manager import ChatWSManager

from tests.conftest import _auth_header


class _FakeWebSocket:
    def __init__(self) -> None:
        self.received: list[str] = []

    async def accept(self) -> None:
        pass

    async def send_text(self, text: str) -> None:
        self.received.append(text)


def test_broadcast_does_not_leak_across_tenants():
    manager = ChatWSManager()
    ws_a = _FakeWebSocket()
    ws_b = _FakeWebSocket()

    async def _run():
        await manager.connect("tenant-a", "user-1", ws_a)  # type: ignore[arg-type]
        await manager.connect("tenant-b", "user-2", ws_b)  # type: ignore[arg-type]
        await manager.broadcast(tenant_id="tenant-a", payload={"event": "message.created"})

    asyncio.run(_run())

    assert ws_a.received, "koneksi di tenant target harus menerima broadcast"
    assert not ws_b.received, "koneksi di tenant lain TIDAK boleh menerima broadcast"


def test_broadcast_filters_by_audience_user_ids():
    manager = ChatWSManager()
    ws_member = _FakeWebSocket()
    ws_outsider = _FakeWebSocket()

    async def _run():
        await manager.connect("tenant-a", "member-1", ws_member)  # type: ignore[arg-type]
        await manager.connect("tenant-a", "outsider-1", ws_outsider)  # type: ignore[arg-type]
        await manager.broadcast(
            tenant_id="tenant-a",
            payload={"event": "message.created"},
            user_ids={"member-1"},
        )

    asyncio.run(_run())

    assert ws_member.received
    assert not ws_outsider.received, "user di luar audience channel tidak boleh menerima broadcast"


def test_channel_audience_is_staff_plus_explicit_members(client):
    admin = _auth_header(client)

    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user
    from app.modules.chat import service as chat_service
    from app.modules.chat.models import Channel

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        for email, role, name in [
            ("hr2@t.co", "hr", "HR Staff 2"),
            ("worker-in@t.co", "karyawan", "Worker In"),
            ("worker-out@t.co", "karyawan", "Worker Out"),
        ]:
            try:
                create_user(
                    db,
                    UserCreate(email=email, full_name=name, password="rahasia-123", role=role),
                    tenant_id=tenant.id,
                )
            except Exception:
                pass
        db.commit()
    finally:
        db.close()

    # Buat channel private via API sebagai admin, tambahkan hanya worker-in sebagai member.
    resp = client.post(
        "/api/v1/chat/channels",
        json={"name": "Audience Test", "channel_type": "private"},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    channel_id = resp.json()["id"]

    db = client.testing_session()
    try:
        from app.modules.auth.models import User
        from sqlalchemy import select

        worker_in = db.execute(select(User).where(User.email == "worker-in@t.co")).scalar_one()
        client.post(
            f"/api/v1/chat/channels/{channel_id}/members",
            json={"user_id": str(worker_in.id)},
            headers=admin,
        )

        from app.core.database import parse_uuid

        ch = db.get(Channel, parse_uuid(channel_id))
        audience = chat_service._channel_audience_ids(db, ch)

        hr = db.execute(select(User).where(User.email == "hr2@t.co")).scalar_one()
        worker_out = db.execute(select(User).where(User.email == "worker-out@t.co")).scalar_one()

        assert str(hr.id) in audience, "staff tenant harus selalu masuk audience"
        assert str(worker_in.id) in audience, "member eksplisit harus masuk audience"
        assert (
            str(worker_out.id) not in audience
        ), "karyawan yang bukan member channel ini tidak boleh masuk audience"
    finally:
        db.close()
