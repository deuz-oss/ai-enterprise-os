"""Fase 8 lanjutan — Mobile GPS+selfie clock in/out (portal & app mobile)."""

from datetime import date
from unittest.mock import patch

import pytest

from tests.conftest import _auth_header
from tests.test_ess import _create_karyawan, _link_employee
from tests.test_recruitment import _client_id


@pytest.fixture(autouse=True)
def _no_real_geocoding():
    """`mobile_clock` panggil reverse_geocode nyata (HTTP ke Nominatim) --
    default-kan ke None (simulasi gagal/tidak tersedia) di semua test file
    ini supaya tidak ada panggilan jaringan sungguhan. Test yang perlu
    verifikasi alamat tersimpan override ini sendiri per-test."""
    with patch("app.core.geocoding.reverse_geocode", return_value=None) as mock:
        yield mock


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


def test_attendance_today_mengikuti_state_clock_in_out(client):
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Today")

    belum = client.get("/api/v1/me/attendance/today", headers=emp)
    assert belum.status_code == 200
    assert belum.json() is None

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        _clock(client, emp, "in")

    setelah_in = client.get("/api/v1/me/attendance/today", headers=emp).json()
    assert setelah_in["clock_in"] is not None
    assert setelah_in["clock_out"] is None
    assert setelah_in["has_clock_in_selfie"] is True
    assert setelah_in["has_clock_out_selfie"] is False

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        _clock(client, emp, "out")

    setelah_out = client.get("/api/v1/me/attendance/today", headers=emp).json()
    assert setelah_out["clock_in"] is not None
    assert setelah_out["clock_out"] is not None
    assert setelah_out["has_clock_out_selfie"] is True


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


# ---------- Geofencing per lokasi klien (Fase 34) ----------

_SITE_LAT = "-6.200000"
_SITE_LNG = "106.816666"


def _create_site(client, headers, client_id, radius_meters=100):
    resp = client.post(
        f"/api/v1/clients/{client_id}/sites",
        headers=headers,
        json={
            "name": "Kantor Klien",
            "latitude": _SITE_LAT,
            "longitude": _SITE_LNG,
            "radius_meters": radius_meters,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_clock_in_tanpa_site_id_tetap_bebas(client):
    """Regresi: karyawan tanpa site_id (perilaku lama) tidak pernah dicek jarak,
    walau koordinatnya jauh dari mana pun."""
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Bebas")

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        jauh = _clock(client, emp, "in", lat="-8.65", lng="115.2167")  # Bali, jauh dari mana pun
    assert jauh.status_code == 200, jauh.text


def test_clock_in_dalam_radius_site_lolos(client):
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Radius Lolos")
    cid = _client_id(client, admin)
    site = _create_site(client, admin, cid, radius_meters=100)
    assert (
        client.patch(
            f"/api/v1/employees/{emp_id}", headers=admin, json={"site_id": site["id"]}
        ).status_code
        == 200
    )

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        # Tepat di titik site -> jarak 0.
        ok = _clock(client, emp, "in", lat=_SITE_LAT, lng=_SITE_LNG)
    assert ok.status_code == 200, ok.text


def test_clock_in_di_luar_radius_site_ditolak(client):
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Radius Tolak")
    cid = _client_id(client, admin)
    site = _create_site(client, admin, cid, radius_meters=100)
    assert (
        client.patch(
            f"/api/v1/employees/{emp_id}", headers=admin, json={"site_id": site["id"]}
        ).status_code
        == 200
    )

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        # Bandung, puluhan km dari titik site -> jauh di luar radius 100m.
        jauh = _clock(client, emp, "in", lat="-6.9175", lng="107.6191")
    assert jauh.status_code == 422
    assert "radius" in jauh.json()["detail"].lower()

    # Record hari ini belum tercatat (ditolak sebelum simpan)
    today = client.get("/api/v1/me/attendance/today", headers=emp).json()
    assert today is None


def test_clock_in_site_dihapus_fail_open(client):
    """Site dihapus (via lepas tautan dulu) tapi employee.site_id tersisa
    (skenario tak terduga) -- tidak boleh memblokir absensi sama sekali."""
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Site Hilang")
    cid = _client_id(client, admin)
    site = _create_site(client, admin, cid, radius_meters=50)
    client.patch(f"/api/v1/employees/{emp_id}", headers=admin, json={"site_id": site["id"]})

    # Hapus site langsung lewat DB (bukan endpoint -- endpoint akan menolak
    # karena masih direferensikan employee, skenario ini sengaja simulasi
    # data yatim yang seharusnya tidak terjadi lewat jalur normal).
    db = client.testing_session()
    try:
        from app.core.database import parse_uuid
        from app.modules.clients.models import ClientSite

        row = db.get(ClientSite, parse_uuid(site["id"]))
        db.delete(row)
        db.commit()
    finally:
        db.close()

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        jauh = _clock(client, emp, "in", lat="-8.65", lng="115.2167")
    assert jauh.status_code == 200, jauh.text


# ---------- Reverse geocoding alamat absensi (Fase 36) ----------


def test_clock_in_alamat_tersimpan_saat_geocoding_sukses(client):
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Geo Sukses")

    with (
        patch("app.core.geocoding.reverse_geocode", return_value="Jl. Sudirman, Jakarta"),
        patch("app.modules.ess.service.storage.put_object") as put,
    ):
        put.return_value = "key"
        cin = _clock(client, emp, "in")
    assert cin.status_code == 200, cin.text
    assert cin.json()["address"] == "Jl. Sudirman, Jakarta"

    today = client.get("/api/v1/me/attendance/today", headers=emp).json()
    assert today["clock_in_address"] == "Jl. Sudirman, Jakarta"


def test_clock_in_tetap_sukses_walau_geocoding_gagal(client):
    """`_no_real_geocoding` sudah default None (simulasi gagal) -- pastikan
    clock-in TETAP 200, bukan ikut gagal gara-gara geocoding best-effort."""
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Geo Gagal")

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        cin = _clock(client, emp, "in")
    assert cin.status_code == 200, cin.text
    assert cin.json()["address"] is None

    today = client.get("/api/v1/me/attendance/today", headers=emp).json()
    assert today["clock_in_address"] is None


# ---------- Strip kalender mingguan (Fase 36) ----------


def test_attendance_week_7_hari_dan_status_benar(client):
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Minggu")

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        _clock(client, emp, "in")

    week = client.get("/api/v1/me/attendance/week", headers=emp)
    assert week.status_code == 200, week.text
    days = week.json()
    assert len(days) == 7
    today_str = date.today().isoformat()
    today_entry = next(d for d in days if d["date"] == today_str)
    assert today_entry["status"] == "hadir"
    assert today_entry["clock_in"] is not None
    # Hari lain dalam minggu itu (belum ada absensi) -- status None, bukan error.
    other_days = [d for d in days if d["date"] != today_str]
    assert all(d["status"] is None for d in other_days)


# ---------- Shift default per karyawan (Fase 36) ----------


def test_shift_diatur_hr_muncul_di_profil_karyawan(client):
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Shift")

    set_shift = client.patch(
        f"/api/v1/employees/{emp_id}",
        headers=admin,
        json={"shift_start_time": "09:00:00", "shift_end_time": "18:00:00"},
    )
    assert set_shift.status_code == 200, set_shift.text

    profile = client.get("/api/v1/me/profile", headers=emp).json()
    assert profile["shift_start_time"] == "09:00:00"
    assert profile["shift_end_time"] == "18:00:00"


# ---------- Regresi: clock-in mobile harus ikut Rekap Kehadiran ----------


def test_clock_in_mobile_terefleksi_di_rekap_bulanan(client):
    """Bug ditemukan Brian: absen mobile tidak pernah memicu
    `recompute_month_summary`, jadi Rekap Kehadiran (AttendanceSummary,
    /me/attendance) tidak pernah ikut ter-update walau AttendanceRecord-nya
    ada."""
    admin, emp, emp_id = _setup_linked_karyawan(client, name="Pekerja Rekap")

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        cin = _clock(client, emp, "in")
    assert cin.status_code == 200, cin.text

    today = date.today()
    rekap = client.get(
        f"/api/v1/me/attendance?year={today.year}&month={today.month}", headers=emp
    ).json()
    assert len(rekap) == 1
    assert rekap[0]["present_days"] == 1

    with patch("app.modules.ess.service.storage.put_object") as put:
        put.return_value = "key"
        _clock(client, emp, "out")

    rekap_setelah_keluar = client.get(
        f"/api/v1/me/attendance?year={today.year}&month={today.month}", headers=emp
    ).json()
    assert rekap_setelah_keluar[0]["present_days"] == 1
