"""Pengajuan lembur karyawan lewat portal ESS: ajukan -> HR putuskan -> rekap."""

from datetime import date, timedelta

from tests.conftest import _auth_header
from tests.test_ess import _create_karyawan, _link_employee


def _setup_linked_karyawan(client, name="Pekerja Lembur") -> tuple[dict, dict, str]:
    admin = _auth_header(client)
    emp = client.post("/api/v1/employees", headers=admin, json={"full_name": name}).json()
    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])
    return admin, headers, emp["id"]


def _submit_overtime(client, headers, **overrides):
    body = {
        "date": str(date.today()),
        "requested_hours": 2,
        "reason": "Tutup buku bulanan",
    }
    body.update(overrides)
    return client.post("/api/v1/me/overtime-requests", headers=headers, json=body)


def test_overtime_request_flow_submit_decide_cancel(client):
    admin, headers, emp_id = _setup_linked_karyawan(client)

    created = _submit_overtime(client, headers)
    assert created.status_code == 201, created.text
    overtime = created.json()
    assert overtime["status"] == "menunggu"
    overtime_id = overtime["id"]

    # tanggal di masa depan ditolak
    future = str(date.today() + timedelta(days=1))
    assert _submit_overtime(client, headers, date=future).status_code == 422

    # jam di luar 1-24 ditolak
    assert _submit_overtime(client, headers, requested_hours=0).status_code == 422
    assert _submit_overtime(client, headers, requested_hours=25).status_code == 422

    # pengajuan kedua di tanggal berbeda
    yesterday = str(date.today() - timedelta(days=1))
    second = _submit_overtime(client, headers, date=yesterday, requested_hours=3)
    assert second.status_code == 201, second.text

    # karyawan tidak punya wewenang memutuskan
    forbidden = client.patch(
        f"/api/v1/employees/overtime-requests/{overtime_id}/decision",
        headers=headers,
        json={"approved": True},
    )
    assert forbidden.status_code in (401, 403)

    # HR menyetujui pengajuan pertama
    decided = client.patch(
        f"/api/v1/employees/overtime-requests/{overtime_id}/decision",
        headers=admin,
        json={"approved": True, "note": "Disetujui HR"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "disetujui"
    assert decided.json()["decided_at"] is not None

    # keputusan ulang ditolak; yang sudah diputuskan tak bisa dibatalkan sendiri
    assert (
        client.patch(
            f"/api/v1/employees/overtime-requests/{overtime_id}/decision",
            headers=admin,
            json={"approved": False},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/me/overtime-requests/{overtime_id}/cancel", headers=headers
        ).status_code
        == 409
    )

    # karyawan membatalkan pengajuan kedua yang masih pending
    cancelled = client.post(
        f"/api/v1/me/overtime-requests/{second.json()['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "dibatalkan"

    # daftar milik sendiri terurut terbaru dulu (tiebreak tanggal saat
    # created_at sama-sama dalam detik yang sama) + filter status sisi HR
    mine = client.get("/api/v1/me/overtime-requests", headers=headers).json()
    assert [row["status"] for row in mine] == ["disetujui", "dibatalkan"]
    approved_only = client.get(
        "/api/v1/employees/overtime-requests",
        headers=admin,
        params={"status": "disetujui"},
    ).json()
    assert [row["id"] for row in approved_only] == [overtime_id]


def test_overtime_approval_menambah_attendance_record_dan_summary(client):
    admin, headers, emp_id = _setup_linked_karyawan(client)
    today = date.today()

    first = _submit_overtime(client, headers, requested_hours=2).json()
    client.patch(
        f"/api/v1/employees/overtime-requests/{first['id']}/decision",
        headers=admin,
        json={"approved": True},
    )

    rows = client.get(
        f"/api/v1/attendance/records?year={today.year}&month={today.month}&employee_id={emp_id}",
        headers=admin,
    ).json()
    assert len(rows) == 1
    assert rows[0]["overtime_hours"] == 2
    assert rows[0]["source"] == "ess"

    summary = client.get(
        f"/api/v1/payroll/attendance?year={today.year}&month={today.month}", headers=admin
    ).json()
    mine_summary = next(row for row in summary if row["employee_id"] == emp_id)
    assert mine_summary["overtime_hours"] == 2

    # Pengajuan kedua di tanggal SAMA -> jam terakumulasi, bukan menimpa
    second = _submit_overtime(client, headers, requested_hours=3).json()
    client.patch(
        f"/api/v1/employees/overtime-requests/{second['id']}/decision",
        headers=admin,
        json={"approved": True},
    )
    rows_after = client.get(
        f"/api/v1/attendance/records?year={today.year}&month={today.month}&employee_id={emp_id}",
        headers=admin,
    ).json()
    assert len(rows_after) == 1
    assert rows_after[0]["overtime_hours"] == 5

    summary_after = client.get(
        f"/api/v1/payroll/attendance?year={today.year}&month={today.month}", headers=admin
    ).json()
    mine_after = next(row for row in summary_after if row["employee_id"] == emp_id)
    assert mine_after["overtime_hours"] == 5


def test_overtime_ditolak_tidak_mengubah_attendance_record(client):
    admin, headers, emp_id = _setup_linked_karyawan(client)
    today = date.today()

    submitted = _submit_overtime(client, headers).json()
    rejected = client.patch(
        f"/api/v1/employees/overtime-requests/{submitted['id']}/decision",
        headers=admin,
        json={"approved": False, "note": "Tidak sesuai kebutuhan"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "ditolak"

    rows = client.get(
        f"/api/v1/attendance/records?year={today.year}&month={today.month}&employee_id={emp_id}",
        headers=admin,
    ).json()
    assert rows == []


def test_overtime_notifies_employee_on_decision(client):
    admin, headers, emp_id = _setup_linked_karyawan(client)
    overtime = _submit_overtime(client, headers).json()

    client.patch(
        f"/api/v1/employees/overtime-requests/{overtime['id']}/decision",
        headers=admin,
        json={"approved": True, "note": "Silakan"},
    )
    notifications = client.get("/api/v1/me/notifications", headers=headers).json()
    assert any("lembur" in (n["title"] or "").lower() for n in notifications)
