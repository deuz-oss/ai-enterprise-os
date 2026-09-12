"""Pinned posts dan preferensi notifikasi per channel (notify_level) --
dua item terakhir dari roadmap riset arsitektur Mattermost untuk chat.
"""

from tests.conftest import _auth_header


def _setup(client):
    admin = _auth_header(client)
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        for email, role, name in [
            ("hr5@t.co", "hr", "HR Lima"),
            ("worker5@t.co", "karyawan", "Worker Lima"),
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

    return {"admin": admin, "hr": login("hr5@t.co"), "worker": login("worker5@t.co")}


def _make_channel(client, headers, name="Pin Test", channel_type="public", member_ids=None):
    payload = {"name": name, "channel_type": channel_type}
    if member_ids:
        payload["member_ids"] = member_ids
    return client.post("/api/v1/chat/channels", headers=headers, json=payload).json()


# ---------- Pinned posts ----------


def test_pin_then_unpin_message(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)
    msg = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin, json={"content": "Penting!"}
    ).json()

    resp = client.post(f"/api/v1/chat/messages/{msg['id']}/pin", headers=admin)
    assert resp.status_code == 200
    assert resp.json() == {"message_id": msg["id"], "is_pinned": True}

    pinned = client.get(f"/api/v1/chat/channels/{ch['id']}/pinned", headers=admin).json()
    assert [m["id"] for m in pinned] == [msg["id"]]
    assert pinned[0]["is_pinned"] is True
    assert pinned[0]["pinned_at"] is not None

    listed = client.get(f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin).json()
    assert next(m for m in listed if m["id"] == msg["id"])["is_pinned"] is True

    # Toggle lagi -- unpin.
    resp2 = client.post(f"/api/v1/chat/messages/{msg['id']}/pin", headers=admin)
    assert resp2.json() == {"message_id": msg["id"], "is_pinned": False}
    pinned_after = client.get(f"/api/v1/chat/channels/{ch['id']}/pinned", headers=admin).json()
    assert pinned_after == []


def test_pin_nonexistent_message_404(client):
    h = _setup(client)
    admin = h["admin"]
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = client.post(f"/api/v1/chat/messages/{fake_id}/pin", headers=admin)
    assert resp.status_code == 404


def test_karyawan_without_membership_cannot_pin(client):
    h = _setup(client)
    admin, worker = h["admin"], h["worker"]
    ch = _make_channel(client, admin, name="Private No Worker Pin", channel_type="private")
    msg = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin, json={"content": "Rahasia"}
    ).json()

    resp = client.post(f"/api/v1/chat/messages/{msg['id']}/pin", headers=worker)
    assert resp.status_code == 403


def test_pinned_list_scoped_per_channel(client):
    h = _setup(client)
    admin = h["admin"]
    ch1 = _make_channel(client, admin, name="Pin Scope A")
    ch2 = _make_channel(client, admin, name="Pin Scope B")
    m1 = client.post(
        f"/api/v1/chat/channels/{ch1['id']}/messages", headers=admin, json={"content": "A"}
    ).json()
    m2 = client.post(
        f"/api/v1/chat/channels/{ch2['id']}/messages", headers=admin, json={"content": "B"}
    ).json()
    client.post(f"/api/v1/chat/messages/{m1['id']}/pin", headers=admin)
    client.post(f"/api/v1/chat/messages/{m2['id']}/pin", headers=admin)

    pinned1 = client.get(f"/api/v1/chat/channels/{ch1['id']}/pinned", headers=admin).json()
    pinned2 = client.get(f"/api/v1/chat/channels/{ch2['id']}/pinned", headers=admin).json()
    assert [m["id"] for m in pinned1] == [m1["id"]]
    assert [m["id"] for m in pinned2] == [m2["id"]]


def test_create_channel_with_member_ids_at_creation(client):
    """Regresi: `member_ids` di `POST /chat/channels` dulu diinsert mentah
    tanpa `parse_uuid` (SQLAlchemy error 'str has no attribute hex') dan
    `uid != user.id` (str vs UUID) tidak pernah true -- jalur ini sama
    sekali tidak pernah dites sebelumnya."""
    h = _setup(client)
    admin = h["admin"]
    users = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users if u["email"] == "worker5@t.co")

    resp = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={
            "name": "Member IDs At Creation",
            "channel_type": "private",
            "member_ids": [worker_id],
        },
    )
    assert resp.status_code == 201, resp.text
    ch = resp.json()

    worker = h["worker"]
    worker_channels = client.get("/api/v1/chat/channels", headers=worker).json()
    assert any(c["id"] == ch["id"] for c in worker_channels)


# ---------- Notification preferences (notify_level) ----------


def test_default_notify_level_public_vs_dm(client):
    h = _setup(client)
    admin, worker = h["admin"], h["worker"]
    users = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users if u["email"] == "worker5@t.co")

    public_ch = _make_channel(client, admin, name="Notify Default Public")
    dm_ch = _make_channel(
        client, admin, name="dm-admin-worker5", channel_type="dm", member_ids=[worker_id]
    )

    public_channels = client.get("/api/v1/chat/channels", headers=admin).json()
    dm_channels = client.get("/api/v1/chat/channels", headers=admin).json()
    public_row = next(c for c in public_channels if c["id"] == public_ch["id"])
    dm_row = next(c for c in dm_channels if c["id"] == dm_ch["id"])
    assert public_row["notify_level"] == "mentions"
    assert dm_row["notify_level"] == "all"

    # Member yang ditambahkan lewat member_ids (worker5) juga dapat default
    # "all" untuk DM, bukan cuma si pembuat channel.
    worker_channels = client.get("/api/v1/chat/channels", headers=worker).json()
    worker_dm_row = next(c for c in worker_channels if c["id"] == dm_ch["id"])
    assert worker_dm_row["notify_level"] == "all"


def test_set_notify_level_invalid_rejected(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)
    resp = client.put(
        f"/api/v1/chat/channels/{ch['id']}/notify-level", headers=admin, json={"level": "loud"}
    )
    assert resp.status_code == 422


def test_muted_channel_suppresses_mention_count_and_notification(client):
    h = _setup(client)
    admin, worker = h["admin"], h["worker"]
    ch = _make_channel(client, admin, name="Mute Test", channel_type="private")
    users = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users if u["email"] == "worker5@t.co")
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/members", headers=admin, json={"user_id": worker_id}
    )

    mute_resp = client.put(
        f"/api/v1/chat/channels/{ch['id']}/notify-level", headers=worker, json={"level": "none"}
    )
    assert mute_resp.status_code == 200

    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "Halo @Worker Lima tolong cek"},
    )

    rows = client.get("/api/v1/chat/channels", headers=worker).json()
    target = next(c for c in rows if c["id"] == ch["id"])
    assert target["mention_count"] == 0

    db = client.testing_session()
    try:
        from app.modules.notifications.models import Notification

        count = db.query(Notification).filter(Notification.category == "chat_mention").count()
        assert count == 0
    finally:
        db.close()


def test_mention_followed_by_punctuation_still_matches(client):
    """Regresi: token mention mentah membawa tanda baca penutup (mis. koma
    sebelum lanjutan kalimat), jadi "Worker Lima," tidak pernah cocok
    dengan nama asli "Worker Lima" -- @mention diikuti koma/titik gagal
    total walau namanya tepat. Lihat `_extract_mention_tokens`."""
    h = _setup(client)
    admin, worker = h["admin"], h["worker"]
    ch = _make_channel(client, admin, name="Mention Punctuation Test", channel_type="private")
    users = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users if u["email"] == "worker5@t.co")
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/members", headers=admin, json={"user_id": worker_id}
    )

    for content in [
        "Halo @Worker Lima, tolong cek ini",
        "cc @Worker Lima. Terima kasih",
        "@Worker Lima! ada waktu?",
    ]:
        client.post(
            f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin, json={"content": content}
        )

    rows = client.get("/api/v1/chat/channels", headers=worker).json()
    target = next(c for c in rows if c["id"] == ch["id"])
    assert target["mention_count"] == 3


def test_mention_creates_bell_notification_by_default(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin, name="Mention Bell Test", channel_type="private")
    users = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users if u["email"] == "worker5@t.co")
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/members", headers=admin, json={"user_id": worker_id}
    )
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "Halo @Worker Lima, tolong review ini"},
    )

    db = client.testing_session()
    try:
        from app.core.database import parse_uuid
        from app.modules.notifications.models import Notification

        notif = (
            db.query(Notification)
            .filter(
                Notification.category == "chat_mention",
                Notification.user_id == parse_uuid(worker_id),
            )
            .one_or_none()
        )
        assert notif is not None
        assert "Mention Bell Test" in notif.title
        assert "menyebut Anda" in notif.title
        assert notif.body == "Halo @Worker Lima, tolong review ini"
    finally:
        db.close()


def test_all_level_marks_every_message_without_bell_notification(client):
    """`notify_level=all` menandai SETIAP pesan sebagai badge mention untuk
    anggota itu, tapi TIDAK memicu notifikasi bel (beda dari @mention asli)
    -- supaya channel ramai tidak membanjiri bel/email."""
    h = _setup(client)
    admin, worker = h["admin"], h["worker"]
    ch = _make_channel(client, admin, name="All Level Test", channel_type="private")
    users = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users if u["email"] == "worker5@t.co")
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/members", headers=admin, json={"user_id": worker_id}
    )
    client.put(
        f"/api/v1/chat/channels/{ch['id']}/notify-level", headers=worker, json={"level": "all"}
    )

    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "Pesan biasa tanpa mention"},
    )

    rows = client.get("/api/v1/chat/channels", headers=worker).json()
    target = next(c for c in rows if c["id"] == ch["id"])
    assert target["mention_count"] == 1

    db = client.testing_session()
    try:
        from app.modules.notifications.models import Notification

        count = db.query(Notification).filter(Notification.category == "chat_mention").count()
        assert count == 0
    finally:
        db.close()
