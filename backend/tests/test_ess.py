"""Portal self-service karyawan (/me/*): hanya data milik akun login sendiri."""

from unittest.mock import patch
from uuid import UUID

from tests.conftest import _auth_header, _platform_admin_header

KARYAWAN_EMAIL = "karyawan@outsourcing.co.id"


def _create_karyawan(client, email: str = KARYAWAN_EMAIL) -> dict[str, str]:
    """Buat akun role karyawan (dibuat oleh HR/admin) lalu login."""
    return _create_account(client, email, role="karyawan")


def _create_account(client, email: str, role: str = "karyawan") -> dict[str, str]:
    """Buat akun tenant dengan role tertentu langsung via DB lalu login."""
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        create_user(
            db,
            UserCreate(
                email=email,
                full_name=f"Akun {role}",
                password="rahasia-123",
                role=role,
            ),
            tenant_id=tenant.id,
        )
    finally:
        db.close()
    return _login_header(client, email)


def _get_user_id(client, email: str):
    from app.modules.auth.service import get_by_email

    db = client.testing_session()
    try:
        return get_by_email(db, email).id
    finally:
        db.close()


def _login_header(client, email: str) -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "rahasia-123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _link_employee(client, employee_id: str, email: str = KARYAWAN_EMAIL) -> None:
    """Tautkan akun karyawan ke data karyawan (normalnya dilakukan HR)."""
    from app.modules.auth.service import get_by_email
    from app.modules.hrd.models import Employee

    db = client.testing_session()
    try:
        user = get_by_email(db, email)
        employee = db.get(Employee, UUID(employee_id))
        assert user is not None and employee is not None
        employee.user_id = user.id
        db.commit()
    finally:
        db.close()


def _upload_document(client, headers, employee_id: str, title: str = "KTP") -> dict:
    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = "key"
        resp = client.post(
            f"/api/v1/employees/{employee_id}/documents",
            headers=headers,
            files={"file": ("ktp.jpg", b"fake-jpeg", "image/jpeg")},
            data={"document_type": "ktp", "title": title},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_portal_requires_linked_employee(client):
    headers = _create_karyawan(client)
    resp = client.get("/api/v1/me/profile", headers=headers)
    assert resp.status_code == 404
    assert "tertaut" in resp.json()["detail"]


def test_profile_contracts_documents_for_owner(client):
    admin = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Karyawan Portal"}
    ).json()

    contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=admin,
        json={"start_date": "2026-01-01"},
    )
    assert contract.status_code == 201, contract.text
    contract_id = contract.json()["id"]

    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = "key"
        uploaded = client.post(
            f"/api/v1/employees/contracts/{contract_id}/file",
            headers=admin,
            files={"file": ("kontrak.pdf", b"%PDF-1.4 kontrak", "application/pdf")},
        )
    assert uploaded.status_code == 200, uploaded.text

    doc = _upload_document(client, admin, emp["id"])
    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])

    profile = client.get("/api/v1/me/profile", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["full_name"] == "Karyawan Portal"
    assert body["status"] == "aktif"

    contracts = client.get("/api/v1/me/contracts", headers=headers).json()
    assert [c["id"] for c in contracts] == [contract_id]

    url = client.get(f"/api/v1/me/contracts/{contract_id}/download-url", headers=headers)
    assert url.status_code == 200
    assert url.json()["url"].startswith("/api/v1/files/")

    docs = client.get("/api/v1/me/documents", headers=headers).json()
    assert [d["id"] for d in docs] == [doc["id"]]
    doc_url = client.get(f"/api/v1/me/documents/{doc['id']}/download-url", headers=headers)
    assert doc_url.status_code == 200


def test_portal_cannot_access_other_employee_resources(client):
    admin = _auth_header(client)

    own = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Pemilik Portal"}
    ).json()
    headers = _create_karyawan(client)
    _link_employee(client, own["id"])

    other = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Karyawan Lain"}
    ).json()
    other_doc = _upload_document(client, admin, other["id"], title="Dokumen orang lain")

    contract = client.post(
        f"/api/v1/employees/{other['id']}/contracts",
        headers=admin,
        json={"start_date": "2026-01-01"},
    ).json()

    assert (
        client.get(
            f"/api/v1/me/documents/{other_doc['id']}/download-url", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/me/contracts/{contract['id']}/download-url", headers=headers
        ).status_code
        == 404
    )


def test_payslips_only_from_finalized_runs(client):
    admin = _auth_header(client)
    emp = client.post(
        "/api/v1/employees",
        headers=admin,
        json={"full_name": "Karyawan Gaji", "base_salary": 6_000_000},
    ).json()
    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])

    run = client.post("/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 7}).json()
    slips = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})
    assert slips.status_code == 201, slips.text

    # Run masih draft → slip belum boleh terlihat oleh karyawan.
    assert client.get("/api/v1/me/payslips", headers=headers).json() == []

    finalized = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)
    assert finalized.status_code == 200, finalized.text

    mine = client.get("/api/v1/me/payslips", headers=headers).json()
    assert len(mine) == 1
    assert mine[0]["year"] == 2026
    assert mine[0]["month"] == 7
    assert float(mine[0]["gross"]) == 6_000_000
    assert float(mine[0]["net_pay"]) == 6_000_000 - float(mine[0]["tax_pph21"])


# ---------- Jatah cuti tahunan (kuota) ----------


def test_leave_balance_flow(client):
    admin = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Pemegang Kuota"}
    ).json()
    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])

    # HR mengatur jatah 12 hari untuk 2026
    set_balance = client.post(
        f"/api/v1/employees/{emp['id']}/leave-balance",
        headers=admin,
        json={"year": 2026, "total_days": 12},
    )
    assert set_balance.status_code == 200, set_balance.text
    assert set_balance.json()["remaining"] == 12

    # portal melihat jatahnya sendiri
    mine = client.get("/api/v1/me/leave-balance", headers=headers, params={"year": 2026}).json()
    assert mine["total_days"] == 12 and mine["used_days"] == 0

    # cuti tahunan 3 hari → approve memotong kuota
    annual = client.post(
        "/api/v1/me/leave-requests",
        headers=headers,
        json={"leave_type": "cuti_tahunan", "start_date": "2026-09-01", "end_date": "2026-09-03"},
    )
    assert annual.status_code == 201, annual.text
    approved = client.patch(
        f"/api/v1/employees/leave-requests/{annual.json()['id']}/decision",
        headers=admin,
        json={"approved": True},
    )
    assert approved.status_code == 200, approved.text
    after = client.get("/api/v1/me/leave-balance", headers=headers, params={"year": 2026}).json()
    assert after["used_days"] == 3
    assert after["remaining"] == 9

    # izin tidak memotong kuota
    permission = client.post(
        "/api/v1/me/leave-requests",
        headers=headers,
        json={"leave_type": "izin", "start_date": "2026-10-01", "end_date": "2026-10-02"},
    )
    assert permission.status_code == 201
    ok = client.patch(
        f"/api/v1/employees/leave-requests/{permission.json()['id']}/decision",
        headers=admin,
        json={"approved": True},
    )
    assert ok.status_code == 200
    still = client.get("/api/v1/me/leave-balance", headers=headers, params={"year": 2026}).json()
    assert still["used_days"] == 3

    # cuti melebihi sisa kuota ditolak saat approval, status tetap menunggu
    big = client.post(
        "/api/v1/me/leave-requests",
        headers=headers,
        json={
            "leave_type": "cuti_tahunan",
            "start_date": "2026-11-02",
            "end_date": "2026-11-20",
        },
    )
    assert big.status_code == 201
    rejected_approval = client.patch(
        f"/api/v1/employees/leave-requests/{big.json()['id']}/decision",
        headers=admin,
        json={"approved": True},
    )
    assert rejected_approval.status_code == 422
    assert "tidak cukup" in rejected_approval.json()["detail"]
    pending = client.get(
        "/api/v1/employees/leave-requests", headers=admin, params={"status": "menunggu"}
    ).json()
    assert [row["id"] for row in pending] == [big.json()["id"]]

    # HR menaikkan jatah menjadi 25 hari lalu approval berhasil
    raised = client.post(
        f"/api/v1/employees/{emp['id']}/leave-balance",
        headers=admin,
        json={"year": 2026, "total_days": 25},
    )
    assert raised.status_code == 200
    assert raised.json()["remaining"] == 22
    approved_again = client.patch(
        f"/api/v1/employees/leave-requests/{big.json()['id']}/decision",
        headers=admin,
        json={"approved": True},
    )
    assert approved_again.status_code == 200
    final = client.get("/api/v1/me/leave-balance", headers=headers, params={"year": 2026}).json()
    assert final["used_days"] == 22

    # jatah baru di bawah pemakaian ditolak
    too_small = client.post(
        f"/api/v1/employees/{emp['id']}/leave-balance",
        headers=admin,
        json={"year": 2026, "total_days": 5},
    )
    assert too_small.status_code == 422


def test_annual_leave_without_balance_still_allowed(client):
    """Tanpa baris balance, approval cuti tahunan tidak dibatasi (opt-in HR)."""
    admin = _auth_header(client)
    emp = client.post("/api/v1/employees", headers=admin, json={"full_name": "Tanpa Kuota"}).json()
    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])

    none_balance = client.get("/api/v1/me/leave-balance", headers=headers, params={"year": 2030})
    assert none_balance.status_code == 200
    assert none_balance.json() is None

    req = client.post(
        "/api/v1/me/leave-requests",
        headers=headers,
        json={
            "leave_type": "cuti_tahunan",
            "start_date": "2030-01-02",
            "end_date": "2030-01-31",
        },
    )
    assert req.status_code == 201
    decided = client.patch(
        f"/api/v1/employees/leave-requests/{req.json()['id']}/decision",
        headers=admin,
        json={"approved": True},
    )
    assert decided.status_code == 200


def test_platform_admin_blocked_from_portal(client):
    headers = _platform_admin_header(client)
    assert client.get("/api/v1/me/profile", headers=headers).status_code == 403


# ---------- HR mengelola akun self-service ----------


def test_hr_links_and_unlinks_selfservice_account(client):
    admin = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Karyawan Tertaut"}
    ).json()
    _create_karyawan(client)

    available = client.get("/api/v1/employees/selfservice-accounts", headers=admin).json()
    assert [a["email"] for a in available] == [KARYAWAN_EMAIL]
    user_id = _get_user_id(client, KARYAWAN_EMAIL)

    linked = client.patch(
        f"/api/v1/employees/{emp['id']}", headers=admin, json={"user_id": str(user_id)}
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["user_id"] == str(user_id)
    assert client.get("/api/v1/employees/selfservice-accounts", headers=admin).json() == []

    # akun yang sama tidak bisa dipakai karyawan lain
    other = client.post("/api/v1/employees", headers=admin, json={"full_name": "Lain"}).json()
    dup = client.patch(
        f"/api/v1/employees/{other['id']}", headers=admin, json={"user_id": str(user_id)}
    )
    assert dup.status_code == 409

    # role selain karyawan ditolak
    admin2_id = _get_user_id(client, "brian@outsourcing.co.id")
    bad_role = client.patch(
        f"/api/v1/employees/{other['id']}", headers=admin, json={"user_id": str(admin2_id)}
    )
    assert bad_role.status_code == 422

    # lepas tautan → akun tersedia lagi
    unlink = client.patch(f"/api/v1/employees/{emp['id']}", headers=admin, json={"user_id": None})
    assert unlink.status_code == 200
    assert unlink.json()["user_id"] is None
    again = client.get("/api/v1/employees/selfservice-accounts", headers=admin).json()
    assert [a["email"] for a in again] == [KARYAWAN_EMAIL]


def test_portal_active_after_hr_link(client):
    """Setelah HR menautkan akun, portal langsung bisa dipakai tanpa DB manual."""
    admin = _auth_header(client)
    emp = client.post("/api/v1/employees", headers=admin, json={"full_name": "Aktif via UI"}).json()
    headers = _create_karyawan(client)
    # sebelum ditautkan portal menolak
    assert client.get("/api/v1/me/profile", headers=headers).status_code == 404

    linked = client.patch(
        f"/api/v1/employees/{emp['id']}",
        headers=admin,
        json={"user_id": str(_get_user_id(client, KARYAWAN_EMAIL))},
    )
    assert linked.status_code == 200, linked.text
    profile = client.get("/api/v1/me/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Aktif via UI"


# ---------- Pengajuan cuti/izin ----------


def _submit_leave(client, headers, start="2026-09-01", end="2026-09-02", **overrides):
    body = {"leave_type": "izin", "start_date": start, "end_date": end, "reason": "Urusan keluarga"}
    body.update(overrides)
    return client.post("/api/v1/me/leave-requests", headers=headers, json=body)


def test_leave_request_flow_submit_decide_cancel(client):
    admin = _auth_header(client)
    emp = client.post("/api/v1/employees", headers=admin, json={"full_name": "Pemohon Cuti"}).json()
    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])

    created = _submit_leave(client, headers)
    assert created.status_code == 201, created.text
    leave = created.json()
    assert leave["status"] == "menunggu"
    leave_id = leave["id"]

    # tanggal terbalik ditolak
    assert _submit_leave(client, headers, end="2026-08-01").status_code == 422
    # tumpang-tindih dengan pengajuan pending/approved ditolak
    overlap = _submit_leave(client, headers, start="2026-09-02", end="2026-09-03")
    assert overlap.status_code == 409
    # di luar rentang tumpang tindih boleh
    second = _submit_leave(client, headers, start="2026-10-01", end="2026-10-02")
    assert second.status_code == 201, second.text

    # karyawan tidak punya wewenang memutuskan
    forbidden = client.patch(
        f"/api/v1/employees/leave-requests/{leave_id}/decision",
        headers=headers,
        json={"approved": True},
    )
    assert forbidden.status_code in (401, 403)

    # HR menyetujui pengajuan pertama
    decided = client.patch(
        f"/api/v1/employees/leave-requests/{leave_id}/decision",
        headers=admin,
        json={"approved": True, "note": "Disetujui HR"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "disetujui"
    assert decided.json()["decided_at"] is not None

    # keputusan ulang ditolak; cuti yang sudah disetujui tak bisa dibatalkan sendiri
    assert (
        client.patch(
            f"/api/v1/employees/leave-requests/{leave_id}/decision",
            headers=admin,
            json={"approved": False},
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/v1/me/leave-requests/{leave_id}/cancel", headers=headers).status_code
        == 409
    )

    # karyawan membatalkan pengajuan kedua yang masih pending
    cancelled = client.post(
        f"/api/v1/me/leave-requests/{second.json()['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "dibatalkan"

    # daftar milik sendiri terurut terbaru dulu + filter status sisi HR
    mine = client.get("/api/v1/me/leave-requests", headers=headers).json()
    assert [row["status"] for row in mine] == ["dibatalkan", "disetujui"]
    approved_only = client.get(
        "/api/v1/employees/leave-requests",
        headers=admin,
        params={"status": "disetujui"},
    ).json()
    assert [row["id"] for row in approved_only] == [leave_id]


# ---------- Rekap absensi sendiri ----------


def test_my_attendance_visible_and_isolated(client):
    admin = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Punya Absensi"}
    ).json()
    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])

    upsert = client.post(
        "/api/v1/payroll/attendance",
        headers=admin,
        json={"employee_id": emp["id"], "year": 2026, "month": 8, "present_days": 21},
    )
    assert upsert.status_code == 201, upsert.text

    # rekap karyawan lain tidak bocor ke portal
    other = client.post(
        "/api/v1/employees", headers=admin, json={"full_name": "Rekan Kerja"}
    ).json()
    client.post(
        "/api/v1/payroll/attendance",
        headers=admin,
        json={"employee_id": other["id"], "year": 2026, "month": 8, "present_days": 10},
    )

    mine = client.get(
        "/api/v1/me/attendance", headers=headers, params={"year": 2026, "month": 8}
    ).json()
    assert len(mine) == 1
    assert mine[0]["present_days"] == 21
    assert mine[0]["client_approved"] is False
