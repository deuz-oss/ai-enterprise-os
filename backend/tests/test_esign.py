"""Test integrasi tanda tangan elektronik (mode sandbox).

Tidak butuh vendor sungguhan: ESIGN_PROVIDER di-patch ke "sandbox" dan
penyelesaian dokumen disimulasikan lewat endpoint simulate-complete
atau webhook ber-HMAC.
"""

import hashlib
import hmac as hmac_mod
import uuid
from unittest.mock import patch

from app.core.config import get_settings

from tests.conftest import _auth_header

_CONTRACT_TEXT = (
    b"PERJANJIAN KERJA POKOK\n"
    b"Pasal 1: Gaji pokok karyawan adalah Rp5.000.000 per bulan.\n"
    b"Pasal 2: Masa kontrak berlaku 12 bulan sejak tanggal mulai.\n"
    b"Pasal 3: Tunjangan transportasi Rp500.000 per bulan.\n"
)


def _employee_with_contract(client, headers, name="Karyawan TTE") -> str:
    emp = client.post("/api/v1/employees", headers=headers, json={"full_name": name}).json()
    contract = client.post(
        f"/api/v1/employees/{emp['id']}/contracts", headers=headers, json={}
    ).json()
    with patch("app.modules.hrd.service.storage.put_object") as put:
        put.return_value = f"contracts/{emp['id']}/kontrak.txt"
        resp = client.post(
            f"/api/v1/employees/contracts/{contract['id']}/file",
            headers=headers,
            files={"file": ("kontrak.txt", _CONTRACT_TEXT, "text/plain")},
        )
    assert resp.status_code == 200, resp.text
    return contract["id"]


def _sandbox_settings():
    settings = get_settings()
    return patch.object(settings, "esign_provider", "sandbox")


def _send(client, headers, contract_id, name="Budi", email="budi@example.com"):
    """Kirim kontrak ke TTE dengan storage di-mock."""
    with patch("app.modules.esign.service.get_object") as get_obj:
        get_obj.return_value = _CONTRACT_TEXT
        return client.post(
            f"/api/v1/esign/contracts/{contract_id}/send",
            headers=headers,
            json={"signer_name": name, "signer_email": email},
        )


def _webhook_signature(body: bytes, secret: str) -> str:
    return hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_config_mengembalikan_status_provider(client):
    headers = _auth_header(client)
    with _sandbox_settings():
        cfg = client.get("/api/v1/esign/config", headers=headers).json()
    assert cfg["provider"] == "sandbox"


def test_send_tanpa_konfigurasi_mengembalikan_503(client):
    """Patch eksplisit ke kosong -- jangan bergantung pada default ambient
    ESIGN_PROVIDER di .env (fragile; nilainya bisa "sandbox" di lingkungan
    dev/demo yang sudah mengaktifkan TTE)."""
    headers = _auth_header(client)
    contract_id = _employee_with_contract(client, headers)
    settings = get_settings()
    with patch.object(settings, "esign_provider", None):
        resp = _send(client, headers, contract_id)
    assert resp.status_code == 503


def test_send_sukses_dan_anti_duplikat(client):
    headers = _auth_header(client)
    contract_id = _employee_with_contract(client, headers)

    with _sandbox_settings():
        first = _send(client, headers, contract_id)
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["provider"] == "sandbox"
        assert body["provider_document_id"].startswith("sbx-")
        assert body["status"] == "terkirim"
        assert body["sign_url"]

        # Permintaan kedua untuk kontrak yang sama harus ditolak
        duplicate = _send(client, headers, contract_id)
        assert duplicate.status_code == 409

        history = client.get(
            "/api/v1/esign/requests",
            headers=headers,
            params={"contract_id": contract_id},
        ).json()
        assert len(history) == 1


def test_simulate_complete_mengubah_kontrak_jadi_ttd(client):
    headers = _auth_header(client)
    contract_id = _employee_with_contract(client, headers)

    with _sandbox_settings():
        sent = _send(client, headers, contract_id).json()
        done = client.post(
            f"/api/v1/esign/requests/{sent['id']}/simulate-complete", headers=headers
        )
        assert done.status_code == 200
        body = done.json()
        assert body["status"] == "selesai"
        assert body["signed_at"]

    # Status kontrak berubah persisten di DB test
    from app.modules.hrd.models import EmploymentContract

    with client.testing_session() as db:  # type: ignore[attr-defined]
        row = db.get(EmploymentContract, uuid.UUID(contract_id))
        assert row is not None
        assert row.sign_status.value == "ditandatangani"
        assert row.signed_at is not None


def test_webhook_hmac_valid_mengubah_status(client):
    headers = _auth_header(client)
    contract_id = _employee_with_contract(client, headers)

    secret = "rahasia-webhook-test"
    settings = get_settings()
    with (
        _sandbox_settings(),
        patch.object(settings, "esign_webhook_secret", secret),
    ):
        sent = _send(client, headers, contract_id, "Citra", "citra@example.com").json()

        payload = (
            b'{"document_token": "' + sent["provider_document_id"].encode() + b'", '
            b'"status": "completed"}'
        )
        # Tanpa/tanda tangan salah → ditolak
        bad = client.post(
            "/api/v1/esign/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Esign-Signature": "salah",
            },
        )
        assert bad.status_code == 401

        good = client.post(
            "/api/v1/esign/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Esign-Signature": _webhook_signature(payload, secret),
            },
        )
        assert good.status_code == 200, good.text
        assert good.json()["status"] == "selesai"


def test_role_hr_wajib_untuk_fitur_esign(client):
    admin = _auth_header(client)
    reg = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={
            "email": "rec@example.com",
            "full_name": "Recruiter",
            "password": "password123",
            "role": "recruiter",
        },
    )
    assert reg.status_code == 201
    token = client.post(
        "/api/v1/auth/login", json={"email": "rec@example.com", "password": "password123"}
    ).json()["access_token"]
    resp = client.get("/api/v1/esign/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
