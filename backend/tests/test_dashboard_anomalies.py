"""Penjelasan perubahan besar KPI dashboard (dashboard/anomalies.py, peluang AI #10)."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from app.core.bootstrap import ensure_default_tenant
from app.core.tenancy import get_tenant, set_tenant
from app.modules.clients.models import Client
from app.modules.dashboard.anomalies import _last_two_full_months, kpi_anomalies
from app.modules.finance.models import Invoice, InvoiceStatus

from tests.conftest import _auth_header

TODAY = date(2026, 10, 10)  # dua bulan penuh terakhir: Sep 2026 vs Agu 2026


@pytest.fixture()
def tenant_db(client):
    db = client.testing_session()
    previous = get_tenant()
    set_tenant(ensure_default_tenant(db).id)
    try:
        yield db
    finally:
        set_tenant(previous)  # jangan bocorkan konteks tenant ke test lain
        db.close()


def _client(db, name):
    c = Client(id=uuid4(), name=name)
    db.add(c)
    db.flush()
    return c.id


def _invoice(
    db, client_id, year, month, total, paid_on=None, status=InvoiceStatus.sent, issued_on=None
):
    db.add(
        Invoice(
            id=uuid4(),
            client_id=client_id,
            invoice_no=f"INV/{uuid4().hex[:6]}",
            year=year,
            month=month,
            # Default: terbit di bulan setelah periodenya (pola nyata).
            issued_date=issued_on or date(year + month // 12, month % 12 + 1, 3),
            total_due=total,
            status=InvoiceStatus.paid if paid_on else status,
            paid_at=datetime(paid_on.year, paid_on.month, paid_on.day, tzinfo=UTC)
            if paid_on
            else None,
        )
    )


def test_last_two_full_months_handles_year_boundary():
    assert _last_two_full_months(date(2026, 10, 10)) == ((2026, 9), (2026, 8))
    assert _last_two_full_months(date(2026, 2, 3)) == ((2026, 1), (2025, 12))
    assert _last_two_full_months(date(2026, 1, 31)) == ((2025, 12), (2025, 11))


def test_revenue_drop_names_largest_contributor(tenant_db):
    db = tenant_db
    a, b = _client(db, "PT Alfa"), _client(db, "PT Beta")
    # Agu: 10 jt + 10 jt dibayar; Sep: hanya 10 jt + 2 jt -> turun 40%.
    _invoice(db, a, 2026, 7, 10_000_000, paid_on=date(2026, 8, 5))
    _invoice(db, b, 2026, 7, 10_000_000, paid_on=date(2026, 8, 6))
    _invoice(db, a, 2026, 8, 10_000_000, paid_on=date(2026, 9, 5))
    _invoice(db, b, 2026, 8, 2_000_000, paid_on=date(2026, 9, 6))
    # Bulan berjalan (Okt) TIDAK ikut dibanding.
    _invoice(db, a, 2026, 9, 50_000_000, paid_on=date(2026, 10, 2))
    db.commit()

    result = kpi_anomalies(db, today=TODAY)
    revenue = next(i for i in result["items"] if i["kpi"] == "revenue_collected")
    assert (revenue["period"], revenue["compared_to"]) == ("Sep 2026", "Agu 2026")
    assert revenue["change_pct"] == pytest.approx(-0.4)
    assert [d["name"] for d in revenue["drivers"]] == ["PT Beta"]  # Alfa tidak berubah
    assert revenue["drivers"][0]["delta"] == -8_000_000
    assert revenue["sentence"] == (
        "Kas masuk dari invoice Sep 2026 turun 40% dari Agu 2026 "
        "(Rp20.000.000 → Rp12.000.000), terbesar dari PT Beta (−Rp8.000.000)."
    )


def test_billed_grouped_by_issue_month_not_period(tenant_db):
    db = tenant_db
    a = _client(db, "PT Gamma")
    _invoice(db, a, 2026, 7, 10_000_000)  # terbit 3 Agu
    _invoice(db, a, 2026, 8, 15_000_000)  # terbit 3 Sep
    # Periode Sep belum ditagih per 10 Okt -- dulu tampil "turun 100%" palsu;
    # terbit di Okt (bulan berjalan) tidak ikut dibanding.
    _invoice(db, a, 2026, 9, 1_000_000)
    # Draft & batal tidak dihitung sebagai penagihan (1 invoice/klien/periode).
    _invoice(db, _client(db, "PT Draft"), 2026, 9, 99_000_000, status=InvoiceStatus.draft)
    _invoice(db, _client(db, "PT Batal"), 2026, 9, 99_000_000, status=InvoiceStatus.cancelled)
    db.commit()

    items = {i["kpi"]: i for i in kpi_anomalies(db, today=TODAY)["items"]}
    assert items["billed"]["change_pct"] == pytest.approx(0.5)
    assert "naik 50%" in items["billed"]["sentence"]
    assert "revenue_collected" not in items


def test_below_threshold_or_tiny_base_is_not_reported(tenant_db):
    db = tenant_db
    a = _client(db, "PT Delta")
    _invoice(db, a, 2026, 7, 10_000_000)
    _invoice(db, a, 2026, 8, 11_000_000)  # +10% < ambang 20%
    b = _client(db, "PT Kecil")
    _invoice(db, b, 2026, 7, 200_000, paid_on=date(2026, 8, 3))  # basis < Rp1 jt
    _invoice(db, b, 2026, 8, 50_000, paid_on=date(2026, 9, 3))
    db.commit()
    assert kpi_anomalies(db, today=TODAY)["items"] == []


def test_endpoint_is_available_to_dashboard_users(client):
    resp = client.get("/api/v1/overview/anomalies", headers=_auth_header(client))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == [] and body["threshold_pct"] == 0.2


def test_payroll_gross_attributed_to_client_via_placement(client, tenant_db, db_engine):
    from sqlalchemy import text

    from tests.test_invoice_reconciliation import _seed

    headers = _auth_header(client)
    _seed(client, headers, salary=5_000_000)  # karyawan ditempatkan di "PT Rekon Absensi"
    for month in (8, 9):
        run = client.post(
            "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": month}
        ).json()["id"]
        resp = client.post(f"/api/v1/payroll/runs/{run}/generate", headers=headers, json={})
        assert resp.status_code == 201, resp.text
    with db_engine.begin() as conn:
        # Run periode Agu final di Agu, periode Sep final di Sep.
        conn.execute(
            text(
                "UPDATE payroll_runs SET status = 'final', "
                "finalized_at = '2026-' || printf('%02d', month) || '-28 10:00:00'"
            )
        )
        # Sep: bruto dinaikkan 50% (mis. lembur besar).
        conn.execute(
            text(
                "UPDATE payslips SET gross = gross * 1.5 WHERE run_id IN "
                "(SELECT id FROM payroll_runs WHERE month = 9)"
            )
        )

    items = {i["kpi"]: i for i in kpi_anomalies(tenant_db, today=TODAY)["items"]}
    payroll = items["payroll_gross"]
    assert payroll["change_pct"] == pytest.approx(0.5)
    assert payroll["drivers"][0]["name"] == "PT Rekon Absensi"
    assert payroll["link"] == "/payroll"
