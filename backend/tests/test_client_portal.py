"""Portal monitoring klien (link tanpa akun, read-only): generate, akses, isolasi, revoke."""

from tests.conftest import _auth_header
from tests.test_recruitment import _client_id, _create_candidate, _create_jo


def _external_employee_for_client(client, headers, client_id, name="Karyawan Klien"):
    """Karyawan eksternal berpindah lewat pipeline Client -> JobOrder ->
    Placement -> onboard, supaya Employee.placement_id terisi (jalur yang
    dipakai query client-portal untuk resolve Client-nya)."""
    jo_id = _create_jo(client, headers, client_id, title="Staff Lapangan")
    cand_id = _create_candidate(client, headers, name=name)
    placement = client.post(
        "/api/v1/recruitment/placements",
        headers=headers,
        json={"candidate_id": cand_id, "job_order_id": jo_id},
    )
    assert placement.status_code == 201, placement.text
    onboarded = client.post(
        "/api/v1/employees/onboard",
        headers=headers,
        json={"placement_id": placement.json()["id"]},
    )
    assert onboarded.status_code == 201, onboarded.text
    return onboarded.json()


def _attendance_record(client, headers, employee_id, day="2026-09-05", **overrides):
    body = {
        "employee_id": employee_id,
        "date": day,
        "status": "hadir",
        "clock_in": f"{day} 08:00",
        "clock_out": f"{day} 17:00",
        "overtime_hours": 2,
    }
    body.update(overrides)
    resp = client.post("/api/v1/attendance/records", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generate_access(client, headers, client_id):
    resp = client.post(f"/api/v1/clients/{client_id}/portal-access", headers=headers, json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    token = body["url"].rsplit("/", 1)[-1]
    return body, token


def test_generate_akses_dan_lihat_rekap(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    emp = _external_employee_for_client(client, headers, cid)
    _attendance_record(client, headers, emp["id"])

    _, token = _generate_access(client, headers, cid)

    view = client.get(f"/api/v1/clients/portal/{token}", params={"year": 2026, "month": 9})
    assert view.status_code == 200, view.text
    body = view.json()
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["employee_name"] == "Karyawan Klien"
    assert row["present_days"] == 1
    assert row["overtime_hours"] == 2
    assert row["client_approved"] is False

    status = client.get(f"/api/v1/clients/{cid}/portal-access", headers=headers).json()
    assert status["last_accessed_at"] is not None


def test_isolasi_antar_klien_dan_karyawan_tanpa_placement(client):
    headers = _auth_header(client)
    cid_a = _client_id(client, headers)
    cid_b = client.post("/api/v1/clients", headers=headers, json={"name": "PT Lain"}).json()["id"]

    emp_a = _external_employee_for_client(client, headers, cid_a, name="Punya Klien A")
    emp_b = _external_employee_for_client(client, headers, cid_b, name="Punya Klien B")
    _attendance_record(client, headers, emp_a["id"])
    _attendance_record(client, headers, emp_b["id"])

    # Karyawan tanpa placement_id (input manual) TIDAK boleh nyasar ke klien manapun.
    manual = client.post(
        "/api/v1/employees", headers=headers, json={"full_name": "Karyawan Manual"}
    ).json()
    _attendance_record(client, headers, manual["id"])

    _, token_a = _generate_access(client, headers, cid_a)
    view = client.get(f"/api/v1/clients/portal/{token_a}", params={"year": 2026, "month": 9}).json()
    names = [r["employee_name"] for r in view["rows"]]
    assert names == ["Punya Klien A"]


def test_karyawan_internal_tidak_muncul_di_portal_klien(client):
    from app.core.database import parse_uuid
    from app.modules.hrd.models import Employee, EmploymentType

    headers = _auth_header(client)
    cid = _client_id(client, headers)
    emp = _external_employee_for_client(client, headers, cid)
    _attendance_record(client, headers, emp["id"])

    db = client.testing_session()
    try:
        row = db.get(Employee, parse_uuid(emp["id"]))
        row.employment_type = EmploymentType.internal
        db.commit()
    finally:
        db.close()

    _, token = _generate_access(client, headers, cid)
    view = client.get(f"/api/v1/clients/portal/{token}", params={"year": 2026, "month": 9}).json()
    assert view["rows"] == []


def test_token_salah_dan_revoke(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)

    invalid = client.get("/api/v1/clients/portal/token-tidak-ada")
    assert invalid.status_code == 404

    _, token = _generate_access(client, headers, cid)
    assert client.get(f"/api/v1/clients/portal/{token}").status_code == 200

    revoked = client.delete(f"/api/v1/clients/{cid}/portal-access", headers=headers)
    assert revoked.status_code == 204
    assert client.get(f"/api/v1/clients/portal/{token}").status_code == 404

    # Cabut lagi tanpa akses yang ada -> 404
    assert client.delete(f"/api/v1/clients/{cid}/portal-access", headers=headers).status_code == 404


def test_regenerate_mencabut_token_lama(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)

    _, token1 = _generate_access(client, headers, cid)
    assert client.get(f"/api/v1/clients/portal/{token1}").status_code == 200

    _, token2 = _generate_access(client, headers, cid)
    assert token2 != token1
    assert client.get(f"/api/v1/clients/portal/{token1}").status_code == 404
    assert client.get(f"/api/v1/clients/portal/{token2}").status_code == 200


def test_status_belum_ada_akses_mengembalikan_null(client):
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    status = client.get(f"/api/v1/clients/{cid}/portal-access", headers=headers)
    assert status.status_code == 200
    assert status.json() is None
