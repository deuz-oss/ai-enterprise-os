"""Foto avatar pewawancara AI per tenant: unggah (validasi + normalisasi
JPEG), ganti, hapus, isolasi tenant, dan endpoint khusus agent yang
meneruskan foto ke avatar-worker. Storage mode lokal di test (data/uploads)."""

import io

from PIL import Image

from tests.conftest import _auth_header, _login_header, _platform_admin_header
from tests.test_ai_interview import (
    _agent_headers,
    _create_active_template,
    _create_candidate,
    _invite,
)
from tests.test_apps import _provision_tenant, _seed_active_subscription

URL = "/api/v1/ai-interview/settings/avatar-image"


def _png(width=400, height=500, color=(200, 120, 80), mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, headers, data: bytes, *, mime="image/png", consent="true", name="a.png"):
    form = {} if consent is None else {"consent": consent}
    return client.put(URL, headers=headers, data=form, files={"file": (name, data, mime)})


def _stored_key(client) -> str | None:
    from app.modules.ai_interview.models import AIInterviewSettings
    from sqlalchemy import select

    db = client.testing_session()
    try:
        rows = (
            db.execute(
                select(AIInterviewSettings).execution_options(include_with_loader_criteria=False)
            )
            .scalars()
            .all()
        )
        keys = [r.avatar_image_key for r in rows if r.avatar_image_key]
        return keys[-1] if keys else None
    finally:
        db.close()


def test_settings_default_has_no_avatar(client):
    admin = _auth_header(client)
    body = client.get("/api/v1/ai-interview/settings", headers=admin).json()
    assert body["has_avatar_image"] is False
    assert body["avatar_image_updated_at"] is None
    assert body["retention_days"] == 180
    assert client.get(URL, headers=admin).status_code == 404


def test_upload_valid_png_normalized_to_jpeg(client):
    from app.core.config import get_settings

    admin = _auth_header(client)
    # 2000x1500 RGBA: harus diperkecil ke sisi terpanjang 1024 dan jadi RGB.
    resp = _upload(client, admin, _png(2000, 1500, (10, 200, 30, 128), mode="RGBA"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_avatar_image"] is True
    assert body["avatar_image_updated_at"] is not None

    got = client.get(URL, headers=admin)
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/jpeg"
    assert got.headers["cache-control"] == "no-store"
    img = Image.open(io.BytesIO(got.content))
    assert img.format == "JPEG" and img.mode == "RGB"
    assert max(img.size) == 1024 and img.size == (1024, 768)
    assert not img.getexif()  # metadata asli tidak ikut tersimpan

    key = _stored_key(client)
    assert key and (get_settings().uploads_root / key).exists()
    assert client.get("/api/v1/ai-interview/settings", headers=admin).json()["has_avatar_image"]


def test_exif_orientation_applied_and_stripped(client):
    admin = _auth_header(client)
    src = Image.new("RGB", (300, 600), (50, 50, 50))
    exif = src.getexif()
    exif[0x0112] = 6  # Orientation: putar 90 derajat
    exif[0x010F] = "KameraRahasia"  # Make
    buf = io.BytesIO()
    src.save(buf, format="JPEG", exif=exif.tobytes())
    resp = _upload(client, admin, buf.getvalue(), mime="image/jpeg", name="a.jpg")
    assert resp.status_code == 200, resp.text
    img = Image.open(io.BytesIO(client.get(URL, headers=admin).content))
    assert img.size == (600, 300)
    assert not img.getexif()


def test_upload_requires_consent(client):
    admin = _auth_header(client)
    for consent in (None, "false", ""):
        resp = _upload(client, admin, _png(), consent=consent)
        assert resp.status_code == 422
        assert resp.json()["detail"] == "Konfirmasi izin pemakaian foto wajib dicentang"
    assert _stored_key(client) is None


def test_upload_rejects_wrong_format(client):
    admin = _auth_header(client)
    resp = _upload(client, admin, b"GIF89a....", mime="image/gif", name="a.gif")
    assert resp.status_code == 422
    assert "JPEG, PNG, atau WebP" in resp.json()["detail"]

    # MIME mengaku PNG tapi isinya GIF asli -> tetap ditolak.
    buf = io.BytesIO()
    Image.new("RGB", (400, 400)).save(buf, format="GIF")
    resp = _upload(client, admin, buf.getvalue(), mime="image/png")
    assert resp.status_code == 422
    assert "JPEG, PNG, atau WebP" in resp.json()["detail"]


def test_upload_rejects_over_5mb(client):
    admin = _auth_header(client)
    big = _png() + b"\x00" * (5 * 1024 * 1024)
    resp = _upload(client, admin, big)
    assert resp.status_code == 422
    assert "5 MB" in resp.json()["detail"]


def test_upload_rejects_non_image_and_truncated(client):
    admin = _auth_header(client)
    resp = _upload(client, admin, b"ini bukan gambar sama sekali" * 10)
    assert resp.status_code == 422
    assert "bukan gambar yang valid" in resp.json()["detail"]

    truncated = _png(800, 800)[:200]
    resp = _upload(client, admin, truncated)
    assert resp.status_code == 422
    assert "bukan gambar yang valid" in resp.json()["detail"]


def test_upload_rejects_too_small(client):
    admin = _auth_header(client)
    resp = _upload(client, admin, _png(100, 100))
    assert resp.status_code == 422
    assert "256x256" in resp.json()["detail"]


def test_upload_rejects_decompression_bomb(client):
    admin = _auth_header(client)
    # 8000x8000 = 64 MP (> 40 MP), file PNG-nya kecil karena warna rata.
    resp = _upload(client, admin, _png(8000, 8000, (0, 0, 0)))
    assert resp.status_code == 422
    assert "Resolusi foto terlalu besar" in resp.json()["detail"]


def test_replace_deletes_old_object_and_delete_is_idempotent(client):
    from app.core.config import get_settings

    admin = _auth_header(client)
    root = get_settings().uploads_root
    assert _upload(client, admin, _png(color=(1, 2, 3))).status_code == 200
    first = _stored_key(client)
    assert _upload(client, admin, _png(color=(200, 2, 3))).status_code == 200
    second = _stored_key(client)
    assert first != second
    assert not (root / first).exists() and (root / second).exists()

    removed = client.delete(URL, headers=admin)
    assert removed.status_code == 200, removed.text
    assert removed.json()["has_avatar_image"] is False
    assert not (root / second).exists()
    assert client.get(URL, headers=admin).status_code == 404
    again = client.delete(URL, headers=admin)
    assert again.status_code == 200 and again.json()["has_avatar_image"] is False


def test_replace_survives_failed_old_object_delete(client, monkeypatch):
    from app.core import storage
    from fastapi import HTTPException

    admin = _auth_header(client)
    assert _upload(client, admin, _png()).status_code == 200

    def boom(key):
        raise HTTPException(status_code=502, detail="storage mati")

    monkeypatch.setattr(storage, "delete_object", boom)
    resp = _upload(client, admin, _png(color=(9, 9, 9)))
    assert resp.status_code == 200, resp.text
    assert client.delete(URL, headers=admin).status_code == 200


def test_audit_events_recorded(client):
    from app.modules.audit.models import AuditLog
    from sqlalchemy import select

    admin = _auth_header(client)
    _upload(client, admin, _png())
    client.delete(URL, headers=admin)
    db = client.testing_session()
    try:
        rows = (
            db.execute(
                select(AuditLog)
                .where(AuditLog.action.like("ai_interview.avatar_image%"))
                .execution_options(include_with_loader_criteria=False)
            )
            .scalars()
            .all()
        )
    finally:
        db.close()
    actions = [r.action for r in rows]
    assert "ai_interview.avatar_image_changed" in actions
    assert "ai_interview.avatar_image_removed" in actions


def test_tenant_isolation(client):
    a = _auth_header(client)
    assert _upload(client, a, _png()).status_code == 200

    platform = _platform_admin_header(client)
    tenant_b = _provision_tenant(client, platform, "tenant-avatar-b")
    tenant_b_id = tenant_b.get("id") or tenant_b.get("tenant", {}).get("id")
    _seed_active_subscription(client, tenant_b_id)
    b = _login_header(client, "admin-tenant-avatar-b@example.com", "rahasia-123")

    settings_b = client.get("/api/v1/ai-interview/settings", headers=b)
    assert settings_b.status_code == 200, settings_b.text
    assert settings_b.json()["has_avatar_image"] is False
    assert client.get(URL, headers=b).status_code == 404
    # Hapus di B tidak menyentuh foto A.
    assert client.delete(URL, headers=b).status_code == 200
    assert client.get(URL, headers=a).status_code == 200


def _voice_token(client, admin) -> str:
    template = _create_active_template(client, admin, mode="realtime_voice")
    cand_id = _create_candidate(client, admin, name="Sari", email="sari-avatar@example.com")
    return _invite(client, admin, template["id"], cand_id)["invite_token"]


def test_agent_avatar_endpoint(client, monkeypatch):
    admin = _auth_header(client)
    token = _voice_token(client, admin)
    url = f"/api/v1/ai-interview/session/{token}/voice/avatar-image"
    agent = _agent_headers(monkeypatch, token)

    # Tanpa / dengan tanda tangan salah: ditolak (kandidat cuma punya token).
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-Agent-Signature": "salah"}).status_code == 401

    assert client.get(url, headers=agent).status_code == 404  # belum ada foto -> env

    assert _upload(client, admin, _png()).status_code == 200
    got = client.get(url, headers=agent)
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/jpeg"
    assert got.content == client.get(URL, headers=admin).content


def test_agent_avatar_endpoint_uses_session_tenant(client, monkeypatch):
    """Sesi milik tenant B tidak pernah mendapat foto tenant A."""
    a = _auth_header(client)
    assert _upload(client, a, _png()).status_code == 200

    platform = _platform_admin_header(client)
    tenant_b = _provision_tenant(client, platform, "tenant-avatar-c")
    tenant_b_id = tenant_b.get("id") or tenant_b.get("tenant", {}).get("id")
    _seed_active_subscription(client, tenant_b_id)
    b = _login_header(client, "admin-tenant-avatar-c@example.com", "rahasia-123")
    client.post("/api/v1/clients", headers=b, json={"name": "PT B"})
    token_b = _voice_token(client, b)
    resp = client.get(
        f"/api/v1/ai-interview/session/{token_b}/voice/avatar-image",
        headers=_agent_headers(monkeypatch, token_b),
    )
    assert resp.status_code == 404
