"""Fase 10 — Accounting ala Accurate (core): COA dinamis, periode,
memorial→posted, mesin auto-journal, dimensi klien."""

from tests.conftest import _auth_header


def _entry(headers, client, date="2026-08-05", lines=None, status=None):
    payload = {
        "entry_date": date,
        "description": "Uji jurnal",
        "lines": lines
        or [
            {"account_code": "1-1100", "debit": 1_000_000, "credit": 0},
            {"account_code": "4-1000", "debit": 0, "credit": 1_000_000},
        ],
    }
    if status:
        payload["status"] = status
    return client.post("/api/v1/accounting/journal", headers=headers, json=payload)


def test_coa_seeded_per_tenant(client):
    headers = _auth_header(client)
    accounts = client.get("/api/v1/accounting/accounts", headers=headers).json()
    codes = {a["code"] for a in accounts}
    # Akun inti template outsourcing wajib ada.
    for expected in ("1-1000", "1-1100", "1-1200", "2-1100", "2-1200", "2-1300",
                     "3-2000", "4-1000", "5-1000", "5-3000", "5-5000"):
        assert expected in codes, expected
    bank = next(a for a in accounts if a["code"] == "1-1100")
    assert bank["is_cash_bank"] is True
    piutang = next(a for a in accounts if a["code"] == "1-1200")
    assert piutang["is_control_ar_ap"] is True


def test_coa_crud_and_delete_guard(client):
    headers = _auth_header(client)
    created = client.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "1-1500",
            "name": "Persediaan ATK",
            "group_type": "aset_lancar",
            "normal_balance": "debit",
        },
    )
    assert created.status_code == 201, created.text

    dup = client.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "1-1500", "name": "Duplikat", "group_type": "aset_lancar"},
    )
    assert dup.status_code == 409

    # Akun tanpa mutasi bisa dihapus; akun bermutasi ditolak.
    deleted = client.delete("/api/v1/accounting/accounts/" + created.json()["id"], headers=headers)
    assert deleted.status_code == 204

    mutated = _entry(
        headers,
        client,
        lines=[
            {"account_code": "1-1100", "debit": 500_000, "credit": 0},
            {"account_code": "4-1000", "debit": 0, "credit": 500_000},
        ],
    )
    assert mutated.status_code == 201
    bank_id = next(
        a["id"] for a in client.get("/api/v1/accounting/accounts", headers=headers).json()
        if a["code"] == "1-1100"
    )
    del_blocked = client.delete(f"/api/v1/accounting/accounts/{bank_id}", headers=headers)
    assert del_blocked.status_code == 409


def test_memorial_posting_flow_and_validations(client):
    headers = _auth_header(client)

    # Memorial tidak muncul di laporan posted
    memorial = _entry(headers, client, status="memorial")
    assert memorial.status_code == 201
    assert memorial.json()["status"] == "memorial"

    tb = client.get("/api/v1/accounting/trial-balance", headers=headers, params={"year": 2026}).json()
    bank = next(r for r in tb if r["account_code"] == "1-1100")
    assert float(bank["total_debit"]) == 0

    entry_id = memorial.json()["id"]

    # Tidak seimbang → posting ditolak
    unbalanced = _entry(headers, client, status="memorial", lines=[
        {"account_code": "1-1100", "debit": 100, "credit": 0},
        {"account_code": "4-1000", "debit": 0, "credit": 90},
    ])
    assert unbalanced.status_code == 201  # pembuatan boleh
    unbal_post = client.post(f"/api/v1/accounting/journal/{unbalanced.json()['id']}/post", headers=headers)
    assert unbal_post.status_code == 422

    # Posting valid → masuk laporan
    posted = client.post(f"/api/v1/accounting/journal/{entry_id}/post", headers=headers)
    assert posted.status_code == 200
    assert posted.json()["status"] == "posted"
    again = client.post(f"/api/v1/accounting/journal/{entry_id}/post", headers=headers)
    assert again.status_code == 409


def test_close_period_blocks_backdate(client):
    from datetime import UTC, datetime, timedelta

    admin = _auth_header(client)
    today = datetime.now(UTC).date()
    last_month = (today.replace(day=1) - timedelta(days=1))

    # Tutup bulan lalu
    closed = client.post(
        f"/api/v1/accounting/periods/{last_month.year}/{last_month.month}/close",
        headers=admin,
    )
    assert closed.status_code == 200, closed.text
    periods = client.get("/api/v1/accounting/periods", headers=admin).json()
    target = next(p for p in periods if p["year"] == last_month.year and p["month"] == last_month.month)

    # Input backdate ke periode tertutup ditolak
    back = _entry(admin, client, date=f"{last_month.year}-{str(last_month.month).zfill(2)}-15")
    assert back.status_code == 422
    assert "ditutup" in back.json()["detail"]

    # Reopen → bisa input lagi
    reopen = client.post(
        f"/api/v1/accounting/periods/{last_month.year}/{last_month.month}/reopen", headers=admin
    )
    assert reopen.status_code == 200
    ok = _entry(admin, client, date=f"{last_month.year}-{str(last_month.month).zfill(2)}-15")
    assert ok.status_code == 201
    del target


def test_auto_journal_invoice_and_payroll(client):
    from tests.conftest import _platform_admin_header
    from tests.test_payroll_dua_jalur import _setup as _payroll_setup

    admin = _auth_header(client)
    plat = _platform_admin_header(client)

    # ---- siapkan karyawan aktif agar payrol bisa diproses ----
    client.post("/api/v1/employees", headers=admin, json={"full_name": "Staf Gaji", "base_salary": 4_000_000})

    # ---- invoice_issued ----
    cl = client.post("/api/v1/clients", headers=admin, json={"name": "PT Auto Jurnal"}).json()
    inv = client.post(
        "/api/v1/finance/invoices/generate",
        headers=admin,
        json={"client_id": cl["id"], "year": 2026, "month": 6, "fee_amount": 5_000_000},
    )
    # Belum ada payrol periode tsb → 422; buat payrol internal final dulu
    assert inv.status_code == 422

    run = client.post("/api/v1/payroll/runs", headers=admin, json={"year": 2026, "month": 6}).json()
    client.post("/api/v1/payroll/runs/{0}/generate".format(run["id"]), headers=admin, json={})
    client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)

    inv = client.post(
        "/api/v1/finance/invoices/generate",
        headers=admin,
        json={"client_id": cl["id"], "year": 2026, "month": 6, "fee_amount": 5_000_000},
    )
    assert inv.status_code == 201, inv.text
    inv_id = inv.json()["id"]
    total_due = float(inv.json()["total_due"])

    entries = client.get(
        "/api/v1/accounting/journal", headers=admin, params={"year": 2026}
    ).json()
    issued = [e for e in entries if e.get("event_code") == "invoice_issued"]
    assert len(issued) == 1
    lines = {l["account_code"]: (float(l["debit"]), float(l["credit"])) for l in issued[0]["lines"]}
    assert lines["1-1200"][0] == total_due  # Dr Piutang
    assert lines["4-1000"][1] > 0  # Cr Pendapatan
    assert lines["2-1300"][1] > 0  # Cr PPN Keluaran

    # Idempoten: generate ulang invoice lain untuk periode sama → 409, jurnal tetap 1
    dup = client.post(
        "/api/v1/finance/invoices/generate",
        headers=admin,
        json={"client_id": cl["id"], "year": 2026, "month": 6, "fee_amount": 5_000_000},
    )
    assert dup.status_code == 409

    # ---- payroll_finalized_internal ----
    payroll_events = [e for e in entries if e.get("event_code") == "payroll_finalized_internal"]
    assert len(payroll_events) == 1

    # ---- invoice_paid ----
    paid = client.patch(
        f"/api/v1/finance/invoices/{inv_id}",
        headers=admin,
        json={"status": "dibayar"},
    )
    assert paid.status_code == 200
    entries2 = client.get("/api/v1/accounting/journal", headers=admin, params={"year": 2026}).json()
    paid_events = [e for e in entries2 if e.get("event_code") == "invoice_paid"]
    assert len(paid_events) == 1
    plines = {l["account_code"]: (float(l["debit"]), float(l["credit"])) for l in paid_events[0]["lines"]}
    assert plines["1-1100"][0] == total_due
    assert plines["1-1200"][1] == total_due


def test_pr_executed_auto_journal_and_profit_by_client(client):
    from tests.test_payroll_dua_jalur import _setup

    admin, client_id, emp = _setup(client)
    run = client.post(
        "/api/v1/payroll/runs",
        headers=admin,
        json={"year": 2026, "month": 10, "run_type": "proyek", "client_id": client_id},
    ).json()
    slips = client.post(f"/api/v1/payroll/runs/{run['id']}/generate", headers=admin, json={}).json()

    sub = client.post(f"/api/v1/payroll/runs/{run['id']}/submit-to-client", headers=admin, json={}).json()
    client.post(
        f"/api/v1/payroll/client/{sub['raw_token']}/decision",
        json={"approved": True, "name": "Klien"},
    )
    client.post(f"/api/v1/payroll/runs/{run['id']}/start-processing", headers=admin)
    client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=admin)

    pr = client.post(
        "/api/v1/payment-requests",
        headers=admin,
        json={"pr_type": "proyek", "payroll_run_id": run["id"]},
    ).json()
    client.post(f"/api/v1/payment-requests/{pr['id']}/approve", headers=admin)
    exe = client.post(f"/api/v1/payment-requests/{pr['id']}/execute", headers=admin)
    assert exe.status_code == 200

    entries = client.get(
        "/api/v1/accounting/journal", headers=admin, params={"year": 2026}
    ).json()
    pr_exec = [e for e in entries if e.get("event_code") == "pr_executed"]
    assert len(pr_exec) == 1

    # Laba rugi per kontrak dari dimensi klien pada baris auto-journal proyek
    report = client.get(
        "/api/v1/accounting/reports/profit-by-client",
        headers=admin,
        params={"year": run["year"]},
    ).json()
    pt_klien = next(r for r in report if r["client"] == "PT Klien Proyek")
    assert pt_klien["expense"] > 0  # HPP TK proyek tercatat dengan dimensi klien
