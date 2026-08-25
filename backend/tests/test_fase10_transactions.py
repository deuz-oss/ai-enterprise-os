"""Fase 10 lanjutan — Kas & Bank, Pembelian, Aset Tetap, Arus Kas tidak langsung."""

from tests.conftest import _auth_header


def test_bank_transaction_receipt_payment_transfer(client):
    admin = _auth_header(client)

    # Penerimaan kas: Dr Bank / Cr Pendapatan (default lawan)
    receipt = client.post(
        "/api/v1/accounting/cashbank/transactions",
        headers=admin,
        json={
            "tx_type": "penerimaan",
            "bank_account_id": None,  # akan diisi setelah resolve id akun Bank
            "amount": 5_000_000,
            "description": "Setoran fee",
        },
    )
    # bank_account_id wajib — kirim kode akun via lookup
    accounts = client.get("/api/v1/accounting/accounts", headers=admin).json()
    by_code = {a["code"]: a["id"] for a in accounts}
    assert receipt.status_code == 422  # tanpa bank_account_id

    ok = client.post(
        "/api/v1/accounting/cashbank/transactions",
        headers=admin,
        json={
            "tx_type": "penerimaan",
            "bank_account_id": by_code["1-1100"],
            "amount": 5_000_000,
            "description": "Setoran fee",
        },
    )
    assert ok.status_code == 201, ok.text

    # Pembayaran dengan lawan beban
    pay = client.post(
        "/api/v1/accounting/cashbank/transactions",
        headers=admin,
        json={
            "tx_type": "pembayaran",
            "bank_account_id": by_code["1-1100"],
            "counter_account_id": by_code["5-9000"],
            "amount": 750_000,
        },
    )
    assert pay.status_code == 201

    # Transfer antar rekening: Kas → Bank
    transfer = client.post(
        "/api/v1/accounting/cashbank/transactions",
        headers=admin,
        json={
            "tx_type": "transfer_antar_rekening",
            "bank_account_id": by_code["1-1100"],
            "counter_account_id": by_code["1-1000"],
            "amount": 1_000_000,
        },
    )
    assert transfer.status_code == 201

    # Jurnal otomatis terbentuk per transaksi
    entries = client.get("/api/v1/accounting/journal", headers=admin, params={"year": 2026}).json()
    events = [e.get("event_code") for e in entries]
    assert events.count("cash_receipt") == 1
    assert events.count("cash_payment") == 1
    assert events.count("bank_transfer") == 1

    # Rekonsiliasi
    tx_id = ok.json()["id"]
    rec = client.post(f"/api/v1/accounting/cashbank/transactions/{tx_id}/reconcile", headers=admin)
    assert rec.json()["reconciled"] is True

    listed = client.get(
        "/api/v1/accounting/cashbank/transactions",
        headers=admin,
        params={"year": 2026, "reconciled": True},
    ).json()
    assert len(listed) == 1


def test_purchase_bill_receive_and_pay(client):
    admin = _auth_header(client)
    accounts = client.get("/api/v1/accounting/accounts", headers=admin).json()
    by_code = {a["code"]: a["id"] for a in accounts}
    bank_id = by_code["1-1100"]

    bill = client.post(
        "/api/v1/accounting/purchases",
        headers=admin,
        json={
            "vendor_name": "PT Vendor ATK",
            "expense_account_id": by_code["5-9000"],
            "amount": 2_000_000,
            "ppn_rate": 0.11,
            "bill_number": "VB-001",
        },
    )
    assert bill.status_code == 201, bill.text
    body = bill.json()
    ppn = round(2_000_000 * 0.11)
    # Status belum dibayar; total utang = amount + ppn
    assert body["status"] == "belum_dibayar"

    # Jurnal penerimaan: Dr Beban + Dr PPN Masukan / Cr Utang Usaha
    entries = client.get(
        "/api/v1/accounting/journal",
        headers=admin,
        params={"year": 2026, "event_code": "purchase_received"},
    ).json()
    assert len(entries) == 1
    lines = {l["account_code"]: l for l in entries[0]["lines"]}
    assert float(lines["5-9000"]["debit"]) == 2_000_000
    assert float(lines["1-1400"]["debit"]) == ppn
    assert float(lines["2-1000"]["credit"]) == 2_000_000 + ppn

    # Bayar → Dr Utang / Cr Bank
    paid = client.post(
        f"/api/v1/accounting/purchases/{body['id']}/pay",
        headers=admin,
        json={"bank_account_id": bank_id},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "dibayar"

    paid_events = client.get(
        "/api/v1/accounting/journal",
        headers=admin,
        params={"year": 2026, "event_code": "purchase_paid"},
    ).json()
    plines = {l["account_code"]: l for l in paid_events[0]["lines"]}
    assert float(plines["2-1000"]["debit"]) == 2_000_000 + ppn
    assert float(plines["1-1100"]["credit"]) == 2_000_000 + ppn

    # Bayar ulang ditolak
    again = client.post(
        f"/api/v1/accounting/purchases/{body['id']}/pay",
        headers=admin,
        json={"bank_account_id": bank_id},
    )
    assert again.status_code == 409


def test_fixed_asset_lifecycle_depreciation_disposal(client):
    admin = _auth_header(client)
    accounts = client.get("/api/v1/accounting/accounts", headers=admin).json()
    by_code = {a["code"]: a["id"] for a in accounts}

    asset = client.post(
        "/api/v1/accounting/assets",
        headers=admin,
        json={
            "name": "Laptop Accounting",
            "asset_account_id": by_code["1-2000"],
            "cost": 24_000_000,
            "useful_life_months": 24,
            "acquisition_date": "2026-01-05",
        },
    )
    assert asset.status_code == 201, asset.text
    body = asset.json()
    assert body["monthly_depreciation"] == 1_000_000
    assert body["book_value"] == 24_000_000

    # Penyusutan Jan & Feb 2026
    for m in ("2026-01-01",):
        pass
    jan = client.post(
        f"/api/v1/accounting/assets/{body['id']}/depreciate",
        headers=admin,
        json={"year": 2026, "month": 1},
    )
    assert jan.status_code == 200, jan.text
    feb = client.post(
        f"/api/v1/accounting/assets/{body['id']}/depreciate",
        headers=admin,
        json={"year": 2026, "month": 2},
    )
    assert feb.status_code == 200
    assert feb.json()["accumulated"] == 2_000_000

    # Duplikat bulan yang sama ditolak
    dup = client.post(
        f"/api/v1/accounting/assets/{body['id']}/depreciate",
        headers=admin,
        json={"year": 2026, "month": 2},
    )
    assert dup.status_code == 409

    # Buku nilai berkurang
    listed = client.get("/api/v1/accounting/assets", headers=admin).json()
    row = next(a for a in listed if a["id"] == body["id"])
    assert row["book_value"] == 22_000_000

    # Jurnal penyusutan otomatis (event depreciation_monthly)
    dep_entries = client.get(
        "/api/v1/accounting/journal",
        headers=admin,
        params={"year": 2026, "event_code": "depreciation_monthly"},
    ).json()
    assert len(dep_entries) == 2

    # Disposisi dengan proceeds lebih rendah dari buku nilai → rugi
    dispose = client.post(
        f"/api/v1/accounting/assets/{body['id']}/dispose",
        headers=admin,
        json={"proceeds": 20_000_000},
    )
    assert dispose.status_code == 200

    disp_events = client.get(
        "/api/v1/accounting/journal",
        headers=admin,
        params={"year": 2026, "event_code": "asset_disposed"},
    ).json()
    assert len(disp_events) == 1
    dlines = {l["account_code"]: l for l in disp_events[0]["lines"]}
    # Rugi 2jt masuk 6-1000
    assert float(dlines["6-1000"]["debit"]) == 2_000_000


def test_cash_flow_indirect_structure(client):
    admin = _auth_header(client)

    # Setor modal 50jt, beli aset 10jt (CFI), laba bersih dari fee 12jt - gaji 4jt
    flows = [
        {
            "entry_date": "2026-07-01",
            "description": "Setor modal",
            "lines": [
                {"account_code": "1-1100", "debit": 50_000_000, "credit": 0},
                {"account_code": "3-1000", "debit": 0, "credit": 50_000_000},
            ],
        },
        {
            "entry_date": "2026-08-05",
            "description": "Fee",
            "lines": [
                {"account_code": "1-1100", "debit": 12_000_000, "credit": 0},
                {"account_code": "4-1000", "debit": 0, "credit": 12_000_000},
            ],
        },
        {
            "entry_date": "2026-08-28",
            "description": "Gaji",
            "lines": [
                {"account_code": "5-1000", "debit": 4_000_000, "credit": 0},
                {"account_code": "1-1100", "debit": 0, "credit": 4_000_000},
            ],
        },
    ]
    for fl in flows:
        resp = client.post("/api/v1/accounting/journal", headers=admin, json=fl)
        assert resp.status_code == 201, resp.text

    cf = client.get("/api/v1/accounting/reports/cash-flow-indirect", headers=admin, params={"year": 2026}).json()
    op = cf["operating_activities"]
    assert op["net_income"] == 8_000_000
    # Net change kas harus cocok dengan Δ saldo bank (50jt modal + 12jt fee - 4jt gaji = 58jt)
    assert cf["net_change_cash"] == 58_000_000
