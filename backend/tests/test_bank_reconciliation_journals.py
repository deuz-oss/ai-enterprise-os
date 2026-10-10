"""Rekonsiliasi bank ke jurnal kas/bank + saran aksi (peluang AI #6)."""

from datetime import date, timedelta
from io import BytesIO
from uuid import UUID

from sqlalchemy import select

from tests.conftest import _auth_header
from tests.test_invoice_reconciliation import _run_and_invoice, _seed

BASE = "/api/v1/accounting/cashbank/statement"


def _import(client, headers, rows):
    body = "tanggal;keterangan;mutasi_masuk;mutasi_keluar\n" + "".join(
        f"{d};{desc};{inn};{out}\n" for d, desc, inn, out in rows
    )
    resp = client.post(
        f"{BASE}/import",
        headers=headers,
        files={"file": ("koran.csv", BytesIO(body.encode()), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["failed"] == []
    return {ln["description"]: ln for ln in client.get(BASE, headers=headers).json()}


def _accounts(client, headers):
    return {
        a["code"]: a["id"]
        for a in client.get("/api/v1/accounting/accounts", headers=headers).json()
    }


def _sent_invoice(client, headers):
    client_id, _ = _seed(client, headers)
    _, invoice_id = _run_and_invoice(client, headers, client_id)
    resp = client.patch(
        f"/api/v1/finance/invoices/{invoice_id}", headers=headers, json={"status": "terkirim"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ar_credits(client, invoice_id):
    """Jumlah baris jurnal yang mengkredit piutang 1-1200 untuk pelunasan."""
    from app.modules.accounting.models import JournalEntry, JournalLine

    db = client.testing_session()
    try:
        return db.execute(
            select(JournalLine)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalLine.account_code == "1-1200", JournalLine.credit > 0)
            .execution_options(include_with_loader_criteria=False)
        ).all()
    finally:
        db.close()


def test_invoice_payment_journal_is_matched_not_left_unmatched(client):
    headers = _auth_header(client)
    inv = _sent_invoice(client, headers)
    paid = client.patch(
        f"/api/v1/finance/invoices/{inv['id']}", headers=headers, json={"status": "dibayar"}
    )
    assert paid.status_code == 200, paid.text
    amount = round(inv["total_due"])

    lines = _import(client, headers, [(date.today(), "TRF MASUK PT REKON ABSENSI", amount, 0)])
    line = lines["TRF MASUK PT REKON ABSENSI"]
    # Dulu: selalu "belum_cocok" karena hanya BankTransaction yang dicari.
    assert line["status"] == "usulan", line
    assert line["suggested_journal_id"] and line["suggested_tx_id"] is None
    assert "Pelunasan invoice" in line["suggested_tx_description"]

    resp = client.post(
        f"{BASE}/{line['id']}/match",
        headers=headers,
        json={"journal_entry_id": line["suggested_journal_id"]},
    )
    assert resp.status_code == 200, resp.text
    matched = {ln["id"]: ln for ln in client.get(BASE, headers=headers).json()}[line["id"]]
    assert matched["status"] == "tercocok"
    assert matched["matched_journal_id"] == line["suggested_journal_id"]

    # Jurnal yang sama tidak bisa dipakai baris lain.
    other = _import(client, headers, [(date.today(), "DUPLIKAT LAIN", amount, 0)])["DUPLIKAT LAIN"]
    assert other["suggested_journal_id"] is None
    resp = client.post(
        f"{BASE}/{other['id']}/match",
        headers=headers,
        json={"journal_entry_id": line["suggested_journal_id"]},
    )
    assert resp.status_code == 409


def test_journal_of_bank_transaction_must_be_matched_via_transaction(client):
    headers = _auth_header(client)
    acc = _accounts(client, headers)
    tx = client.post(
        "/api/v1/accounting/cashbank/transactions",
        headers=headers,
        json={"tx_type": "penerimaan", "bank_account_id": acc["1-1100"], "amount": 3_000_000},
    ).json()
    line = _import(client, headers, [(date.today(), "SETORAN", 3_000_000, 0)])["SETORAN"]
    # Kandidat tetap transaksinya, bukan jurnalnya (tidak ada kandidat ganda).
    assert line["suggested_tx_id"] == tx["id"] and line["suggested_journal_id"] is None
    from app.modules.accounting.models import BankTransaction

    db = client.testing_session()
    try:
        tx_journal = db.execute(
            select(BankTransaction.journal_entry_id)
            .where(BankTransaction.id == UUID(tx["id"]))
            .execution_options(include_with_loader_criteria=False)
        ).scalar_one()
    finally:
        db.close()
    assert tx_journal is not None
    resp = client.post(
        f"{BASE}/{line['id']}/match",
        headers=headers,
        json={"journal_entry_id": str(tx_journal)},
    )
    assert resp.status_code == 422


def test_suggest_and_settle_open_invoice_credits_receivable_once(client):
    headers = _auth_header(client)
    inv = _sent_invoice(client, headers)
    amount = round(inv["total_due"])
    paid_on = date.today() - timedelta(days=3)
    line = _import(client, headers, [(paid_on, "TRF DARI KLIEN", amount, 0)])["TRF DARI KLIEN"]
    assert line["status"] == "belum_cocok"

    sug = client.get(f"{BASE}/{line['id']}/suggestions", headers=headers)
    assert sug.status_code == 200, sug.text
    actions = sug.json()["actions"]
    assert actions[0]["kind"] == "settle_invoice" and actions[0]["invoice_id"] == inv["id"]
    assert sug.json()["bank_accounts"]

    before = len(_ar_credits(client, inv["id"]))
    resp = client.post(
        f"{BASE}/{line['id']}/apply",
        headers=headers,
        json={"kind": "settle_invoice", "invoice_id": inv["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "tercocok"

    invoice = client.get(f"/api/v1/finance/invoices/{inv['id']}", headers=headers).json()
    assert invoice["status"] == "dibayar"
    assert invoice["paid_at"].startswith(paid_on.isoformat())  # tanggal mutasi, bukan hari ini
    # Piutang dikredit tepat sekali (jurnal invoice_paid), tidak ada transaksi bank tambahan.
    assert len(_ar_credits(client, inv["id"])) == before + 1
    txs = client.get(
        f"/api/v1/accounting/cashbank/transactions?year={paid_on.year}", headers=headers
    )
    assert txs.status_code == 200, txs.text
    assert txs.json() == []


def test_suggest_and_pay_matching_bill(client):
    headers = _auth_header(client)
    acc = _accounts(client, headers)
    bill = client.post(
        "/api/v1/accounting/purchases",
        headers=headers,
        json={
            "vendor_name": "CV Sumber ATK",
            "expense_account_id": acc["5-9000"],
            "amount": 1_250_000,
        },
    )
    assert bill.status_code == 201, bill.text
    line = _import(client, headers, [(date.today(), "TRF KE CV SUMBER ATK", 0, 1_250_000)])[
        "TRF KE CV SUMBER ATK"
    ]
    actions = client.get(f"{BASE}/{line['id']}/suggestions", headers=headers).json()["actions"]
    assert actions[0]["kind"] == "pay_bill" and actions[0]["bill_id"] == bill.json()["id"]

    resp = client.post(
        f"{BASE}/{line['id']}/apply",
        headers=headers,
        json={"kind": "pay_bill", "bill_id": bill.json()["id"], "bank_account_id": acc["1-1100"]},
    )
    assert resp.status_code == 200, resp.text
    bills = client.get("/api/v1/accounting/purchases", headers=headers).json()
    assert bills[0]["status"] == "dibayar"


def test_keyword_then_history_suggestions_for_admin_fee(client):
    headers = _auth_header(client)
    acc = _accounts(client, headers)
    first = _import(
        client, headers, [(date.today() - timedelta(days=30), "BIAYA ADMIN BULANAN", 0, 25_000)]
    )["BIAYA ADMIN BULANAN"]
    actions = client.get(f"{BASE}/{first['id']}/suggestions", headers=headers).json()["actions"]
    assert actions == [
        {
            "kind": "create_transaction",
            "label": "Catat ke 5-9000 Beban Operasional Lainnya",
            "reason": 'Keterangan memuat "biaya admin"',
            "counter_account_id": acc["5-9000"],
        }
    ]
    resp = client.post(
        f"{BASE}/{first['id']}/apply",
        headers=headers,
        json={**actions[0], "bank_account_id": acc["1-1100"]},
    )
    assert resp.status_code == 200, resp.text

    second = _import(client, headers, [(date.today(), "BIAYA ADMIN BULANAN OKT", 0, 25_000)])[
        "BIAYA ADMIN BULANAN OKT"
    ]
    actions = client.get(f"{BASE}/{second['id']}/suggestions", headers=headers).json()["actions"]
    # Riwayat didahulukan; akun yang sama tidak diulang dari kata kunci.
    assert len(actions) == 1 and actions[0]["reason"].startswith("Mirip mutasi")


def test_apply_rejects_wrong_direction_and_unknown_action(client):
    headers = _auth_header(client)
    inv = _sent_invoice(client, headers)
    line = _import(client, headers, [(date.today(), "KELUAR", 0, round(inv["total_due"]))])[
        "KELUAR"
    ]
    resp = client.post(
        f"{BASE}/{line['id']}/apply",
        headers=headers,
        json={"kind": "settle_invoice", "invoice_id": inv["id"]},
    )
    assert resp.status_code == 422
    resp = client.post(
        f"{BASE}/{line['id']}/apply", headers=headers, json={"kind": "posting_otomatis"}
    )
    assert resp.status_code == 422
    invoice = client.get(f"/api/v1/finance/invoices/{inv['id']}", headers=headers).json()
    assert invoice["status"] == "terkirim"


def test_reversed_payment_journal_is_not_a_cash_candidate(client):
    """Cek gap: jurnal pelunasan yang sudah DIBALIK (dan jurnal pembaliknya)
    bukan mutasi kas nyata -- tidak boleh diusulkan atau dicocokkan."""
    headers = _auth_header(client)
    inv = _sent_invoice(client, headers)
    client.patch(
        f"/api/v1/finance/invoices/{inv['id']}", headers=headers, json={"status": "dibayar"}
    )
    amount = round(inv["total_due"])
    journals = client.get(
        "/api/v1/accounting/journal", headers=headers, params={"year": date.today().year}
    ).json()
    paid = next(e for e in journals if e.get("event_code") == "invoice_paid")
    rev = client.post(
        f"/api/v1/accounting/journal/{paid['id']}/reverse",
        headers=headers,
        json={"reason": "salah input"},
    )
    assert rev.status_code in (200, 201), rev.text

    line = _import(client, headers, [(date.today(), "TRF MASUK", amount, 0)])["TRF MASUK"]
    assert line["status"] == "belum_cocok" and line["suggested_journal_id"] is None
    for journal_id in (paid["id"], rev.json()["id"]):
        resp = client.post(
            f"{BASE}/{line['id']}/match", headers=headers, json={"journal_entry_id": journal_id}
        )
        assert resp.status_code == 422, resp.text


def _journal_of_tx(client, tx_id):
    from app.modules.accounting.models import BankTransaction

    db = client.testing_session()
    try:
        return db.execute(
            select(BankTransaction.journal_entry_id)
            .where(BankTransaction.id == UUID(tx_id))
            .execution_options(include_with_loader_criteria=False)
        ).scalar_one()
    finally:
        db.close()


def test_reversing_a_matched_journal_unmatches_the_statement_line(client):
    headers = _auth_header(client)
    acc = _accounts(client, headers)

    # Jalur 1: baris tercocok langsung ke jurnal (pelunasan invoice).
    inv = _sent_invoice(client, headers)
    client.patch(
        f"/api/v1/finance/invoices/{inv['id']}", headers=headers, json={"status": "dibayar"}
    )
    line = _import(client, headers, [(date.today(), "TRF A", round(inv["total_due"]), 0)])["TRF A"]
    client.post(
        f"{BASE}/{line['id']}/match",
        headers=headers,
        json={"journal_entry_id": line["suggested_journal_id"]},
    )
    client.post(
        f"/api/v1/accounting/journal/{line['suggested_journal_id']}/reverse",
        headers=headers,
        json={"reason": "salah"},
    )

    # Jalur 2: baris tercocok ke transaksi kas-bank, lalu jurnal transaksinya dibalik.
    tx = client.post(
        "/api/v1/accounting/cashbank/transactions",
        headers=headers,
        json={"tx_type": "penerimaan", "bank_account_id": acc["1-1100"], "amount": 2_500_000},
    ).json()
    line2 = _import(client, headers, [(date.today(), "SETORAN B", 2_500_000, 0)])["SETORAN B"]
    client.post(
        f"{BASE}/{line2['id']}/match", headers=headers, json={"bank_transaction_id": tx["id"]}
    )
    client.post(
        f"/api/v1/accounting/journal/{_journal_of_tx(client, tx['id'])}/reverse",
        headers=headers,
        json={"reason": "salah"},
    )

    lines = {ln["id"]: ln for ln in client.get(BASE, headers=headers).json()}
    for lid in (line["id"], line2["id"]):
        assert lines[lid]["status"] == "belum_cocok"
        assert lines[lid]["match_reason"] == "Jurnal pasangannya dibalik -- cocokkan ulang"
        assert lines[lid]["matched_journal_id"] is None and lines[lid]["matched_tx_id"] is None

    # Transaksi yang jurnalnya dibalik tidak lagi jadi kandidat.
    again = _import(client, headers, [(date.today(), "SETORAN C", 2_500_000, 0)])["SETORAN C"]
    assert again["suggested_tx_id"] is None
