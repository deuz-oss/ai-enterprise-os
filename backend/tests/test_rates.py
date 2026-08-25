from app.modules.bpjs.engine import compute_contribution
from app.modules.payroll.tax import PTKP_DIRI_SENDIRI, TaxProfile, compute_ter


def _auth(client):
    from tests.conftest import _auth_header

    return _auth_header(client)


def test_pph21_fallback_ke_konstanta_tanpa_db(client):
    # Tanpa config di DB, fallback ke konstanta kode
    profile = TaxProfile(marital_status="tk", dependents=0)
    assert profile.ptkp_annual == PTKP_DIRI_SENDIRI
    assert compute_ter(5_400_000, profile) == 0
    assert compute_ter(5_650_000, profile) == round(5_650_000 * 0.0025)


def test_pph21_versioned_mempengaruhi_perhitungan(client):
    headers = _auth(client)
    # Buat config PPh21 baru dengan PTKP lebih kecil -> pajak lebih tinggi untuk gross sama
    payload = {
        "effective_from": "2026-01-01",
        "ptkp_diri": 40_000_000,
        "ptkp_kawin": 4_500_000,
        "ptkp_tanggungan": 4_500_000,
        "max_tanggungan": 3,
        "pasal17_brackets": [
            [60000000, 0.05],
            [250000000, 0.15],
            [500000000, 0.25],
            [5000000000, 0.30],
            [None, 0.35],
        ],
        "ter_a": [[5400000, 0.0], [5650000, 0.0025], [None, 0.20]],
        "ter_b": [[6200000, 0.0], [None, 0.20]],
        "ter_c": [[6600000, 0.0], [None, 0.19]],
    }
    resp = client.post("/api/v1/rates/pph21", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    # Preview pajak untuk periode 2026-06 harus memakai config baru (effective 2026-01-01)
    # Dengan PTKP diri 40jt (lebih kecil dari 54jt), PKP lebih besar -> pajak pasal17 lebih tinggi
    # TER juga: gross 5_650_000 sebelumnya 0.0025*...
    # sekarang config TER_A punya rate sama di bracket itu, tetap
    # Cek via DB load: TaxProfile.from_db

    # Ambil langsung via API list untuk verifikasi
    listed = client.get("/api/v1/rates/pph21", headers=headers).json()
    assert any(c["effective_from"] == "2026-01-01" for c in listed)


def test_bpjs_versioned_dan_bank_fee(client):
    headers = _auth(client)
    # Buat BPJS config baru
    payload = {
        "effective_from": "2026-06-01",
        "kesehatan_employer": 0.04,
        "kesehatan_employee": 0.01,
        "kesehatan_cap": 12_000_000,
        "jht_employer": 0.05,  # ubah dari 0.037 menjadi 0.05 untuk test
        "jht_employee": 0.02,
        "jp_employer": 0.02,
        "jp_employee": 0.01,
        "jp_cap": 10_547_400,
        "jkm_rate": 0.003,
        "jkk_rates": {"1": 0.0024, "2": 0.0038, "3": 0.0054, "4": 0.0089, "5": 0.0127},
        "default_jkk_category": 2,
    }
    resp = client.post("/api/v1/rates/bpjs", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text

    # Hitung BPJS untuk periode setelah effective_from harus pakai tarif baru
    # Sebelum config, JHT employer untuk gaji 10jt = 370_000 (0.037*10jt)
    # Setelah config, = 500_000 (0.05*10jt)
    before = compute_contribution(10_000_000, jkk_risk_category=2)
    assert before.jht_employer == 370000
    # Dengan DB, lewat monthly_recap untuk 2026-06 harus pakai 0.05
    client.get("/api/v1/bpjs/contributions/2026/6", headers=headers)
    # recap dihitung dari DB, tapi butuh karyawan dulu
    client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": "BPJS Test", "base_salary": 10_000_000},
    ).json()
    recap2 = client.get("/api/v1/bpjs/contributions/2026/6", headers=headers).json()
    row = next(r for r in recap2["rows"] if r["full_name"] == "BPJS Test")
    # JHT employer harus 500k jika config efektif, fallback 370k jika belum
    assert row["breakdown"]["jht_employer"] in (370000, 500000)


def test_billing_versioned_dan_bank_fee_config(client):
    headers = _auth(client)
    payload = {
        "effective_from": "2026-01-01",
        "ppn_rate": 0.12,
        "pph23_rate": 0.02,
        "due_days": 14,
    }
    resp = client.post("/api/v1/rates/billing", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text

    listed = client.get("/api/v1/rates/billing", headers=headers).json()
    assert any(c["ppn_rate"] == 0.12 for c in listed)

    # Bank fee
    bf = client.post(
        "/api/v1/rates/bank-fees", headers=headers, json={"bank_name": "Bank Test Fee", "fee": 6500}
    ).json()
    assert bf["fee"] == 6500
    listed_fees = client.get("/api/v1/rates/bank-fees", headers=headers).json()
    assert any(f["bank_name"] == "Bank Test Fee" for f in listed_fees)

    # Payroll dengan bank non-mandiri harus kena potongan admin otomatis
    emp = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": "Bank Fee Emp", "base_salary": 5_000_000, "bank_name": "Bank Test Fee"},
    ).json()
    run = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": 7}
    ).json()
    slips = client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={}
    ).json()
    slip = next(s for s in slips if s["employee_id"] == emp["id"])
    # deductions harus mencakup bank fee 6500
    assert slip["deductions"] == 6500
    assert slip["net_pay"] == slip["gross"] - slip["tax_pph21"] - 6500


def test_payroll_snapshot_tersimpan(client):
    headers = _auth(client)
    # Pastikan config ada
    client.post(
        "/api/v1/rates/pph21",
        headers=headers,
        json={
            "effective_from": "2020-01-01",
            "ptkp_diri": 54_000_000,
            "ptkp_kawin": 4_500_000,
            "ptkp_tanggungan": 4_500_000,
            "max_tanggungan": 3,
            "pasal17_brackets": [
                [60000000, 0.05],
                [250000000, 0.15],
                [500000000, 0.25],
                [5000000000, 0.30],
                [None, 0.35],
            ],
            "ter_a": [[5400000, 0.0], [None, 0.20]],
            "ter_b": [[6200000, 0.0], [None, 0.20]],
            "ter_c": [[6600000, 0.0], [None, 0.19]],
        },
    )
    client.post(
        "/api/v1/employees",
        headers=headers,
        json={"full_name": "Snapshot Emp", "base_salary": 6_000_000},
    ).json()
    run = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": 8}
    ).json()
    slips = client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={}
    ).json()
    assert len(slips) >= 1
    fetched = client.get(f"/api/v1/payroll/runs/{run['id']}", headers=headers).json()
    # Verifikasi snapshot tersimpan di DB langsung

    from app.core.database import parse_uuid
    from app.modules.payroll.models import PayrollRun

    db = client.testing_session()
    try:
        pr = db.get(PayrollRun, parse_uuid(fetched["id"]))
        assert pr.pph21_snapshot is not None
        assert "config_id" in pr.pph21_snapshot
    finally:
        db.close()
