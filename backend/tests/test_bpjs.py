"""Test modul BPJS: engine iuran, rekap API, dan ekspor CSV."""

from app.modules.bpjs.engine import DEFAULT_JKK_CATEGORY, compute_contribution

from tests.conftest import _auth_header

# ---- Unit engine ----


def test_iuran_gaji_di_bawah_cap():
    b = compute_contribution(5_000_000)
    # Kesehatan 4%+1% dari 5jt
    assert b.kes_employer == 200_000
    assert b.kes_employee == 50_000
    # JHT 3,7%+2% dari 5jt
    assert b.jht_employer == 185_000
    assert b.jht_employee == 100_000
    # JP 2%+1% dari 5jt (di bawah cap)
    assert b.jp_employer == 100_000
    assert b.jp_employee == 50_000
    # JKM 0,3% & JKK default kategori 2 (0,38%)
    assert b.jkm == 15_000
    assert b.jkk == round(5_000_000 * 0.0038)
    assert DEFAULT_JKK_CATEGORY == 2


def test_cap_kesehatan_dan_jp():
    gaji = 20_000_000
    b = compute_contribution(gaji)
    # Kesehatan di-cap 12jt → 480rb + 120rb
    assert b.salary_kesehatan == 12_000_000
    assert b.kes_employer == 480_000
    assert b.kes_employee == 120_000
    # JP di-cap 10.547.400
    assert b.salary_jp == 10_547_400
    assert b.jp_employer == round(10_547_400 * 0.02)
    # JHT/JKK/JKM tanpa cap
    assert b.jht_employer == round(20_000_000 * 0.037)


def test_jkk_mengikuti_kategori_risiko():
    gaji = 10_000_000
    tarif = {kat: compute_contribution(gaji, kat).jkk for kat in range(1, 6)}
    assert tarif[1] == round(gaji * 0.0024)
    assert tarif[3] == round(gaji * 0.0054)
    assert tarif[5] > tarif[1]
    # Tanpa parameter → pakai default kategori 2
    assert compute_contribution(gaji).jkk == compute_contribution(gaji, None).jkk


def test_total_adalah_penjumlahan_komponen():
    b = compute_contribution(7_500_000, 4)
    assert b.grand_total == b.employer_total + b.employee_total
    assert b.employer_total == (b.kes_employer + b.jkk + b.jkm + b.jht_employer + b.jp_employer)


# ---- API ----


def _create_employee(client, headers, name="Budi BPJS", salary=8_000_000, jkk=None) -> dict:
    body: dict = {"full_name": name, "base_salary": salary}
    if jkk:
        body["jkk_risk_category"] = jkk
    resp = client.post("/api/v1/employees", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_rekap_hanya_karyawan_aktif(client):
    headers = _auth_header(client)
    _create_employee(client, headers, "Aktif Satu")
    _create_employee(client, headers, salary=6_000_000)
    resign = _create_employee(client, headers, "Yang Resign")
    client.patch(
        f"/api/v1/employees/{resign['id']}",
        headers=headers,
        json={"status": "resign"},
    )

    recap = client.get("/api/v1/bpjs/contributions/2026/8", headers=headers).json()
    names = {r["full_name"] for r in recap["rows"]}
    assert names == {"Aktif Satu", "Budi BPJS"}
    assert len(recap["rows"]) == 2
    assert recap["summary"]["grand_total"] == sum(r["grand_total"] for r in recap["rows"])


def test_export_csv_iuran(client):
    headers = _auth_header(client)
    _create_employee(client, headers, name="Citra CSV")

    resp = client.get("/api/v1/bpjs/contributions/2026/8/export", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "bpjs-iuran-202608.csv" in resp.headers["content-disposition"]
    text = resp.text
    assert "Citra CSV" in text
    assert "Iuran Kesehatan" in text  # header kolom ada
    lines = [line for line in text.strip().splitlines() if line]
    assert any("TOTAL" in line for line in lines)


def test_export_csv_pendaftaran_peserta(client):
    headers = _auth_header(client)
    emp = _create_employee(client, headers, name="Dedi Daftar")
    client.patch(
        f"/api/v1/employees/{emp['id']}",
        headers=headers,
        json={"ktp_no": "3578010101900001", "phone": "081234567890"},
    )

    resp = client.get("/api/v1/bpjs/enrollments/export", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "bpjs-peserta-" in resp.headers["content-disposition"]
    assert "Dedi Daftar" in resp.text
    assert "3578010101900001" in resp.text


def test_periode_tidak_wajar_mengembalikan_422(client):
    headers = _auth_header(client)
    resp = client.get("/api/v1/bpjs/contributions/2026/13", headers=headers)
    assert resp.status_code == 422


def test_role_recruiter_ditolak(client):
    admin = _auth_header(client)
    reg = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={
            "email": "rec-bpjs@example.com",
            "full_name": "Recruiter",
            "password": "password123",
            "role": "recruiter",
        },
    )
    assert reg.status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "rec-bpjs@example.com", "password": "password123"},
    ).json()["access_token"]
    resp = client.get(
        "/api/v1/bpjs/contributions/2026/8",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
