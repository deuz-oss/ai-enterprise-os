from datetime import date, timedelta
from unittest.mock import patch

from tests.conftest import _auth_header


def _placement_id(client, headers) -> str:
    resp = client.post("/api/v1/clients", headers=headers, json={"name": "PT HRD Klien"})
    assert resp.status_code == 201, resp.text
    client_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": client_id, "title": "Operator Gudang", "headcount": 3},
    )
    assert resp.status_code == 201, resp.text
    jo_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={"full_name": "Citra Lestari", "phone": "081234567890"},
    )
    assert resp.status_code == 201, resp.text
    cand_id = resp.json()["id"]
    resp = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_onboard_from_placement_creates_employee(client):
    headers = _auth_header(client)
    pid = _placement_id(client, headers)

    resp = client.post(
        "/api/v1/employees/onboard",
        headers=headers,
        json={"placement_id": pid, "join_date": "2026-09-01"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["full_name"] == "Citra Lestari"
    assert body["employee_no"].startswith("EMP-")
    assert body["status"] == "aktif"
    assert body["phone"] == "081234567890"

    # onboard ganda untuk placement yang sama harus ditolak
    dup = client.post("/api/v1/employees/onboard", headers=headers, json={"placement_id": pid})
    assert dup.status_code == 409


def test_create_employee_generated_no_and_search(client):
    headers = _auth_header(client)
    first = client.post("/api/v1/employees", headers=headers, json={"full_name": "Budi Santoso"})
    assert first.status_code == 201, first.text
    assert first.json()["employee_no"].startswith("EMP-")

    client.post("/api/v1/employees", headers=headers, json={"full_name": "Ani Rahayu"})

    listed = client.get("/api/v1/employees", headers=headers, params={"q": "budi"}).json()
    assert len(listed) == 1
    assert listed[0]["full_name"] == "Budi Santoso"


def test_contract_lifecycle_sign_and_expiring(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Dewi Anggraini"}
    ).json()

    end_date = (date.today() + timedelta(days=20)).isoformat()
    created = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2026-01-01", "end_date": end_date},
    )
    assert created.status_code == 201, created.text
    contract = created.json()
    assert contract["contract_no"].startswith("KON/")
    assert contract["sign_status"] == "menunggu_ttd"

    # periode tidak valid harus ditolak
    bad = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2026-06-01", "end_date": "2026-01-01"},
    )
    assert bad.status_code == 422

    expiring = client.get(
        "/api/v1/employees/contracts/expiring",
        headers=headers,
        params={"within_days": 60},
    ).json()
    assert len(expiring) == 1
    assert expiring[0]["employee_name"] == "Dewi Anggraini"
    assert isinstance(expiring[0]["days_left"], int)

    signed = client.post(f"/api/v1/employees/contracts/{contract['id']}/sign", headers=headers)
    assert signed.status_code == 200
    assert signed.json()["sign_status"] == "ditandatangani"
    assert signed.json()["signed_at"] is not None

    again = client.post(f"/api/v1/employees/contracts/{contract['id']}/sign", headers=headers)
    assert again.status_code == 409


def test_upload_hr_document_versions(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Eko Prasetyo"}
    ).json()

    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = "key"
        ktp1 = client.post(
            f"/api/v1/employees/{emp['id']}/documents",
            headers=headers,
            files={"file": ("ktp-scan.jpg", b"fake-jpeg", "image/jpeg")},
            data={"document_type": "ktp", "title": "KTP Eko"},
        )
        ktp2 = client.post(
            f"/api/v1/employees/{emp['id']}/documents",
            headers=headers,
            files={"file": ("ktp-rescan.jpg", b"fake-jpeg-2", "image/jpeg")},
            data={"document_type": "ktp", "title": "KTP Eko ulang"},
        )
        bpjs = client.post(
            f"/api/v1/employees/{emp['id']}/documents",
            headers=headers,
            files={"file": ("bpjs.pdf", b"%PDF-1.4 bpjs", "application/pdf")},
            data={"document_type": "bpjs_kesehatan", "title": "Kartu BPJS"},
        )

    assert ktp1.status_code == 201 and ktp2.status_code == 201 and bpjs.status_code == 201
    assert ktp1.json()["version"] == 1
    assert ktp2.json()["version"] == 2
    assert bpjs.json()["version"] == 1

    docs = client.get(f"/api/v1/employees/{emp['id']}/documents", headers=headers).json()
    assert len(docs) == 3


def test_insurance_crud_and_bpjs_card_status(client):
    """PRD v3.0 §5 — asuransi one-to-many + BPJS status/kartu/valid_until (Employees.tsx)."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Insurance Test"}
    ).json()

    created = client.post(
        f"/api/v1/employees/{emp['id']}/insurances",
        headers=headers,
        json={"provider": "prudential", "policy_no": "POL-001", "start_date": "2026-01-01"},
    )
    assert created.status_code == 201, created.text
    ins = created.json()
    assert ins["status"] == "aktif"

    updated = client.patch(
        f"/api/v1/employees/insurances/{ins['id']}",
        headers=headers,
        json={"status": "kedaluwarsa", "valid_until": "2026-12-31"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "kedaluwarsa"
    assert updated.json()["valid_until"] == "2026-12-31"

    listed = client.get(f"/api/v1/employees/{emp['id']}/insurances", headers=headers).json()
    assert len(listed) == 1

    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = "key"
        card = client.post(
            f"/api/v1/employees/insurances/{ins['id']}/card",
            headers=headers,
            files={"file": ("polis.jpg", b"fake-jpeg", "image/jpeg")},
        )
    assert card.status_code == 201, card.text
    assert card.json()["card_object_key"]

    with patch("app.modules.hrd.service.storage.presigned_get_url") as presign:
        presign.return_value = "https://example.com/signed"
        url = client.get(
            f"/api/v1/employees/insurances/{ins['id']}/card/download-url", headers=headers
        )
    assert url.status_code == 200
    assert url.json()["url"] == "https://example.com/signed"

    deleted = client.delete(f"/api/v1/employees/insurances/{ins['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/employees/{emp['id']}/insurances", headers=headers).json() == []


def test_bpjs_card_upload_and_status_valid_until(client):
    headers = _auth_header(client)
    emp = client.post("/api/v1/employees", headers=headers, json={"full_name": "BPJS Test"}).json()

    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = "key"
        card = client.post(
            f"/api/v1/employees/{emp['id']}/bpjs-card",
            headers=headers,
            files={"file": ("kartu.jpg", b"fake-jpeg", "image/jpeg")},
            data={"bpjs_type": "kesehatan", "valid_until": "2027-01-31"},
        )
    assert card.status_code == 201, card.text
    assert card.json()["bpjs_kesehatan_card_key"]
    assert card.json()["bpjs_kesehatan_valid_until"] == "2027-01-31"

    status_update = client.patch(
        f"/api/v1/employees/{emp['id']}",
        headers=headers,
        json={"bpjs_kesehatan_status": "aktif", "bpjs_ketenagakerjaan_status": "menunggu"},
    )
    assert status_update.status_code == 200, status_update.text
    body = status_update.json()
    assert body["bpjs_kesehatan_status"] == "aktif"
    assert body["bpjs_ketenagakerjaan_status"] == "menunggu"


def test_hr_endpoints_reject_non_admin_role(client):
    """Role recruiter tidak boleh akses modul HRD (hanya hr/management/admin)."""
    db = client.testing_session()
    try:
        from app.modules.auth.schemas import UserCreate
        from app.modules.auth.service import create_user

        create_user(
            db,
            UserCreate(
                email="recruiter@outsourcing.co.id",
                full_name="Rina",
                password="rahasia-123",
                role="recruiter",
            ),
        )
    finally:
        db.close()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "recruiter@outsourcing.co.id", "password": "rahasia-123"},
    )
    token = login.json()["access_token"]
    resp = client.get("/api/v1/employees", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
