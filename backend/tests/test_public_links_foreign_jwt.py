"""Link publik ber-token tetap bisa dibuka walau browser menyimpan JWT tenant lain.

Regresi (ditemukan saat verifikasi AI #9, 2026-10-10): middleware menyetel
konteks tenant dari klaim `tid` JWT mana pun di header. Lookup token publik
lalu tersaring ke tenant itu, dan link yang valid dijawab 404 "tidak valid".
"""

from uuid import uuid4

from app.core.security import create_access_token

from tests.conftest import _auth_header
from tests.test_client_portal import _generate_access
from tests.test_hrd_onboarding import _create_invite
from tests.test_recruitment import _client_id

# JWT sah (ditandatangani) tetapi milik tenant lain / akun basi.
FOREIGN = {"Authorization": f"Bearer {create_access_token(str(uuid4()), tenant_id=uuid4())}"}


def test_onboarding_link_opens_with_foreign_jwt(client):
    _, token = _create_invite(client, _auth_header(client))
    resp = client.get(f"/api/v1/onboarding/{token}", headers=FOREIGN)
    assert resp.status_code == 200, resp.text
    assert resp.json()["candidate_name"] == "Citra Lestari"


def test_client_portal_link_opens_with_foreign_jwt(client):
    headers = _auth_header(client)
    _, token = _generate_access(client, headers, _client_id(client, headers))
    resp = client.get(
        f"/api/v1/clients/portal/{token}", params={"year": 2026, "month": 9}, headers=FOREIGN
    )
    assert resp.status_code == 200, resp.text


def test_payroll_approval_link_opens_with_foreign_jwt(client):
    from tests.test_payroll_dua_jalur import _setup

    admin, client_id, _ = _setup(client)
    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 10, "run_type": "proyek", "client_id": client_id},
    ).json()
    client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={})
    sub = client.post(
        f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}
    ).json()
    resp = client.get(f"/api/v1/payroll/client/{sub['raw_token']}", headers=FOREIGN)
    assert resp.status_code == 200, resp.text
