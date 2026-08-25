"""Fase 8 — Absensi harian: CRUD, agregasi, impor CSV, dua jalur, integrasi ESS."""

from tests.conftest import _auth_header


def _employee(client, headers, name="Pekerja Absen", employment=None):
    body = {"full_name": name}
    if employment:
        body["employment_type"] = employment
    resp = client.post("/api/v1/employees", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _record(client, headers, employee_id, day="2026-08-04", **overrides):
    body = {
        "employee_id": employee_id,
        "date": day,
        "status": "hadir",
        "clock_in": f"{day} 07:55",
        "clock_out": f"{day} 17:05",
        "overtime_hours": 2,
    }
    body.update(overrides)
    return client.post("/api/v1/attendance/records", headers=headers, json=body)


def test_manual_record_and_auto_aggregation(client):
    admin = _auth_header(client)
    emp = _employee(client, admin)

    created = _record(client, admin, emp["id"])
    assert created.status_code == 201, created.text
    assert created.json()["source"] == "manual"

    # Rekap bulanan terbentuk otomatis dari record harian.
    summaries = client.get(
        "/api/v1/payroll/attendance", headers=admin, params={"year": 2026, "month": 8}
    ).json()
    assert len(summaries) == 1
    assert summaries[0]["present_days"] == 1
    assert summaries[0]["overtime_hours"] == 2

    # Tambah hari terlambat + dinas luar → ikut dihitung hadir; izin tidak.
    _record(client, admin, emp["id"], day="2026-08-05", status="terlambat", overtime_hours=0)
    _record(client, admin, emp["id"], day="2026-08-06", status="dinas_luar", overtime_hours=0)
    _record(client, admin, emp["id"], day="2026-08-07", status="izin", overtime_hours=0)

    summaries = client.get(
        "/api/v1/payroll/attendance", headers=admin, params={"year": 2026, "month": 8}
    ).json()
    assert summaries[0]["present_days"] == 3

    # Update record yang sama (bukan duplikat baru) → agregasi tetap benar.
    updated = _record(client, admin, emp["id"], day="2026-08-04", overtime_hours=5)
    assert updated.status_code == 200 or updated.status_code == 201
    summaries = client.get(
        "/api/v1/payroll/attendance", headers=admin, params={"year": 2026, "month": 8}
    ).json()
    assert summaries[0]["present_days"] == 3
    assert summaries[0]["overtime_hours"] == 5


def test_two_lane_validation(client):
    from datetime import date

    admin = _auth_header(client)
    internal = _employee(client, admin, "Staf Internal", employment="internal")
    eksternal = _employee(client, admin, "TKO Klien", employment="eksternal")

    today = date.today()
    first_day = today.replace(day=1).isoformat()
    for emp in (internal, eksternal):
        rec = _record(client, admin, emp["id"], day=first_day)
        assert rec.status_code in (200, 201), rec.text

    def summary_id_for(emp_id):
        rows = client.get(
            "/api/v1/payroll/attendance",
            headers=admin,
            params={"year": today.year, "month": today.month},
        ).json()
        return next(r["id"] for r in rows if r["employee_id"] == emp_id)

    # Jalur klien menolak karyawan internal; jalur HR menerima.
    wrong = client.post(
        f"/api/v1/attendance/summaries/{summary_id_for(internal['id'])}/validate",
        headers=admin,
        params={"lane": "klien"},
    )
    assert wrong.status_code == 422
    hr_ok = client.post(
        f"/api/v1/attendance/summaries/{summary_id_for(internal['id'])}/validate",
        headers=admin,
        params={"lane": "hr"},
    )
    assert hr_ok.status_code == 200, hr_ok.text
    assert hr_ok.json()["client_approved"] is True

    # Jalur HR menolak karyawan eksternal; jalur klien menerima.
    wrong2 = client.post(
        f"/api/v1/attendance/summaries/{summary_id_for(eksternal['id'])}/validate",
        headers=admin,
        params={"lane": "hr"},
    )
    assert wrong2.status_code == 422
    client_ok = client.post(
        f"/api/v1/attendance/summaries/{summary_id_for(eksternal['id'])}/validate",
        headers=admin,
        params={"lane": "klien"},
    )
    assert client_ok.status_code == 200

    # Endpoint lama (approval klien payrol) juga menolak karyawan internal.
    legacy = client.patch(
        f"/api/v1/payroll/attendance/{summary_id_for(internal['id'])}/client-approval",
        headers=admin,
        params={"approved": True},
    )
    assert legacy.status_code == 422


def test_csv_import_with_failures(client):
    admin = _auth_header(client)
    emp = _employee(client, admin, "Impor Sukses")

    csv_text = (
        "employee_no;date;clock_in;clock_out;overtime_hours;status\n"
        f"{emp['employee_no']};2026-08-10;2026-08-10 08:00;2026-08-10 17:00;1;hadir\n"
        "EMP-TAK-ADA;2026-08-10;; ;0;hadir\n"
        f"{emp['employee_no']};31/12/2026;;;0;hadir\n"
        f"{emp['employee_no']};2026-08-11;;;;cuti\n"
    )
    uploaded = client.post(
        "/api/v1/attendance/import",
        headers=admin,
        files={"file": ("fingerprint.csv", csv_text.encode(), "text/csv")},
    )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["inserted"] == 2
    assert body["updated"] == 0
    assert len(body["failed"]) == 2
    errors = [f["error"] for f in body["failed"]]
    assert any("tidak ditemukan" in e for e in errors)
    assert any("tidak valid" in e for e in errors)

    records = client.get(
        "/api/v1/attendance/records", headers=admin, params={"year": 2026, "month": 8}
    ).json()
    by_date = {r["date"]: r for r in records}
    assert by_date["2026-08-10"]["source"] == "impor"
    assert by_date["2026-08-11"]["status"] == "cuti"

    # Impor ulang baris yang sama → update, bukan duplikat.
    again = client.post(
        "/api/v1/attendance/import",
        headers=admin,
        files={"file": ("fingerprint.csv", csv_text.encode(), "text/csv")},
    )
    assert again.json()["updated"] == 2 and again.json()["inserted"] == 0


def test_template_download(client):
    admin = _auth_header(client)
    resp = client.get("/api/v1/attendance/template", headers=admin)
    assert resp.status_code == 200
    assert "employee_no;date;clock_in" in resp.text


def test_approved_leave_creates_attendance_records(client):
    admin = _auth_header(client)
    emp = _employee(client, admin, "Pemohon Sakit")
    from tests.test_ess import _create_karyawan, _link_employee

    headers = _create_karyawan(client)
    _link_employee(client, emp["id"])

    leave = client.post(
        "/api/v1/me/leave-requests",
        headers=headers,
        json={
            "leave_type": "sakit",
            "start_date": "2026-09-14",
            "end_date": "2026-09-16",
            "reason": "Flu",
        },
    ).json()
    decided = client.patch(
        f"/api/v1/employees/leave-requests/{leave['id']}/decision",
        headers=admin,
        json={"approved": True},
    )
    assert decided.status_code == 200, decided.text

    records = client.get(
        "/api/v1/attendance/records", headers=admin, params={"year": 2026, "month": 9}
    ).json()
    mine = [r for r in records if r["employee_id"] == emp["id"]]
    assert len(mine) == 3
    assert all(r["status"] == "sakit" for r in mine)
    assert all(r["source"] == "ess" for r in mine)

    # Record cuti tidak dihitung hadir dalam agregasi.
    summaries = client.get(
        "/api/v1/payroll/attendance", headers=admin, params={"year": 2026, "month": 9}
    ).json()
    target = next(s for s in summaries if s["employee_id"] == emp["id"])
    assert target["present_days"] == 0
