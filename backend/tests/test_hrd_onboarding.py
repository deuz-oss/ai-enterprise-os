"""Onboarding self-service kandidat via link ber-token (gap #4, 2026-09-06)."""

import io

from tests.conftest import _auth_header
from tests.test_hrd import _placement_id


def _create_invite(client, headers, days=14):
    pid = _placement_id(client, headers)
    resp = client.post(
        "/api/v1/employees/onboarding-invites",
        headers=headers,
        json={"placement_id": pid, "days": days},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    url = body["onboarding_url"]
    token = url.rsplit("/", 1)[-1]
    return body["invite"], token


def _submit_payload(**overrides):
    payload = {
        "phone": "081200000001",
        "ktp_no": "3201010101010001",
        "npwp_no": "09.123.456.7-890.000",
        "bank_name": "BCA",
        "bank_account": "1234567890",
        "marital_status": "tk",
        "dependents": 0,
        "emergency_contact_name": "Sari",
        "emergency_contact_relation": "Ibu",
        "emergency_contact_phone": "081200000002",
        "citizen_address": {
            "province": "DKI Jakarta",
            "city": "Jakarta Selatan",
            "detail": "Jl. A",
        },
        "residential_address": {
            "province": "DKI Jakarta",
            "city": "Jakarta Selatan",
            "detail": "Jl. A",
        },
        "consent": True,
    }
    payload.update(overrides)
    return payload


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4 fake ktp scan"


def test_onboarding_invite_full_lifecycle_submit_to_apply(client):
    headers = _auth_header(client)
    invite, token = _create_invite(client, headers)
    assert invite["status"] == "invited"

    view = client.get(f"/api/v1/onboarding/{token}")
    assert view.status_code == 200, view.text
    assert view.json()["status"] == "invited"
    assert view.json()["candidate_name"] == "Citra Lestari"

    submitted = client.post(f"/api/v1/onboarding/{token}", json=_submit_payload())
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    up = client.post(
        f"/api/v1/onboarding/{token}/documents",
        files={"file": ("ktp.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
        data={"document_type": "ktp"},
    )
    assert up.status_code == 200, up.text
    assert up.json()["document_type"] == "ktp"

    view2 = client.get(f"/api/v1/onboarding/{token}")
    assert view2.status_code == 200
    assert view2.json()["status"] == "submitted"
    assert len(view2.json()["documents"]) == 1
    assert view2.json()["submitted_data"]["ktp_no"] == "3201010101010001"

    detail = client.get(f"/api/v1/employees/onboarding-invites/{invite['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["submitted_data"]["bank_account"] == "1234567890"
    assert len(detail.json()["documents"]) == 1
    assert detail.json()["documents"][0]["download_url"]

    applied = client.post(
        f"/api/v1/employees/onboarding-invites/{invite['id']}/apply", headers=headers
    )
    assert applied.status_code == 200, applied.text
    employee = applied.json()
    assert employee["ktp_no"] == "3201010101010001"
    assert employee["npwp_no"] == "09.123.456.7-890.000"
    assert employee["bank_name"] == "BCA"
    assert employee["emergency_contact_name"] == "Sari"
    assert employee["citizen_address"]["city"] == "Jakarta Selatan"

    docs = client.get(f"/api/v1/employees/{employee['id']}/documents", headers=headers)
    assert docs.status_code == 200
    assert len(docs.json()) == 1
    assert docs.json()[0]["document_type"] == "ktp"

    # Token yang sudah applied tidak bisa dipakai lagi.
    again = client.get(f"/api/v1/onboarding/{token}")
    assert again.status_code == 409


def test_onboarding_submit_tanpa_consent_ditolak(client):
    headers = _auth_header(client)
    _invite, token = _create_invite(client, headers)
    resp = client.post(f"/api/v1/onboarding/{token}", json=_submit_payload(consent=False))
    assert resp.status_code == 422


def test_onboarding_upload_document_mime_salah_ditolak(client):
    headers = _auth_header(client)
    _invite, token = _create_invite(client, headers)
    resp = client.post(
        f"/api/v1/onboarding/{token}/documents",
        files={"file": ("ktp.txt", io.BytesIO(b"halo"), "text/plain")},
        data={"document_type": "ktp"},
    )
    assert resp.status_code == 422


def test_onboarding_upload_document_ganti_bukan_versioning(client):
    headers = _auth_header(client)
    invite, token = _create_invite(client, headers)
    client.post(
        f"/api/v1/onboarding/{token}/documents",
        files={"file": ("ktp-v1.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
        data={"document_type": "ktp"},
    )
    client.post(
        f"/api/v1/onboarding/{token}/documents",
        files={"file": ("ktp-v2.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
        data={"document_type": "ktp"},
    )
    detail = client.get(
        f"/api/v1/employees/onboarding-invites/{invite['id']}", headers=headers
    ).json()
    ktp_docs = [d for d in detail["documents"] if d["document_type"] == "ktp"]
    assert len(ktp_docs) == 1
    assert ktp_docs[0]["file_name"] == "ktp-v2.pdf"


def test_onboarding_token_invalid_404(client):
    resp = client.get("/api/v1/onboarding/token-tidak-ada")
    assert resp.status_code == 404


def test_onboarding_token_kedaluwarsa_410(client):
    from datetime import UTC, datetime, timedelta

    from app.core.database import parse_uuid
    from app.modules.hrd.models import OnboardingInvite

    headers = _auth_header(client)
    invite, token = _create_invite(client, headers, days=1)

    db = client.testing_session()
    try:
        row = db.get(OnboardingInvite, parse_uuid(invite["id"]))
        row.expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/v1/onboarding/{token}")
    assert resp.status_code == 410


def test_onboarding_apply_ditolak_sebelum_submit(client):
    headers = _auth_header(client)
    invite, _token = _create_invite(client, headers)
    resp = client.post(
        f"/api/v1/employees/onboarding-invites/{invite['id']}/apply", headers=headers
    )
    assert resp.status_code == 409


def test_onboarding_revoke_lalu_token_ditolak(client):
    headers = _auth_header(client)
    invite, token = _create_invite(client, headers)
    revoked = client.post(
        f"/api/v1/employees/onboarding-invites/{invite['id']}/revoke", headers=headers
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"

    resp = client.get(f"/api/v1/onboarding/{token}")
    assert resp.status_code == 409


def test_onboarding_revoke_setelah_applied_ditolak(client):
    headers = _auth_header(client)
    invite, token = _create_invite(client, headers)
    client.post(f"/api/v1/onboarding/{token}", json=_submit_payload())
    client.post(f"/api/v1/employees/onboarding-invites/{invite['id']}/apply", headers=headers)

    resp = client.post(
        f"/api/v1/employees/onboarding-invites/{invite['id']}/revoke", headers=headers
    )
    assert resp.status_code == 409


def test_onboarding_request_resubmission_keeps_token_and_data(client):
    headers = _auth_header(client)
    invite, token = _create_invite(client, headers)
    client.post(f"/api/v1/onboarding/{token}", json=_submit_payload())

    resubmit = client.post(
        f"/api/v1/employees/onboarding-invites/{invite['id']}/request-resubmission",
        headers=headers,
    )
    assert resubmit.status_code == 200, resubmit.text
    assert resubmit.json()["status"] == "invited"

    view = client.get(f"/api/v1/onboarding/{token}")
    assert view.status_code == 200
    assert view.json()["status"] == "invited"
    # Data lama tetap ada buat prefill.
    assert view.json()["submitted_data"]["ktp_no"] == "3201010101010001"

    resubmitted = client.post(
        f"/api/v1/onboarding/{token}", json=_submit_payload(ktp_no="3201010101019999")
    )
    assert resubmitted.status_code == 200
    detail = client.get(
        f"/api/v1/employees/onboarding-invites/{invite['id']}", headers=headers
    ).json()
    assert detail["submitted_data"]["ktp_no"] == "3201010101019999"


def test_onboarding_creating_new_invite_cabut_invite_lama(client):
    headers = _auth_header(client)
    invite1, token1 = _create_invite(client, headers)
    # Buat placement lagi untuk invite kedua dengan placement SAMA -- ambil
    # placement_id dari invite pertama, cabut invite lama.
    pid = invite1["placement_id"]
    resp2 = client.post(
        "/api/v1/employees/onboarding-invites",
        headers=headers,
        json={"placement_id": pid, "days": 14},
    )
    assert resp2.status_code == 201, resp2.text

    old = client.get(f"/api/v1/onboarding/{token1}")
    assert old.status_code == 404
