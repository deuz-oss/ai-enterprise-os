"""Fase 11 — Chat Workspace: channel, message, reaction, akses ter-scope."""

from tests.conftest import _auth_header


def _setup(client):
    admin = _auth_header(client)

    # Buat staff user (HR) dan karyawan outsourcing
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        for email, role, name in [
            ("hr@t.co", "hr", "HR Staff"),
            ("ops@t.co", "operations", "Ops Staff"),
            ("worker1@t.co", "karyawan", "TKO 1"),
            ("worker2@t.co", "karyawan", "TKO 2"),
        ]:
            try:
                create_user(
                    db,
                    UserCreate(email=email, full_name=name, password="rahasia-123", role=role),
                    tenant_id=tenant.id,
                )
            except Exception:
                pass
    finally:
        db.close()

    def login(email):
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "rahasia-123"})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return {
        "admin": admin,
        "hr": login("hr@t.co"),
        "ops": login("ops@t.co"),
        "worker1": login("worker1@t.co"),
        "worker2": login("worker2@t.co"),
    }


def test_create_channel_and_send_message(client):
    h = _setup(client)
    admin = h["admin"]

    created = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={
            "name": "General",
            "channel_type": "public",
        },
    )
    assert created.status_code == 201, created.text
    channel_id = created.json()["id"]

    # Kirim pesan dari admin
    msg = client.post(
        f"/api/v1/chat/channels/{channel_id}/messages",
        headers=admin,
        json={"content": "Selamat datang di workspace!"},
    )
    assert msg.status_code == 201, msg.text
    assert msg.json()["content"] == "Selamat datang di workspace!"
    assert msg.json()["is_own"] is True

    # List messages
    listed = client.get(f"/api/v1/chat/channels/{channel_id}/messages", headers=admin).json()
    assert len(listed) == 1


def test_karyawan_scoped_access(client):
    h = _setup(client)
    admin, worker1 = h["admin"], h["worker1"]

    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={
            "name": "Proyek Alpha",
            "channel_type": "private",
            "member_ids": [],
        },
    ).json()

    # Worker1 belum jadi member → 403
    blocked = client.get(f"/api/v1/chat/channels/{ch['id']}/messages", headers=worker1)
    assert blocked.status_code == 403

    # Tambah worker1 sebagai member (perlu user_id)
    users_list = client.get("/api/v1/auth/users", headers=admin).json()
    w1_id = next(u["id"] for u in users_list if u["email"] == "worker1@t.co")
    added = client.post(
        f"/api/v1/chat/channels/{ch['id']}/members",
        headers=admin,
        json={"user_id": w1_id},
    )
    assert added.status_code == 200

    # Sekarang bisa baca
    ok = client.get(f"/api/v1/chat/channels/{ch['id']}/messages", headers=worker1)
    assert ok.status_code == 200

    # Karyawan tidak bisa menambah member lain
    other_add = client.post(
        f"/api/v1/chat/channels/{ch['id']}/members",
        headers=worker1,
        json={"user_id": w1_id},
    )
    assert other_add.status_code == 403 or other_add.status_code == 409


def test_broadcast_channel_ops_only_post(client):
    h = _setup(client)
    ops, worker1 = h["ops"], h["worker1"]

    ch = client.post(
        "/api/v1/chat/channels",
        headers=ops,
        json={
            "name": "Pengumuman",
            "channel_type": "broadcast",
        },
    ).json()
    channel_id = ch["id"]

    # Ops bisa posting
    msg = client.post(
        f"/api/v1/chat/channels/{channel_id}/messages",
        headers=ops,
        json={"content": "Pengumuman penting!"},
    )
    assert msg.status_code == 201

    # Worker1 tidak bisa posting di broadcast (belum member juga → 403)
    denied_scope = client.post(
        f"/api/v1/chat/channels/{channel_id}/messages",
        headers=worker1,
        json={"content": "Halo"},
    )
    assert denied_scope.status_code == 403


def test_thread_reply_and_reaction(client):
    h = _setup(client)
    admin, hr = h["admin"], h["hr"]

    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={
            "name": "Diskusi",
            "channel_type": "public",
        },
    ).json()
    channel_id = ch["id"]

    parent = client.post(
        f"/api/v1/chat/channels/{channel_id}/messages",
        headers=admin,
        json={"content": "Pertanyaan: siapa yang handle payroll bulan ini?"},
    ).json()

    reply = client.post(
        f"/api/v1/chat/channels/{channel_id}/messages",
        headers=hr,
        json={"content": "Saya yang handle.", "parent_id": parent["id"]},
    )
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == parent["id"]

    # Thread replies terpisah
    thread = client.get(
        f"/api/v1/chat/channels/{channel_id}/messages",
        headers=admin,
        params={"parent_id": parent["id"]},
    ).json()
    assert len(thread) == 1 and thread[0]["content"] == "Saya yang handle."

    # Reaction
    react = client.post(
        f"/api/v1/chat/messages/{parent['id']}/react",
        headers=hr,
        json={"emoji": "👍"},
    )
    assert react.status_code == 200
    assert react.json()["active"] is True

    # Toggle off
    unreact = client.post(
        f"/api/v1/chat/messages/{parent['id']}/react",
        headers=hr,
        json={"emoji": "👍"},
    )
    assert unreact.json()["active"] is False

    # Edit & delete
    edited = client.patch(
        f"/api/v1/chat/messages/{parent['id']}",
        headers=admin,
        json={"content": "Pertanyaan revisi"},
    )
    assert edited.status_code == 200 and edited.json()["edited_at"] is not None

    deleted = client.delete(f"/api/v1/chat/messages/{parent['id']}", headers=admin)
    assert deleted.status_code == 204

    listed = client.get(f"/api/v1/chat/channels/{channel_id}/messages", headers=admin).json()
    deleted_msg = next((m for m in listed if m["id"] == parent["id"]), None)
    if deleted_msg:
        assert deleted_msg["content"] == "(pesan dihapus)"


def test_channel_list_shows_unread_for_karyawan(client):
    h = _setup(client)
    admin, worker1 = h["admin"], h["worker1"]

    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={
            "name": "Tim Proyek",
            "channel_type": "private",
        },
    ).json()
    users_list = client.get("/api/v1/auth/users", headers=admin).json()
    w1_id = next(u["id"] for u in users_list if u["email"] == "worker1@t.co")
    client.post(f"/api/v1/chat/channels/{ch['id']}/members", headers=admin, json={"user_id": w1_id})

    # Admin kirim 2 pesan
    for i in range(2):
        client.post(
            f"/api/v1/chat/channels/{ch['id']}/messages",
            headers=admin,
            json={"content": f"Pesan {i + 1}"},
        )

    channels = client.get("/api/v1/chat/channels", headers=worker1).json()
    target = next(c for c in channels if c["id"] == ch["id"])
    assert target["unread_count"] == 2
