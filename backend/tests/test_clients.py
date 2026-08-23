from unittest.mock import patch

from tests.conftest import _auth_header


def _create_client(client, headers, name="PT Klien Sejahtera"):
    resp = client.post(
        "/api/v1/clients",
        headers=headers,
        json={
            "name": name,
            "npwp": "01.234.567.8-901.000",
            "pic_name": "Sari",
            "contract_end": "2026-12-31",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_and_get_client(client):
    headers = _auth_header(client)
    created = _create_client(client, headers)
    fetched = client.get(f"/api/v1/clients/{created['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "aktif"


def test_upload_document_versions(client):
    headers = _auth_header(client)
    created = _create_client(client, headers)

    with patch("app.modules.clients.service.storage.put_object") as put:
        put.return_value = "key"
        first = client.post(
            f"/api/v1/clients/{created['id']}/documents",
            headers=headers,
            files={"file": ("pks-v1.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"document_type": "perjanjian_kerjasama", "title": "PKS 2026"},
        )
        second = client.post(
            f"/api/v1/clients/{created['id']}/documents",
            headers=headers,
            files={"file": ("pks-v2.pdf", b"%PDF-1.4 fake2", "application/pdf")},
            data={"document_type": "perjanjian_kerjasama", "title": "PKS 2026 revisi"},
        )
        other = client.post(
            f"/api/v1/clients/{created['id']}/documents",
            headers=headers,
            files={"file": ("npwp.pdf", b"%PDF-1.4 npwp", "application/pdf")},
            data={"document_type": "npwp", "title": "NPWP klien"},
        )

    assert first.status_code == 201 and second.status_code == 201 and other.status_code == 201
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert other.json()["version"] == 1

    docs = client.get(f"/api/v1/clients/{created['id']}/documents", headers=headers).json()
    assert len(docs) == 3


def test_expiring_contracts(client):
    headers = _auth_header(client)
    _create_client(client, headers)
    result = client.get(
        "/api/v1/clients/expiring-contracts", headers=headers, params={"within_days": 365}
    )
    assert result.status_code == 200
    assert len(result.json()) == 1


def test_overview_counts(client):
    headers = _auth_header(client)
    _create_client(client, headers)
    overview = client.get("/api/v1/overview", headers=headers).json()
    assert overview["clients"] == 1
