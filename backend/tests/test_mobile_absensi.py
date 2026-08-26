"""Fase 8 lanjutan — Mobile GPS+selfie clock in/out (portal & app mobile)."""

from datetime import date
from unittest.mock import patch

from tests.conftest import _auth_header
from tests.test_ess import _create_karyawan, _link_employee


def _employee(client, headers, name="Pekerja Mobile") -> str:
    resp = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": name, "base_salary": 5_000_000},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _clock(client, headers, direction, lat="-6.2", lng="106.816666"):
    return client.post(
        f"/api/v1/me/attendance/clock-{direction}",
        headers=headers,
        files={"file": ("selfie.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"latitude": lat, "longitude": lng},
    )


def _setup_linked_karyawan(client, name="Pekerja Mobile") -> dict[str, str]:
    admin = _auth_header(client)
    emp_id = _employee(client, admin, name=name)
    emp_headers = _create_karyawan(client)
    _link_employee(client, emp_id)
    return admin, emp_headers, emp_id


def test_clock_in_out_flow_dan_duplikat(client):
    admin, emp, emp_id = _setup_linked_karyawan(client)

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        cin = _clock(client, emp, "in")
    assert cin.status_code == 200, cin.text
    body = cin.json()
    assert body["direction"] == "in"
    assert body["geo"] == "-6.2,106.816666"
    assert body["status"] == "hadir"

    # Clock-in kedua hari yang sama ditolak
    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        dup = _clock(client, emp, "in")
    assert dup.status_code == 409

    # Clock-out sukses lalu ditolak bila diulang
    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        cout = _clock(client, emp, "out")
    assert cout.status_code == 200, cout.text

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        again = _clock(client, emp, "out")
    assert again.status_code == 409

    # Record harian terlihat oleh HR dengan flag selfie + koordinat
    today = date.today()
    rows = client.get(
        f"/api/v1/attendance/records?year={today.year}&month={today.month}&employee_id={emp_id}",
        headers=admin,
    ).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "mobile"
    assert row["has_clock_in_selfie"] is True
    assert row["has_clock_out_selfie"] is True
    assert row["clock_in_geo"] and row["clock_out_geo"]


def test_clock_validasi_akun_koordinat_dan_format(client):
    _auth_header(client)
    emp_headers = _create_karyawan(client)

    # Akun belum tertaut karyawan → 404
    no_link = _clock(client, emp_headers, "in")
    assert no_link.status_code == 404

    admin = _auth_header(client)
    emp_id = _employee(client, admin)
    _link_employee(client, emp_id, email="karyawan@outsourcing.co.id")

    # Koordinat di luar jangkauan → 422
    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        bad_coord = _clock(client, emp_headers, "in", lat="999")
    assert bad_coord.status_code == 422

    # Format bukan gambar → 422
    bad_mime = client.post(
        "/api/v1/me/attendance/clock-in",
        headers=emp_headers,
        files={"file": ("selfie.pdf", b"%PDF-1.4", "application/pdf")},
        data={"latitude": "-6.2", "longitude": "106.8"},
    )
    assert bad_mime.status_code == 422


def test_record_manual_memblokir_clock_in(client):
    from tests.test_attendance import _record as make_record

    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Manual")
    make_record(client, admin, emp_id, day=str(date.today()))

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        dup = _clock(client, emp, "in")
    assert dup.status_code == 409


def test_selfie_url_hanya_role_berwenang_dan_pemilik(client):
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Selfie")

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        cin = _clock(client, emp, "in")
    record_id = cin.json()["id"]

    url_admin = client.get(
        f"/api/v1/attendance/records/{record_id}/selfie/in/download-url", headers=admin
    )
    assert url_admin.status_code == 200
    assert "url" in url_admin.json()

    # Role karyawan tidak boleh lihat selfie via endpoint HR
    forbidden = client.get(
        f"/api/v1/attendance/records/{record_id}/selfie/in/download-url", headers=emp
    )
    assert forbidden.status_code == 403

    # Pemilik boleh lewat portal /me
    own = client.get(f"/api/v1/me/attendance/{record_id}/selfie/in/download-url", headers=emp)
    assert own.status_code == 200
