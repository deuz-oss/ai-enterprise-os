"""File attachment chat: upload berdiri sendiri lalu ditempel ke pesan lewat
`file_ids` (alur ala Mattermost -- `POST /files` lalu `POST /posts`).
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
        for email, role, name in [("hr4@t.co", "hr", "HR Empat")]:
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

    return {"admin": admin, "hr": login("hr4@t.co")}


def _make_channel(client, headers, name="File Test", channel_type="public"):
    return client.post(
        "/api/v1/chat/channels", headers=headers, json={"name": name, "channel_type": channel_type}
    ).json()


def test_upload_then_attach_to_message(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)

    up = client.post(
        f"/api/v1/chat/channels/{ch['id']}/files",
        headers=admin,
        files={"file": ("gambar.png", b"\x89PNG fake bytes", "image/png")},
    )
    assert up.status_code == 201, up.text
    file_meta = up.json()
    assert file_meta["file_name"] == "gambar.png"
    assert file_meta["mime_type"] == "image/png"
    assert file_meta["file_size"] == len(b"\x89PNG fake bytes")
    assert "url" in file_meta

    resp = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "Lihat gambar ini", "file_ids": [file_meta["id"]]},
    )
    assert resp.status_code == 201, resp.text
    msg = resp.json()
    assert len(msg["files"]) == 1
    assert msg["files"][0]["id"] == file_meta["id"]

    # Muncul juga saat daftar pesan diambil ulang (bukan cuma di response kirim).
    listed = client.get(f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin).json()
    assert len(listed[-1]["files"]) == 1
    assert listed[-1]["files"][0]["file_name"] == "gambar.png"


def test_message_with_only_attachment_no_text_allowed(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)

    up = client.post(
        f"/api/v1/chat/channels/{ch['id']}/files",
        headers=admin,
        files={"file": ("dok.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    file_id = up.json()["id"]

    resp = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "", "file_ids": [file_id]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["content"] == ""
    assert len(resp.json()["files"]) == 1


def test_empty_message_without_attachment_still_rejected(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)
    resp = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin, json={"content": ""}
    )
    assert resp.status_code == 422


def test_oversized_file_rejected(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)
    too_big = b"x" * (10 * 1024 * 1024 + 1)
    resp = client.post(
        f"/api/v1/chat/channels/{ch['id']}/files",
        headers=admin,
        files={"file": ("besar.bin", too_big, "application/octet-stream")},
    )
    assert resp.status_code == 413


def test_cannot_attach_file_from_different_channel(client):
    h = _setup(client)
    admin = h["admin"]
    ch1 = _make_channel(client, admin, name="File Test A")
    ch2 = _make_channel(client, admin, name="File Test B")

    up = client.post(
        f"/api/v1/chat/channels/{ch1['id']}/files",
        headers=admin,
        files={"file": ("a.txt", b"isi file", "text/plain")},
    )
    file_id = up.json()["id"]

    resp = client.post(
        f"/api/v1/chat/channels/{ch2['id']}/messages",
        headers=admin,
        json={"content": "coba tempel lampiran channel lain", "file_ids": [file_id]},
    )
    assert resp.status_code == 422


def test_cannot_attach_another_users_file(client):
    h = _setup(client)
    admin, hr = h["admin"], h["hr"]
    ch = _make_channel(client, admin)
    # HR bukan member eksplisit tapi staff -- boleh upload+post di channel publik.

    up = client.post(
        f"/api/v1/chat/channels/{ch['id']}/files",
        headers=hr,
        files={"file": ("hr-file.txt", b"punya hr", "text/plain")},
    )
    assert up.status_code == 201, up.text
    file_id = up.json()["id"]

    resp = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "coba pakai lampiran orang lain", "file_ids": [file_id]},
    )
    assert resp.status_code == 403


def test_cannot_reuse_file_already_attached(client):
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)

    up = client.post(
        f"/api/v1/chat/channels/{ch['id']}/files",
        headers=admin,
        files={"file": ("sekali-pakai.txt", b"isi", "text/plain")},
    )
    file_id = up.json()["id"]

    first = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "pesan pertama", "file_ids": [file_id]},
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "coba pakai lagi", "file_ids": [file_id]},
    )
    assert second.status_code == 409


def test_deleting_message_with_attachment_does_not_error(client):
    """Pesan berlampiran yang dihapus tidak boleh 500 (dan -- perilaku
    existing `list_messages`, bukan hal baru dari lampiran -- pesan
    terhapus memang tidak lagi muncul di daftar sama sekali)."""
    h = _setup(client)
    admin = h["admin"]
    ch = _make_channel(client, admin)

    up = client.post(
        f"/api/v1/chat/channels/{ch['id']}/files",
        headers=admin,
        files={"file": ("rahasia.txt", b"isi", "text/plain")},
    )
    file_id = up.json()["id"]
    sent = client.post(
        f"/api/v1/chat/channels/{ch['id']}/messages",
        headers=admin,
        json={"content": "akan dihapus", "file_ids": [file_id]},
    ).json()

    resp = client.delete(f"/api/v1/chat/messages/{sent['id']}", headers=admin)
    assert resp.status_code == 204

    listed = client.get(f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin).json()
    assert sent["id"] not in [m["id"] for m in listed]


def test_karyawan_cannot_upload_outside_membership(client):
    """Karyawan (non-staff) tanpa membership di channel private tidak boleh
    upload -- sama seperti tidak boleh kirim pesan."""
    admin = _auth_header(client)
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        try:
            create_user(
                db,
                UserCreate(
                    email="worker-file@t.co",
                    full_name="Worker File",
                    password="rahasia-123",
                    role="karyawan",
                ),
                tenant_id=tenant.id,
            )
        except Exception:
            pass
    finally:
        db.close()

    resp = client.post(
        "/api/v1/auth/login", json={"email": "worker-file@t.co", "password": "rahasia-123"}
    )
    worker = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    ch = _make_channel(client, admin, name="Private No Worker", channel_type="private")
    up = client.post(
        f"/api/v1/chat/channels/{ch['id']}/files",
        headers=worker,
        files={"file": ("a.txt", b"isi", "text/plain")},
    )
    assert up.status_code == 403
