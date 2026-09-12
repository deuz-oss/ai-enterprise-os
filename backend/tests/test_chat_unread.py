"""Model unread counter ala Mattermost (unread = total_msg_count - msg_count).

Regresi yang dikunci di sini:
1. `read-all` dulu HANYA menghitung count tanpa menyimpan apa pun — klik
   "Tandai dibaca" di UI tidak pernah benar-benar mengubah state tersimpan,
   jadi badge unread tidak pernah berkurang. Sekarang persisten.
2. Mention men-set `mention_count` per user, ikut ter-reset saat channel
   dilihat.
3. Staff yang bukan member eksplisit channel publik dulu SELALU unread_count=0
   (tidak pernah dihitung) — sekarang ikut model counter yang sama seperti
   karyawan, jadi channel yang belum pernah dilihat tetap unread.
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
            ("hr3@t.co", "hr", "HR Tiga"),
            ("worker3@t.co", "karyawan", "Worker Tiga"),
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

    return {"admin": admin, "hr": login("hr3@t.co"), "worker": login("worker3@t.co")}


def test_read_all_persists_and_clears_unread(client):
    h = _setup(client)
    admin, worker = h["admin"], h["worker"]

    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Unread Persist Test", "channel_type": "private"},
    ).json()
    users_list = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users_list if u["email"] == "worker3@t.co")
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/members", headers=admin, json={"user_id": worker_id}
    )

    for i in range(3):
        client.post(
            f"/api/v1/chat/channels/{ch['id']}/messages",
            headers=admin,
            json={"content": f"Pesan {i + 1}"},
        )

    def unread_for(headers):
        rows = client.get("/api/v1/chat/channels", headers=headers).json()
        return next(c for c in rows if c["id"] == ch["id"])["unread_count"]

    assert unread_for(worker) == 3

    resp = client.post(f"/api/v1/chat/channels/{ch['id']}/read-all", headers=worker)
    assert resp.status_code == 200
    assert resp.json()["marked"] == 3

    # Regresi inti: setelah read-all, unread harus BENAR-BENAR turun ke 0,
    # bukan cuma di response sesaat tapi tetap 3 di fetch selanjutnya.
    assert unread_for(worker) == 0

    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "Pesan setelah dibaca"},
    )
    assert unread_for(worker) == 1


def test_mention_count_tracked_and_reset_on_read(client):
    h = _setup(client)
    admin, worker = h["admin"], h["worker"]

    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Mention Test", "channel_type": "private"},
    ).json()
    users_list = client.get("/api/v1/auth/users", headers=admin).json()
    worker_id = next(u["id"] for u in users_list if u["email"] == "worker3@t.co")
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/members", headers=admin, json={"user_id": worker_id}
    )

    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "Halo @Worker Tiga tolong cek ini"},
    )

    rows = client.get("/api/v1/chat/channels", headers=worker).json()
    target = next(c for c in rows if c["id"] == ch["id"])
    assert target["mention_count"] >= 1

    client.post(f"/api/v1/chat/channels/{ch['id']}/read-all", headers=worker)

    rows = client.get("/api/v1/chat/channels", headers=worker).json()
    target = next(c for c in rows if c["id"] == ch["id"])
    assert target["mention_count"] == 0
    assert target["unread_count"] == 0


def test_staff_without_membership_row_sees_unread_on_public_channel(client):
    h = _setup(client)
    admin, hr = h["admin"], h["hr"]

    ch = client.post(
        "/api/v1/chat/channels",
        headers=admin,
        json={"name": "Public Unread Test", "channel_type": "public"},
    ).json()
    client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "Pesan publik pertama"},
    )

    # HR bukan member eksplisit tapi staff -- dulu unread_count SELALU 0
    # tanpa syarat untuk staff; sekarang ikut model counter yang sama.
    rows = client.get("/api/v1/chat/channels", headers=hr).json()
    target = next(c for c in rows if c["id"] == ch["id"])
    assert target["unread_count"] == 1

    client.post(f"/api/v1/chat/channels/{ch['id']}/read-all", headers=hr)

    rows = client.get("/api/v1/chat/channels", headers=hr).json()
    target = next(c for c in rows if c["id"] == ch["id"])
    assert target["unread_count"] == 0
