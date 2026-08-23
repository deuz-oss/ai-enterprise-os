from tests.conftest import _auth_header


def _entry_payload(**overrides) -> dict:
    payload = {
        "entry_date": "2026-08-01",
        "description": "Setor modal awal",
        "lines": [
            {"account_code": "1-1100", "debit": 100_000_000, "credit": 0},
            {"account_code": "3-1000", "debit": 0, "credit": 100_000_000},
        ],
    }
    payload.update(overrides)
    return payload


def test_create_and_list_journal_entry(client):
    headers = _auth_header(client)
    resp = client.post("/api/v1/accounting/journal", headers=headers, json=_entry_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["lines"]) == 2

    listed = client.get(
        "/api/v1/accounting/journal", headers=headers, params={"year": 2026}
    ).json()
    assert len(listed) == 1


def test_unbalanced_entry_rejected(client):
    headers = _auth_header(client)
    bad = _entry_payload(
        lines=[
            {"account_code": "1-1100", "debit": 100, "credit": 0},
            {"account_code": "3-1000", "debit": 0, "credit": 90},
        ]
    )
    resp = client.post("/api/v1/accounting/journal", headers=headers, json=bad)
    assert resp.status_code == 422


def test_unknown_account_rejected(client):
    headers = _auth_header(client)
    bad = _entry_payload(
        lines=[
            {"account_code": "9-9999", "debit": 100, "credit": 0},
            {"account_code": "1-1100", "debit": 0, "credit": 100},
        ]
    )
    resp = client.post("/api/v1/accounting/journal", headers=headers, json=bad)
    assert resp.status_code == 422


def test_trial_balance_and_income_statement(client):
    headers = _auth_header(client)

    # Pendapatan fee 10jt (kas masuk) & beban gaji 6jt (kas keluar)
    entries = [
        {
            "entry_date": "2026-08-05",
            "description": "Fee management Juli",
            "lines": [
                {"account_code": "1-1100", "debit": 10_000_000, "credit": 0},
                {"account_code": "4-1000", "debit": 0, "credit": 10_000_000},
            ],
        },
        {
            "entry_date": "2026-08-28",
            "description": "Bayar gaji Juli",
            "lines": [
                {"account_code": "5-1000", "debit": 6_000_000, "credit": 0},
                {"account_code": "1-1100", "debit": 0, "credit": 6_000_000},
            ],
        },
    ]
    for e in entries:
        resp = client.post("/api/v1/accounting/journal", headers=headers, json=e)
        assert resp.status_code == 201, resp.text

    tb = client.get(
        "/api/v1/accounting/trial-balance", headers=headers, params={"year": 2026}
    ).json()
    bank = next(r for r in tb if r["account_code"] == "1-1100")
    assert float(bank["total_debit"]) == 10_000_000
    assert float(bank["total_credit"]) == 6_000_000

    is_report = client.get(
        "/api/v1/accounting/reports/income-statement", headers=headers, params={"year": 2026}
    ).json()
    assert is_report["total_revenue"] == 10_000_000
    assert is_report["total_expense"] == 6_000_000
    assert is_report["net_income"] == 4_000_000


def test_balance_sheet(client):
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/accounting/journal", headers=headers, json=_entry_payload()
    )
    assert resp.status_code == 201

    bs = client.get(
        "/api/v1/accounting/reports/balance-sheet",
        headers=headers,
        params={"as_of": "2026-12-31"},
    ).json()
    assert float(bs["assets"]["total"]) == 100_000_000
    assert float(bs["equity"]["total"]) == 100_000_000
    assert float(bs["liabilities"]["total"]) == 0


def test_ledger_running_balance(client):
    headers = _auth_header(client)
    for debit, credit in [(5_000_000, 0), (2_000_000, 0)]:
        entry = {
            "entry_date": "2026-09-01",
            "description": "Kas masuk",
            "lines": [
                {"account_code": "1-1000", "debit": debit, "credit": credit},
                {"account_code": "4-2000", "debit": credit, "credit": debit},
            ],
        }
        client.post("/api/v1/accounting/journal", headers=headers, json=entry)

    result = client.get(
        "/api/v1/accounting/ledger/1-1000", headers=headers, params={"year": 2026}
    ).json()
    balances = [line["balance"] for line in result["lines"]]
    assert balances == [5_000_000.0, 7_000_000.0]
