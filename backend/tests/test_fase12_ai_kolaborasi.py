"""Fase 12 — AI Kolaborasi: @AEOS, rangkuman thread, digest, slash command."""

from datetime import date, timedelta
from unittest.mock import patch

from tests.conftest import _auth_header


def _setup(client):
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
                UserCreate(email="hr12@t.co", full_name="HR 12", password="rahasia-123", role="hr"),
                tenant_id=tenant.id,
            )
        except Exception:
            pass
    finally:
        db.close()

    def login(email):
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "rahasia-123"})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return {"admin": admin, "hr": login("hr12@t.co")}


def _channel(client, headers, name, channel_type="public"):
    created = client.post(
        "/api/v1/chat/channels", headers=headers, json={"name": name, "channel_type": channel_type}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _send(client, headers, channel_id, content):
    resp = client.post(
        f"/api/v1/chat/channels/{channel_id}/messages", headers=headers, json={"content": content}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _replies(client, headers, channel_id, root_id):
    rows = client.get(
        f"/api/v1/chat/channels/{channel_id}/messages",
        headers=headers,
        params={"parent_id": root_id},
    ).json()
    return rows


def _toplevel(client, headers, channel_id):
    """Pesan level-atas channel (parent_id=None) — tempat balasan AEOS/slash
    command sungguhan muncul saat trigger-nya sendiri top-level (regresi:
    dulu selalu ke-nest jadi balasan thread di bawah pesan pemicu, jadi tak
    pernah tampil di sini)."""
    return client.get(f"/api/v1/chat/channels/{channel_id}/messages", headers=headers).json()


def test_slash_help_dan_pr_status_di_channel_public(client):
    h = _setup(client)
    ch = _channel(client, h["admin"], "general")

    _send(client, h["admin"], ch, "/help")
    replies = _toplevel(client, h["admin"], ch)
    assert any("Perintah tersedia" in r["content"] for r in replies)

    # Seed PR menunggu langsung via DB agar fokus ke perintahnya
    from app.modules.auth.models import User
    from app.modules.finance.models import PaymentRequest, PaymentRequestStatus
    from sqlalchemy import select

    db = client.testing_session()
    try:
        u = (
            db.execute(select(User).where(User.email == "brian@outsourcing.co.id"))
            .scalars()
            .first()
        )
        db.add(
            PaymentRequest(
                tenant_id=u.tenant_id,
                pr_number="PR/2026/9001",
                pr_type="internal",
                amount=7_500_000,
                status=PaymentRequestStatus.waiting_superior,
                requester_id=u.id,
            )
        )
        db.commit()
    finally:
        db.close()

    _send(client, h["admin"], ch, "/pr status")
    replies2 = _toplevel(client, h["admin"], ch)
    assert any("PR/2026/9001" in r["content"] for r in replies2)


def test_cuti_hanya_di_dm_dan_ajukan_butuh_karyawan_tertaut(client):
    h = _setup(client)
    pub = _channel(client, h["admin"], "pub-cuti")

    # Di channel public ditolak dengan arahan DM
    _send(client, h["hr"], pub, "/cuti sisa")
    replies = _toplevel(client, h["hr"], pub)
    assert any("bersifat pribadi" in r["content"] for r in replies)

    dm = _channel(client, h["hr"], "DM HR-AEOS", channel_type="dm")
    _send(client, h["hr"], dm, "/cuti sisa")
    replies2 = _toplevel(client, h["hr"], dm)
    # Tanpa karyawan tertaut → pesan ramah; dengan kuota → angka sisa.
    assert replies2
    joined = "\n".join(r["content"] for r in replies2)
    assert (
        ("cuti tahunan" in joined.lower()) or ("belum tertaut" in joined.lower()) or ("⚠️" in joined)
    )

    # Ajukan tanpa karyawan tertaut → pesan ramah dari AEOS, bukan crash
    tomorrow = date.today() + timedelta(days=1)
    day_after = date.today() + timedelta(days=2)
    _send(
        client,
        h["hr"],
        dm,
        f"/cuti ajukan izin {tomorrow.isoformat()} {day_after.isoformat()} acara keluarga",
    )
    replies3 = _toplevel(client, h["hr"], dm)
    assert replies3, "harus ada balasan AEOS"
    assert any("⚠️" in r["content"] or "✅" in r["content"] for r in replies3)


def test_aeos_mention_tanpa_lisensi_memberi_pesan_ramah(client):
    from app.modules.ai import collab

    h = _setup(client)
    ch = _channel(client, h["admin"], "ai-room")

    with patch.object(collab, "_ai_license_active", return_value=False):
        _send(client, h["admin"], ch, "@AEOS berapa total invoice belum lunas?")
    replies = _toplevel(client, h["admin"], ch)
    assert any("AI add-on" in r["content"] for r in replies)
    # Regresi: balasan harus top-level (parent_id None) sama seperti pemicu,
    # bukan di-nest sebagai thread di bawahnya (tak akan tampil di channel utama).
    aeos_reply = next(r for r in replies if "AI add-on" in r["content"])
    assert aeos_reply["parent_id"] is None


def test_aeos_mention_dengan_llm_mocked_membalas_jawaban(client):
    from app.modules.ai import collab

    h = _setup(client)
    ch = _channel(client, h["admin"], "ai-room-2")

    with patch.object(
        collab, "chat_completion", return_value="Pendapatan tahun ini Rp100.000.000."
    ):
        _send(client, h["admin"], ch, "@AEOS bagaimana laba rugi tahun ini?")
    replies = _toplevel(client, h["admin"], ch)
    assert any("Rp100.000.000" in r["content"] for r in replies)

    # Pertanyaan di luar data + kata kunci finance → saran routing Finance
    with patch.object(collab, "chat_completion", return_value="Saya tidak menemukan datanya."):
        _send(client, h["admin"], ch, "@AEOS kapan PPN faktur lama dikoreksi?")
    replies2 = _toplevel(client, h["admin"], ch)
    assert any("routing" in r["content"].lower() for r in replies2)


def test_summarize_thread_endpoint(client):
    from app.modules.ai import collab

    h = _setup(client)
    ch = _channel(client, h["admin"], "thread-sum")

    root = _send(client, h["admin"], ch, "Kita perlu putuskan vendor ATK")
    for text in (
        "Vendor A harga 2 juta",
        "Setuju Vendor A, tolong buat PO",
        "OK saya buat PO besok",
    ):
        client.post(
            f"/api/v1/chat/channels/{ch}/messages",
            headers=h["admin"],
            json={"content": text, "parent_id": root["id"]},
        )

    # Thread pendek tanpa reply → 422
    single = _send(client, h["admin"], ch, "Root kosong")
    short = client.post(f"/api/v1/chat/messages/{single['id']}/summarize", headers=h["admin"])
    assert short.status_code == 422

    with patch.object(
        collab, "chat_completion", return_value="- Vendor A dipilih\n- PO dibuat besok"
    ):
        result = client.post(f"/api/v1/chat/messages/{root['id']}/summarize", headers=h["admin"])
    assert result.status_code == 200, result.text
    body = result.json()
    assert "Vendor A dipilih" in body["summary"]
    assert body["message_count"] == 3

    # Balasan rangkuman muncul di thread
    replies = _replies(client, h["admin"], ch, root["id"])
    assert any("Rangkuman thread" in r["content"] for r in replies)


def test_digest_harian_dan_ask_langsung(client):
    h = _setup(client)

    digest = client.get("/api/v1/chat/digest", headers=h["admin"])
    assert digest.status_code == 200, digest.text
    types = [i["type"] for i in digest.json()["items"]]
    assert "ringkasan" in types

    ask = client.post(
        "/api/v1/chat/ask", headers=h["admin"], json={"question": "berapa lead saat ini?"}
    )
    assert ask.status_code == 200, ask.text
    body = ask.json()
    assert body["answer"]
    assert body["sources"]
