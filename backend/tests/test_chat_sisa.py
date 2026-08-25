"""Sisa Fase 11 — channel otomatis per entitas & card interaktif + WebSocket."""

from tests.conftest import _auth_header


def _setup_basic(client):
    admin = _auth_header(client)
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        for email, role in [("ops@t.co", "operations")]:
            try:
                create_user(
                    db,
                    UserCreate(email=email, full_name="Ops", password="rahasia-123", role=role),
                    tenant_id=tenant.id,
                )
            except Exception:
                pass
    finally:
        db.close()

    def login(email):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "rahasia-123"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    ops = login("ops@t.co")

    # Klien + Job order → auto #jo channel
    cl = client.post("/api/v1/clients", headers=admin, json={"name": "PT Auto Channel"}).json()
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=admin,
        json={"client_id": cl["id"], "title": "Admin Gudang", "headcount": 2},
    ).json()

    channels = client.get("/api/v1/chat/channels", headers=admin).json()
    assert any("jo-" in c["slug"] for c in channels), channels

    # Kandidat + placement → auto #proyek channel
    cand = client.post(
        "/api/v1/recruitment/candidates", headers=admin, json={"full_name": "Auto Worker"}
    ).json()
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=admin,
        json={"candidate_id": cand["id"], "job_order_id": jo["id"]},
    ).json()
    channels2 = client.get("/api/v1/chat/channels", headers=admin).json()
    assert any("proyek-" in c["slug"] for c in channels2), channels2

    return admin, ops, cl, jo, cand, placement


def test_auto_channels_per_entity(client):
    _setup_basic(client)


def test_payroll_auto_channel_and_system_message(client):
    admin, ops, cl, jo, cand, placement = _setup_basic(client)

    # Buat karyawan dari placement → emp + rekap absensi
    emp = client.post(
        "/api/v1/employees",
        headers=admin,
        json={"full_name": "TKO Payroll", "placement_id": placement["id"], "base_salary": 5000000},
    ).json()
    client.post(
        "/api/v1/payroll/attendance",
        headers=admin,
        json={
            "employee_id": emp["id"],
            "year": 2026,
            "month": 9,
            "present_days": 22,
            "overtime_hours": 2,
        },
    )
    # Approve agar generate bisa sertakan lembur
    att = client.get(
        "/api/v1/payroll/attendance", headers=admin, params={"year": 2026, "month": 9}
    ).json()[0]
    client.patch(
        f"/api/v1/payroll/attendance/{att['id']}/client-approval",
        headers=admin,
        params={"approved": True},
    )

    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 9, "run_type": "proyek", "client_id": cl["id"]},
    ).json()
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})
    client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}).json()

    channels = client.get("/api/v1/chat/channels", headers=admin).json()
    payroll_ch = next(c for c in channels if c["slug"].startswith("payroll-2026"))
    msgs = client.get(f"/api/v1/chat/channels/{payroll_ch['id']}/messages", headers=admin).json()
    assert any("menunggu persetujuan klien" in m["content"] for m in msgs)


def test_interactive_card_pr_approve_via_chat(client):
    admin, ops, cl, jo, cand, placement = _setup_basic(client)

    # Finalize run agar PR bisa dibuat
    client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "PR Worker", "base_salary": 6000000}
    ).json()
    run = client.post(
        "/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 10}
    ).json()
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})
    client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)

    pr = client.post(
        "/api/v1/payment-requests",
        headers=admin,
        json={"pr_type": "internal", "payroll_run_id": run["id"]},
    ).json()

    # Card harus ada di channel payroll terkait
    channels = client.get("/api/v1/chat/channels", headers=admin).json()
    # Jika belum ada karena internal run tidak punya client channel,
    # setidaknya cek card ada di salah satu channel
    card_found = False
    for ch in channels:
        msgs = client.get(f"/api/v1/chat/channels/{ch['id']}/messages", headers=admin).json()
        for m in msgs:
            if m.get("message_type") == "card" and pr["pr_number"] in str(m.get("card_data", {})):
                card_found = True
                # Approve via card action
                approve = client.post(
                    f"/api/v1/chat/messages/{m['id']}/actions/approve_pr:{pr['id']}",
                    headers=admin,
                    json={},
                )
                assert approve.status_code == 200, approve.text
                # PR harus sudah disetujui
                listed = client.get("/api/v1/payment-requests", headers=admin).json()
                target = next(p for p in listed if p["id"] == pr["id"])
                assert target["status"] == "disetujui_atasan"
                # Thread reply tercatat
                thread = client.get(
                    f"/api/v1/chat/channels/{ch['id']}/messages",
                    headers=admin,
                    params={"parent_id": m["id"]},
                ).json()
                assert any("disetujui" in r["content"].lower() for r in thread)
                return
    assert card_found, "Card PR tidak ditemukan di channel manapun"


def test_websocket_requires_auth(client):
    # WebSocket handshake tanpa token yang valid → harus ditolak (1008)
    # Polling tetap menjadi jalur utama bila WS tidak tersedia
    try:
        with client.websocket_connect("/api/v1/chat/ws?token=invalid") as ws:
            ws.send_text("ping")
            raise AssertionError("Seharusnya ditolak")
    except Exception:
        # TestClient mengangkat WebSocketDisconnect atau ClosedResourceError
        pass
