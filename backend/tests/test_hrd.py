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


def test_onboard_copies_identity_fields_from_candidate(client):
    """Tier 1/2 gap-fill: birthdate/gender/education/current_position/
    blood_type/birthplace disalin dari Candidate saat onboarding (bukan
    ditinggal begitu saja seperti sebelum perbaikan ini)."""
    headers = _auth_header(client)
    client_resp = client.post(
        "/api/v1/clients", headers=headers, json={"name": "PT Identity Klien"}
    )
    client_id = client_resp.json()["id"]
    jo = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={"client_id": client_id, "title": "Staff Gudang", "headcount": 1},
    ).json()
    cand = client.post(
        "/api/v1/recruitment/candidates",
        headers=headers,
        json={
            "full_name": "Gita Permata",
            "phone": "081211110000",
            "email": "gita@contoh.co.id",
            "gender": "Perempuan",
            "birthdate": "1997-03-10",
            "birthplace": "Bandung",
            "blood_type": "O",
            "education": "S1 Akuntansi",
            "current_position": "Staff Admin",
        },
    ).json()
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand["id"], "job_order_id": jo["id"]},
    ).json()

    onboarded = client.post(
        "/api/v1/employees/onboard", headers=headers, json={"placement_id": placement["id"]}
    )
    assert onboarded.status_code == 201, onboarded.text
    body = onboarded.json()
    assert body["email"] == "gita@contoh.co.id"
    assert body["gender"] == "Perempuan"
    assert body["birthdate"] == "1997-03-10"
    assert body["birthplace"] == "Bandung"
    assert body["blood_type"] == "O"
    assert body["education"] == "S1 Akuntansi"
    assert body["current_position"] == "Staff Admin"


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


def test_contract_extend_builds_renewal_chain(client):
    """Tier 2 gap-fill (audit MYOHRIS "Extensions"): kontrak bisa diperpanjang,
    membentuk rantai riwayat lewat `previous_contract_id`."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Farah Yuliana"}
    ).json()

    original = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2026-01-01", "end_date": "2026-06-30"},
    ).json()
    assert original["previous_contract_id"] is None

    extended = client.post(
        f"/api/v1/employees/contracts/{original['id']}/extend",
        headers=headers,
        json={"start_date": "2026-07-01", "end_date": "2026-12-31"},
    )
    assert extended.status_code == 201, extended.text
    extended_body = extended.json()
    assert extended_body["previous_contract_id"] == original["id"]
    assert extended_body["contract_no"].startswith("KON/")

    # Kontrak yang sudah diperpanjang tidak boleh diperpanjang lagi langsung --
    # harus lewat kontrak perpanjangan terakhir.
    again = client.post(
        f"/api/v1/employees/contracts/{original['id']}/extend",
        headers=headers,
        json={"start_date": "2027-01-01", "end_date": "2027-06-30"},
    )
    assert again.status_code == 409

    # Tapi memperpanjang kontrak perpanjangan terakhir itu sendiri boleh.
    chained = client.post(
        f"/api/v1/employees/contracts/{extended_body['id']}/extend",
        headers=headers,
        json={"start_date": "2027-01-01", "end_date": "2027-06-30"},
    )
    assert chained.status_code == 201, chained.text
    assert chained.json()["previous_contract_id"] == extended_body["id"]

    listed = client.get(f"/api/v1/employees/{emp['id']}/contracts", headers=headers).json()
    assert len(listed) == 3


def test_double_extension_blocked_even_via_plain_create_endpoint(client):
    """Cek-gap: `previous_contract_id` adalah field publik di ContractCreate,
    jadi guard "cuma kontrak terbaru boleh diperpanjang" harus tetap
    tertegak walau dilewati lewat POST /{employee_id}/contracts biasa
    (bukan lewat /extend) -- sebelumnya guard ini cuma ada di fungsi
    extend_contract, jadi bisa dilewati begitu saja lewat endpoint lain."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Karim Hidayat"}
    ).json()

    original = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2026-01-01", "end_date": "2026-06-30"},
    ).json()
    first_extension = client.post(
        f"/api/v1/employees/contracts/{original['id']}/extend",
        headers=headers,
        json={"start_date": "2026-07-01", "end_date": "2026-12-31"},
    ).json()

    # Coba bikin cabang kedua dari kontrak yang sama, lewat POST biasa
    # (bukan /extend) dengan previous_contract_id ditulis manual di body.
    branch_attempt = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={
            "start_date": "2026-07-01",
            "end_date": "2026-12-31",
            "previous_contract_id": original["id"],
        },
    )
    assert branch_attempt.status_code == 409
    assert "sudah pernah diperpanjang" in branch_attempt.json()["detail"]

    listed = client.get(f"/api/v1/employees/{emp['id']}/contracts", headers=headers).json()
    assert len(listed) == 2
    assert first_extension["id"] in [c["id"] for c in listed]


def test_cannot_link_previous_contract_from_another_employee(client):
    """Cek-gap: previous_contract_id ditulis lewat POST biasa tanpa validasi
    employee_id-nya cocok -- tanpa guard ini bisa membuat rantai kontrak
    lintas karyawan (kontrak milik karyawan A tercatat "perpanjangan dari"
    kontrak milik karyawan B)."""
    headers = _auth_header(client)
    emp_a = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Lestari Wijaya"}
    ).json()
    emp_b = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Maulana Rizki"}
    ).json()

    contract_b = client.post(
        f"/api/v1/employees/{emp_b['id']}/contracts",
        headers=headers,
        json={"start_date": "2026-01-01", "end_date": "2026-06-30"},
    ).json()

    cross_link = client.post(
        f"/api/v1/employees/{emp_a['id']}/contracts",
        headers=headers,
        json={
            "start_date": "2026-07-01",
            "end_date": "2026-12-31",
            "previous_contract_id": contract_b["id"],
        },
    )
    assert cross_link.status_code == 422
    assert "bukan milik karyawan ini" in cross_link.json()["detail"]


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


def test_insurance_file_size_limits_differ_card_vs_policy(client):
    """PRD v3.0 §5 — kartu ≤5MB, polis ≤10MB (bukan flat 10MB untuk keduanya)."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "File Limit Test"}
    ).json()
    ins = client.post(
        f"/api/v1/employees/{emp['id']}/insurances",
        headers=headers,
        json={"provider": "axa", "policy_no": "POL-LIMIT"},
    ).json()

    oversized_for_card = b"x" * (6 * 1024 * 1024)  # >5MB, <=10MB
    card = client.post(
        f"/api/v1/employees/insurances/{ins['id']}/card",
        headers=headers,
        files={"file": ("kartu.jpg", oversized_for_card, "image/jpeg")},
    )
    assert card.status_code == 413, card.text

    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = "key"
        policy = client.post(
            f"/api/v1/employees/insurances/{ins['id']}/policy",
            headers=headers,
            files={"file": ("polis.pdf", oversized_for_card, "application/pdf")},
        )
    assert policy.status_code == 201, policy.text  # 6MB tetap OK untuk polis (limit 10MB)


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


def _operations_header(client) -> dict[str, str]:
    db = client.testing_session()
    try:
        from app.modules.auth.schemas import UserCreate
        from app.modules.auth.service import create_user

        create_user(
            db,
            UserCreate(
                email="ops-fase23@outsourcing.co.id",
                full_name="Ops",
                password="rahasia-123",
                role="operations",
            ),
        )
    finally:
        db.close()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ops-fase23@outsourcing.co.id", "password": "rahasia-123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_operations_role_sees_only_external_employees(client):
    """Fase 23 butir 1 -- sebelumnya Ops sama sekali tidak bisa akses modul
    karyawan; sekarang boleh, tapi dibatasi ke karyawan eksternal saja."""
    headers = _auth_header(client)
    internal = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": "Karyawan Internal", "employment_type": "internal"},
    ).json()
    external = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": "Karyawan Eksternal", "employment_type": "eksternal"},
    ).json()

    ops_headers = _operations_header(client)

    listed = client.get("/api/v1/employees", headers=ops_headers)
    assert listed.status_code == 200, listed.text
    names = [row["full_name"] for row in listed.json()]
    assert "Karyawan Eksternal" in names
    assert "Karyawan Internal" not in names

    visible = client.get(f"/api/v1/employees/{external['id']}", headers=ops_headers)
    assert visible.status_code == 200

    hidden = client.get(f"/api/v1/employees/{internal['id']}", headers=ops_headers)
    assert hidden.status_code == 404

    # Ops tidak boleh akses endpoint HRD administratif lain (di router terpisah).
    forbidden = client.get(f"/api/v1/employees/{external['id']}/contracts", headers=ops_headers)
    assert forbidden.status_code == 403


def test_warning_letter_valid_until_computed(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Ferdi Wibowo"}
    ).json()

    created = client.post(
        f"/api/v1/employees/{emp['id']}/warning-letters",
        headers=headers,
        data={"letter_type": "sp1", "reason": "Terlambat berulang", "issued_at": "2026-01-15"},
    )
    assert created.status_code == 201, created.text
    letter = created.json()
    assert letter["valid_until"] == "2026-07-14"
    assert letter["is_active"] is False  # sudah lewat 2026-09-04 (tanggal berjalan tes)

    listed = client.get(f"/api/v1/employees/{emp['id']}/warning-letters", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_contract_template_crud(client):
    headers = _auth_header(client)
    created = client.post(
        "/api/v1/employees/contract-templates",
        headers=headers,
        json={
            "name": "Kontrak PKWT Standar",
            "field_schema": [
                {"key": "posisi", "label": "Posisi", "type": "text"},
                {
                    "key": "klausul",
                    "label": "Ketentuan Kerja",
                    "type": "list",
                    "list_style": "numeric",
                },
            ],
            "footer_text": "Dokumen internal",
        },
    )
    assert created.status_code == 201, created.text
    tmpl = created.json()
    assert tmpl["field_schema"][1]["type"] == "list"
    assert tmpl["is_active"] is True

    listed = client.get("/api/v1/employees/contract-templates", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/v1/employees/contract-templates/{tmpl['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def test_generate_contract_document_with_numeric_and_alpha_list_fields(client):
    """Fase 25 -- klausul kontrak bernomor/alfabet, ground baru yang belum
    ada di render_document_docx sebelum Fase 25 (Agreement Fase 20 cuma
    pakai value string flat, tidak pernah list)."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Lupita Sari"}
    ).json()
    contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2026-01-01"},
    ).json()

    tmpl = client.post(
        "/api/v1/employees/contract-templates",
        headers=headers,
        json={
            "name": "Kontrak Generate Test",
            "field_schema": [
                {"key": "posisi", "label": "Posisi", "type": "text"},
                {
                    "key": "tugas",
                    "label": "Uraian Tugas",
                    "type": "list",
                    "list_style": "numeric",
                },
                {
                    "key": "lampiran",
                    "label": "Daftar Lampiran",
                    "type": "list",
                    "list_style": "alpha",
                },
            ],
        },
    ).json()

    generated = client.post(
        f"/api/v1/employees/contracts/{contract['id']}/generate-document",
        headers=headers,
        json={
            "template_id": tmpl["id"],
            "field_values": {
                "posisi": "Staff Admin",
                "tugas": ["Input data", "Rekap laporan"],
                "lampiran": ["Fotokopi KTP", "Ijazah"],
            },
        },
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["template_id"] == tmpl["id"]
    assert body["file_name"].endswith(".docx")

    dl = client.get(f"/api/v1/employees/contracts/{contract['id']}/download-url", headers=headers)
    assert dl.status_code == 200
    file_resp = client.get(dl.json()["url"])
    assert file_resp.status_code == 200

    import io

    from docx import Document

    doc = Document(io.BytesIO(file_resp.content))
    paragraphs = [p.text for p in doc.paragraphs]
    assert "1. Input data" in paragraphs
    assert "2. Rekap laporan" in paragraphs
    assert "a. Fotokopi KTP" in paragraphs
    assert "b. Ijazah" in paragraphs
    assert "Staff Admin" in paragraphs


def test_generate_contract_document_requires_existing_template(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Mahesa Putra"}
    ).json()
    contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts", headers=headers, json={}
    ).json()

    resp = client.post(
        f"/api/v1/employees/contracts/{contract['id']}/generate-document",
        headers=headers,
        json={"template_id": "00000000-0000-0000-0000-000000000000", "field_values": {}},
    )
    assert resp.status_code == 404


def test_employee_fase26_fields_roundtrip(client):
    headers = _auth_header(client)
    created = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "full_name": "Nadia Kusuma",
            "grade": "G3",
            "level": "Senior",
            "citizen_address": {"province": "Jawa Barat", "city": "Bandung"},
            "residential_address": {"province": "DKI Jakarta", "city": "Jakarta Selatan"},
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["grade"] == "G3"
    assert body["level"] == "Senior"
    assert body["citizen_address"] == {"province": "Jawa Barat", "city": "Bandung"}
    assert body["residential_address"] == {"province": "DKI Jakarta", "city": "Jakarta Selatan"}
    assert body["payroll_locked"] is False

    updated = client.patch(
        f"/api/v1/employees/{body['id']}",
        headers=headers,
        json={"grade": "G4", "residential_address": {"province": "Jawa Barat"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["grade"] == "G4"
    assert updated.json()["residential_address"] == {"province": "Jawa Barat"}


def test_employee_emergency_contacts_crud(client):
    """Kontak darurat one-to-many (dulu 3 kolom flat, hanya nampung satu)."""
    headers = _auth_header(client)
    emp = client.post("/api/v1/employees", headers=headers, json={"full_name": "Wulan Sari"}).json()

    empty = client.get(f"/api/v1/employees/{emp['id']}/emergency-contacts", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []

    first = client.post(
        f"/api/v1/employees/{emp['id']}/emergency-contacts",
        headers=headers,
        json={
            "name": "Budi Sari",
            "relation": "Suami",
            "phone": "081200000001",
            "is_primary": True,
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["is_primary"] is True

    second = client.post(
        f"/api/v1/employees/{emp['id']}/emergency-contacts",
        headers=headers,
        json={"name": "Ratna Sari", "relation": "Ibu", "phone": "081200000002", "is_primary": True},
    ).json()
    assert second["is_primary"] is True

    listed = client.get(f"/api/v1/employees/{emp['id']}/emergency-contacts", headers=headers).json()
    assert len(listed) == 2
    # Menandai kontak kedua utama otomatis melepas status utama kontak pertama.
    primaries = [c["is_primary"] for c in listed]
    assert primaries.count(True) == 1
    assert next(c for c in listed if c["id"] == second["id"])["is_primary"] is True

    patched = client.patch(
        f"/api/v1/employees/emergency-contacts/{second['id']}",
        headers=headers,
        json={"phone": "081299999999"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["phone"] == "081299999999"

    deleted = client.delete(
        f"/api/v1/employees/emergency-contacts/{first.json()['id']}", headers=headers
    )
    assert deleted.status_code == 204

    remaining = client.get(
        f"/api/v1/employees/{emp['id']}/emergency-contacts", headers=headers
    ).json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == second["id"]


def test_employee_movements_crud(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Oscar Putra"}
    ).json()

    created = client.post(
        f"/api/v1/employees/{emp['id']}/movements",
        headers=headers,
        json={
            "movement_type": "promosi",
            "previous_grade": "G2",
            "new_grade": "G3",
            "new_division": "Operations",
            "new_position": "Senior Staff",
            "effective_date": "2026-06-01",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["new_grade"] == "G3"

    listed = client.get(f"/api/v1/employees/{emp['id']}/movements", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # Tier 3 gap-fill: movement mensinkron field live di Employee, bukan
    # cuma jadi entri log yang tidak pernah dibaca ulang.
    refreshed = client.get(f"/api/v1/employees/{emp['id']}", headers=headers).json()
    assert refreshed["grade"] == "G3"
    assert refreshed["division"] == "Operations"
    assert refreshed["position"] == "Senior Staff"


def test_pkwt_duration_limit_enforced_across_extensions(client):
    """Tier 3 gap-fill: PKWT dibatasi total durasi 5 tahun TERMASUK semua
    perpanjangan (UU Cipta Kerja) -- dihitung dari tanggal mulai kontrak
    AWAL rantai, bukan kontrak perpanjangan terakhir."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Hasan Wibowo"}
    ).json()

    original = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2022-01-01", "end_date": "2024-12-31", "contract_type": "pkwt"},
    ).json()
    assert original["contract_type"] == "pkwt"

    # Perpanjangan ke 2026-12-31 -> total 5 tahun persis dari 2022-01-01, masih boleh.
    within_limit = client.post(
        f"/api/v1/employees/contracts/{original['id']}/extend",
        headers=headers,
        json={"start_date": "2025-01-01", "end_date": "2026-12-31"},
    )
    assert within_limit.status_code == 201, within_limit.text
    # contract_type diwarisi otomatis dari kontrak yang diperpanjang.
    assert within_limit.json()["contract_type"] == "pkwt"

    # Perpanjangan lagi sampai lewat 5 tahun (2027-01-01) harus ditolak.
    over_limit = client.post(
        f"/api/v1/employees/contracts/{within_limit.json()['id']}/extend",
        headers=headers,
        json={"start_date": "2027-01-01", "end_date": "2027-06-30"},
    )
    assert over_limit.status_code == 422
    assert "5 tahun" in over_limit.json()["detail"]

    # PKWTT tidak dibatasi -- kontrak baru & perpanjangan panjang harus lolos.
    permanent = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2020-01-01", "end_date": "2035-01-01", "contract_type": "pkwtt"},
    )
    assert permanent.status_code == 201, permanent.text


def test_pkwt_duration_limit_enforced_on_direct_update_too(client):
    """Cek-gap: validasi batas 5 tahun sebelumnya cuma jalan di
    create/extend -- PATCH /contracts/{id} bisa dipakai buat lompat lewat
    batas tanpa tervalidasi sama sekali (ubah end_date, atau tandai
    contract_type=pkwt belakangan pada kontrak yang durasinya sudah
    kelewat)."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Indra Kusuma"}
    ).json()

    contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2022-01-01", "end_date": "2024-12-31", "contract_type": "pkwt"},
    ).json()

    # PATCH end_date langsung melewati batas 5 tahun dari 2022-01-01 -> ditolak.
    over_limit = client.patch(
        f"/api/v1/employees/contracts/{contract['id']}",
        headers=headers,
        json={"end_date": "2027-06-30"},
    )
    assert over_limit.status_code == 422
    assert "5 tahun" in over_limit.json()["detail"]

    # Kontrak PKWTT lama yang durasinya sudah kelewat 5 tahun, ditandai PKWT
    # belakangan lewat PATCH -- juga harus ditolak, bukan cuma dibiarkan lolos.
    old_contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2018-01-01", "end_date": "2026-01-01"},
    ).json()
    retro_tag = client.patch(
        f"/api/v1/employees/contracts/{old_contract['id']}",
        headers=headers,
        json={"contract_type": "pkwt"},
    )
    assert retro_tag.status_code == 422
    assert "5 tahun" in retro_tag.json()["detail"]


def test_cannot_delete_contract_still_referenced_by_extension(client):
    """Cek-gap: menghapus kontrak yang sudah diperpanjang (dirujuk
    previous_contract_id kontrak lain) sebelumnya tidak dicegah sama sekali
    -- SQLite tidak menegakkan FK secara default, jadi hapus sukses diam-diam
    tapi meninggalkan previous_contract_id menggantung (rantai riwayat rusak
    tanpa error apa pun)."""
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Joko Santoso"}
    ).json()

    original = client.post(
        f"/api/v1/employees/{emp['id']}/contracts",
        headers=headers,
        json={"start_date": "2026-01-01", "end_date": "2026-06-30"},
    ).json()
    extended = client.post(
        f"/api/v1/employees/contracts/{original['id']}/extend",
        headers=headers,
        json={"start_date": "2026-07-01", "end_date": "2026-12-31"},
    ).json()

    blocked = client.delete(f"/api/v1/employees/contracts/{original['id']}", headers=headers)
    assert blocked.status_code == 409
    assert extended["contract_no"] in blocked.json()["detail"]

    # Kontrak yang TIDAK dirujuk siapa pun (ujung rantai) tetap boleh dihapus.
    allowed = client.delete(f"/api/v1/employees/contracts/{extended['id']}", headers=headers)
    assert allowed.status_code == 204


def test_vaccine_records_crud(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Putri Amelia"}
    ).json()

    created = client.post(
        f"/api/v1/employees/{emp['id']}/vaccine-records",
        headers=headers,
        json={"vaccine_name": "COVID-19 Booster", "dose_number": 3, "vaccinated_at": "2026-03-01"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["vaccine_name"] == "COVID-19 Booster"

    listed = client.get(f"/api/v1/employees/{emp['id']}/vaccine-records", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_employee_payroll_lock_toggle(client):
    headers = _auth_header(client)
    emp = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Qori Ramadhan"}
    ).json()

    locked = client.post(f"/api/v1/employees/{emp['id']}/payroll-lock", headers=headers)
    assert locked.status_code == 200, locked.text
    assert locked.json()["payroll_locked"] is True
    assert locked.json()["payroll_locked_at"] is not None

    unlocked = client.delete(f"/api/v1/employees/{emp['id']}/payroll-lock", headers=headers)
    assert unlocked.status_code == 200
    assert unlocked.json()["payroll_locked"] is False
    assert unlocked.json()["payroll_locked_at"] is None
