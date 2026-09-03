"""Job Portal publik (PRD v3.1 Patch 5) — sebelumnya NOL test sama sekali
(temuan audit 2026-09-02) padahal ini permukaan publik tanpa auth yang
memanipulasi tenant context secara manual. Fokus: isolasi tenant (paling
kritis) dan alur apply->cek status by token, termasuk fix
`_resolve_placement_tenant`/`resolve_placement_tenant()` SQL function
untuk lookup token di bawah RLS Postgres (di SQLite/test, fungsi itu tidak
dipakai -- cabang dialect di service.py fallback ke query ORM biasa, jadi
test ini tetap valid tanpa Postgres nyata)."""

import io

from tests.conftest import _auth_header
from tests.test_platform import _login, _provision


def _create_client(client, headers, name="PT Klien Portal") -> str:
    resp = client.post("/api/v1/clients", headers=headers, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_public_job_order(client, headers, client_id, title="QA Engineer", label=None) -> dict:
    resp = client.post(
        "/api/v1/recruitment/job-orders",
        headers=headers,
        json={
            "client_id": client_id,
            "title": title,
            "headcount": 1,
            "is_public": True,
            "public_client_label": label,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_public_listing_terisolasi_per_tenant(client):
    admin_a = _auth_header(client)
    client_id_a = _create_client(client, admin_a)
    _create_public_job_order(client, admin_a, client_id_a, title="Backend Engineer A")

    _provision(client, "portal-b")
    admin_b = _login(client, "admin-portal-b@example.com")
    client_id_b = _create_client(client, admin_b, name="PT Klien B")
    _create_public_job_order(client, admin_b, client_id_b, title="Backend Engineer B")

    # Tenant default (A) -- slug-nya "default" (lihat bootstrap.py).
    listing_a = client.get("/api/v1/public/default/job-orders")
    assert listing_a.status_code == 200
    titles_a = [jo["title"] for jo in listing_a.json()]
    assert "Backend Engineer A" in titles_a
    assert "Backend Engineer B" not in titles_a

    listing_b = client.get("/api/v1/public/portal-b/job-orders")
    assert listing_b.status_code == 200
    titles_b = [jo["title"] for jo in listing_b.json()]
    assert "Backend Engineer B" in titles_b
    assert "Backend Engineer A" not in titles_b


def test_public_job_order_tidak_bocorkan_nama_klien_asli(client):
    admin = _auth_header(client)
    client_id = _create_client(client, admin, name="PT Rahasia Klien")
    jo = _create_public_job_order(client, admin, client_id, title="Data Analyst", label=None)

    resp = client.get(f"/api/v1/public/default/job-orders/{jo['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert "PT Rahasia Klien" not in str(body)


def test_apply_lalu_cek_status_by_token(client):
    admin = _auth_header(client)
    client_id = _create_client(client, admin)
    jo = _create_public_job_order(client, admin, client_id, title="Support Coordinator")

    cv_file = io.BytesIO(b"%PDF-1.4 fake cv content")
    resp = client.post(
        f"/api/v1/public/default/job-orders/{jo['id']}/apply",
        data={
            "full_name": "Kandidat Uji Portal",
            "email": "kandidat.portal@example.com",
            "consent": "true",
            "screening_answers": "{}",
        },
        files={"file": ("cv.pdf", cv_file, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["application_token"]
    assert token

    status_resp = client.get(f"/api/v1/public/applications/{token}")
    assert status_resp.status_code == 200, status_resp.text
    body = status_resp.json()
    assert body["job_title"] == "Support Coordinator"
    assert body["candidate_name"] == "Kandidat Uji Portal"
    assert body["status_label"]


def test_cek_status_token_asal_asalan_404(client):
    resp = client.get("/api/v1/public/applications/token-yang-tidak-pernah-ada")
    assert resp.status_code == 404
