"""Fase 10 sisa AI — OCR faktur, rekonsiliasi bank cerdas, prediksi pembayaran klien."""

from datetime import date, timedelta
from io import BytesIO

from tests.conftest import _auth_header

# ---------- Prediksi pembayaran klien (deterministik) ----------


def _seed_invoices(client, rows: list[dict]):
    """Seed klien + invoice langsung via DB (skor dari histori, bukan alur payrol)."""
    from app.core.bootstrap import ensure_default_tenant
    from app.modules.clients.models import Client
    from app.modules.finance.models import Invoice, InvoiceStatus

    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
        clients: dict[str, object] = {}
        for spec in rows:
            name = spec["client"]
            if name not in clients:
                c = Client(name=name, tenant_id=tenant.id)
                db.add(c)
                db.flush()
                clients[name] = c
            inv = Invoice(
                client_id=clients[name].id,
                tenant_id=tenant.id,
                invoice_no=spec["invoice_no"],
                year=spec["date"].year,
                month=spec["date"].month,
                total_due=spec["total_due"],
                status=InvoiceStatus.sent,
                issued_date=spec["date"],
                due_date=spec["due"],
            )
            if spec.get("paid_at"):
                inv.paid_at = spec["paid_at"]
            db.add(inv)
        db.commit()
    finally:
        db.close()


def test_payment_prediction_ranks_late_payers_first(client):
    admin = _auth_header(client)
    today = date.today()
    _seed_invoices(
        client,
        [
            # Klien Rajin: dua invoice lunas tepat waktu + satu berjalan belum jatuh tempo
            {
                "client": "PT Rajin",
                "invoice_no": "INV/R/1",
                "total_due": 10_000_000,
                "date": today - timedelta(days=95),
                "due": today - timedelta(days=65),
                "paid_at": today - timedelta(days=70),
            },
            {
                "client": "PT Rajin",
                "invoice_no": "INV/R/2",
                "total_due": 10_000_000,
                "date": today - timedelta(days=65),
                "due": today - timedelta(days=35),
                "paid_at": today - timedelta(days=40),
            },
            {
                "client": "PT Rajin",
                "invoice_no": "INV/R/3",
                "total_due": 8_000_000,
                "date": today,
                "due": today + timedelta(days=20),
            },
            # Klien Telat: dua invoice lunas sangat terlambat + satu overdue berjalan
            # (bulan berbeda agar tidak clash unique client/year/month)
            {
                "client": "CV Telat",
                "invoice_no": "INV/T/1",
                "total_due": 12_000_000,
                "date": today - timedelta(days=120),
                "due": today - timedelta(days=90),
                "paid_at": today - timedelta(days=50),  # telat 40 hari
            },
            {
                "client": "CV Telat",
                "invoice_no": "INV/T/2",
                "total_due": 12_000_000,
                "date": today - timedelta(days=60),
                "due": today - timedelta(days=30),
                "paid_at": today - timedelta(days=20),  # telat 10 hari
            },
            {
                "client": "CV Telat",
                "invoice_no": "INV/T/3",
                "total_due": 9_000_000,
                "date": today - timedelta(days=45),
                "due": today - timedelta(days=15),  # overdue 15 hari
            },
        ],
    )

    res = client.get("/api/v1/accounting/ai/payment-prediction", headers=admin)
    assert res.status_code == 200, res.text
    data = res.json()
    ranked = {r["client_name"]: r for r in data["clients_ranked"]}

    rajin = ranked["PT Rajin"]
    telat = ranked["CV Telat"]
    assert telat["risk_score"] > rajin["risk_score"]
    assert telat["late_ratio"] == 1.0
    assert rajin["late_ratio"] == 0.0
    assert telat["overdue_total"] == 9_000_000
    assert rajin["overdue_total"] == 0

    # Prioritas collection: CV Telat di urutan pertama
    assert data["clients_ranked"][0]["client_name"] == "CV Telat"
    assert data["summary"]["total_overdue"] == 9_000_000


# ---------- Rekonsiliasi bank cerdas ----------


def _csv_file(content: str) -> dict[str, object]:
    return {
        "file": ("koran.csv", BytesIO(content.encode("utf-8")), "text/csv"),
    }


def test_bank_statement_import_match_confirm_ignore(client):
    admin = _auth_header(client)
    accounts = client.get("/api/v1/accounting/accounts", headers=admin).json()
    by_code = {a["code"]: a["id"] for a in accounts}

    # Transaksi sistem yang belum terekonsiliasi
    tx = client.post(
        "/api/v1/accounting/cashbank/transactions",
        headers=admin,
        json={
            "tx_type": "penerimaan",
            "bank_account_id": by_code["1-1100"],
            "amount": 15_000_000,
            "tx_date": str(date.today()),
            "description": "Pembayaran invoice PT Maju Jaya",
        },
    )
    assert tx.status_code == 201

    template = client.get("/api/v1/accounting/cashbank/statement/template", headers=admin)
    assert template.status_code == 200
    assert "tanggal" in template.text

    csv_content = (
        "tanggal;keterangan;mutasi_masuk;mutasi_keluar\n"
        f"{date.today()};TRANSFER MASUK PT MAJU JAYA;15000000;0\n"
        f"{date.today()};BIAYA ADMIN BULANAN;0;25000\n"
    )
    imp = client.post(
        "/api/v1/accounting/cashbank/statement/import",
        headers=admin,
        files=_csv_file(csv_content),
    )
    assert imp.status_code == 200, imp.text
    result = imp.json()
    assert result["inserted"] == 2
    assert result["failed"] == []

    lines = client.get("/api/v1/accounting/cashbank/statement", headers=admin).json()
    by_desc_in = next(ln for ln in lines if ln["amount_in"] == 15_000_000)
    admin_fee = next(ln for ln in lines if ln["amount_out"] == 25_000)

    # Baris besar → usulan match ke transaksi sistem
    assert by_desc_in["status"] == "usulan"
    assert by_desc_in["suggested_tx_id"] is not None
    assert by_desc_in["match_score"] >= 0.75

    # Baris tanpa pasangan → belum cocok + alasan bisa dibaca
    assert admin_fee["status"] == "belum_cocok"
    assert admin_fee["match_reason"]

    # Konfirmasi usulan → baris tercocok + transaksi terekonsiliasi
    conf = client.post(
        f"/api/v1/accounting/cashbank/statement/{by_desc_in['id']}/match",
        headers=admin,
        json={"bank_transaction_id": by_desc_in["suggested_tx_id"]},
    )
    assert conf.status_code == 200, conf.text
    txs = client.get(
        f"/api/v1/accounting/cashbank/transactions?reconciled=true&year={date.today().year}",
        headers=admin,
    ).json()
    assert any(t["id"] == by_desc_in["suggested_tx_id"] for t in txs)

    # Abaikan baris biaya admin
    ign = client.post(
        f"/api/v1/accounting/cashbank/statement/{admin_fee['id']}/ignore", headers=admin
    )
    assert ign.status_code == 200
    assert ign.json()["status"] == "diabaikan"


def test_bank_statement_import_reports_bad_rows_and_duplicates(client):
    admin = _auth_header(client)
    csv_content = (
        "tanggal;keterangan;mutasi_masuk;mutasi_keluar\n"
        "bukan-tanggal;SALAH FORMAT;1000;0\n"
        ";TANPA TANGGAL;1000;0\n"
        f"{date.today()};DUPLIKAT NOL;0;0\n"
    )
    first = client.post(
        "/api/v1/accounting/cashbank/statement/import",
        headers=admin,
        files=_csv_file(csv_content),
    )
    assert first.status_code == 200, first.text
    assert len(first.json()["failed"]) == 3

    good = f"tanggal;keterangan;mutasi_masuk;mutasi_keluar\n{date.today()};UNIK ABC;500000;0\n"
    ok1 = client.post(
        "/api/v1/accounting/cashbank/statement/import", headers=admin, files=_csv_file(good)
    )
    assert ok1.status_code == 200 and ok1.json()["inserted"] == 1

    ok2 = client.post(
        "/api/v1/accounting/cashbank/statement/import", headers=admin, files=_csv_file(good)
    )
    assert ok2.status_code == 200
    assert ok2.json()["inserted"] == 0
    assert len(ok2.json()["duplicates"]) == 1


# ---------- OCR faktur (butuh AI dikonfigurasi) ----------


def test_ocr_bill_rejects_invalid_type_and_needs_ai(client):
    admin = _auth_header(client)

    bad = client.post(
        "/api/v1/accounting/ai/ocr-bill",
        headers=admin,
        files={"file": ("nota.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert bad.status_code == 422

    png = client.post(
        "/api/v1/accounting/ai/ocr-bill",
        headers=admin,
        files={"file": ("nota.png", BytesIO(b"\x89PNG fake"), "image/png")},
    )
    # Tanpa AI_BASE_URL → fitur AI 503 (jangan 500)
    assert png.status_code == 503
