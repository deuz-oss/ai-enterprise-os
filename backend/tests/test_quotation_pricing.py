"""Pengaman margin quotation (presales/pricing.py, peluang AI #7)."""

from decimal import Decimal

import pytest
from app.modules.presales.pricing import parse_number
from sqlalchemy import text

from tests.conftest import _auth_header

FIELDS = [
    {"key": "posisi", "label": "Posisi", "type": "text"},
    {"key": "gaji", "label": "Gaji pokok", "type": "number", "role": "base_salary"},
    {"key": "tunj", "label": "Tunjangan", "type": "number", "role": "allowance"},
    {"key": "fee", "label": "Management fee (%)", "type": "number", "role": "management_fee_pct"},
    {"key": "harga", "label": "Harga/orang", "type": "number", "role": "price_per_head"},
    {"key": "hc", "label": "Jumlah orang", "type": "number", "role": "headcount"},
]


def _setup(client, fields=FIELDS):
    headers = _auth_header(client)
    lead = client.post("/api/v1/leads", headers=headers, json={"company_name": "PT Harga Uji"})
    assert lead.status_code == 201, lead.text
    tmpl = client.post(
        "/api/v1/quotation-templates",
        headers=headers,
        json={"name": "Outsourcing per orang", "field_schema": fields},
    )
    assert tmpl.status_code == 201, tmpl.text
    return headers, lead.json()["id"], tmpl.json()


def _check(client, headers, template_id, values, lead_id=None):
    body = {"template_id": template_id, "field_values": values}
    if lead_id:
        body["lead_id"] = lead_id
    resp = client.post("/api/v1/quotations/pricing-check", headers=headers, json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_roles_round_trip_on_template(client):
    _, _, tmpl = _setup(client)
    roles = {f["key"]: f.get("role") for f in tmpl["field_schema"]}
    assert roles["gaji"] == "base_salary" and roles["posisi"] is None


def test_unknown_role_is_rejected(client):
    headers = _auth_header(client)
    resp = client.post(
        "/api/v1/quotation-templates",
        headers=headers,
        json={"name": "X", "field_schema": [{"key": "a", "label": "A", "role": "harga"}]},
    )
    assert resp.status_code == 422


def test_fee_based_price_cost_and_margin_add_up(client):
    headers, _, tmpl = _setup(client)
    rec = _check(
        client, headers, tmpl["id"], {"gaji": "5.000.000", "tunj": 500_000, "fee": "10", "hc": 4}
    )
    ph = rec["per_head"]
    assert rec["applicable"] is True
    assert ph["bpjs_employer"] > 0  # iuran perusahaan dari engine BPJS (Rates)
    assert ph["cost"] == 5_000_000 + 500_000 + ph["bpjs_employer"]
    assert ph["fee"] == round(ph["cost"] * 0.10)
    assert ph["price"] == ph["cost"] + ph["fee"]
    assert ph["margin"] == ph["fee"]
    assert rec["monthly"] == {
        "headcount": 4,
        "price": ph["price"] * 4,
        "cost": ph["cost"] * 4,
        "margin": ph["margin"] * 4,
    }
    assert rec["findings"] == []


def test_price_below_cost_is_flagged_as_loss(client):
    headers, _, tmpl = _setup(client)
    rec = _check(client, headers, tmpl["id"], {"gaji": 5_000_000, "harga": 5_000_000})
    assert rec["per_head"]["margin"] < 0
    assert [f["kind"] for f in rec["findings"]] == ["rugi"]
    assert rec["findings"][0]["severity"] == "high"


def test_thin_margin_and_inconsistent_price(client):
    headers, _, tmpl = _setup(client)
    rec = _check(client, headers, tmpl["id"], {"gaji": 5_000_000, "fee": "2"})
    assert [f["kind"] for f in rec["findings"]] == ["margin_tipis"]

    # Harga diisi manual tapi tidak sama dengan biaya + fee 10%.
    rec = _check(client, headers, tmpl["id"], {"gaji": 5_000_000, "fee": "10", "harga": 9_000_000})
    assert "harga_tidak_konsisten" in {f["kind"] for f in rec["findings"]}


def test_unreadable_value_is_reported_not_treated_as_zero(client):
    headers, _, tmpl = _setup(client)
    rec = _check(client, headers, tmpl["id"], {"gaji": "lima juta", "fee": "10"})
    assert rec["per_head"] is None
    assert [f["kind"] for f in rec["findings"]] == ["tidak_terbaca"]


def test_template_without_roles_is_not_applicable(client):
    headers, _, tmpl = _setup(client, fields=[{"key": "posisi", "label": "Posisi"}])
    rec = _check(client, headers, tmpl["id"], {"posisi": "Operator"})
    assert rec["applicable"] is False and rec["per_head"] is None and rec["findings"] == []


def test_fee_drop_vs_previous_quotation_for_same_lead(client, db_engine):
    headers, lead_id, tmpl = _setup(client)
    first = client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "lead_id": lead_id,
            "template_id": tmpl["id"],
            "field_values": {"gaji": 5_000_000, "fee": "12"},
        },
    )
    assert first.status_code == 201, first.text
    # created_at beresolusi detik: mundurkan supaya urutan tidak seri.
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE quotations SET created_at = '2026-01-01 00:00:00'"))

    rec = _check(client, headers, tmpl["id"], {"gaji": 5_000_000, "fee": "8"}, lead_id=lead_id)
    assert rec["history"] == {"count": 1, "last_fee_pct": 12.0, "median_fee_pct": 12.0}
    assert "fee_turun" in {f["kind"] for f in rec["findings"]}

    second = client.post(
        "/api/v1/quotations",
        headers=headers,
        json={
            "lead_id": lead_id,
            "template_id": tmpl["id"],
            "field_values": {"gaji": 5_000_000, "fee": "8"},
        },
    ).json()
    # Quotation tersimpan: riwayat hanya yang dibuat sebelumnya (bukan dirinya).
    stored = client.get(f"/api/v1/quotations/{second['id']}/pricing-check", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["history"]["count"] == 1
    assert "fee_turun" in {f["kind"] for f in stored.json()["findings"]}
    first_check = client.get(
        f"/api/v1/quotations/{first.json()['id']}/pricing-check", headers=headers
    ).json()
    assert first_check["history"] is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5.000.000", Decimal("5000000")),
        ("Rp 5.000.000,50", Decimal("5000000.50")),
        ("10%", Decimal("10")),
        ("2,5", Decimal("2.5")),
        ("1.5", Decimal("1.5")),
        (7_500_000, Decimal("7500000")),
        ("lima", None),
        ("", None),
        (True, None),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected
