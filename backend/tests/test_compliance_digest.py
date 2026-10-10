"""Digest kepatuhan kontrak & BPJS mingguan (hrd/compliance_digest.py, AI #4)."""

from datetime import date, timedelta

import pytest
from app.core.bootstrap import ensure_default_tenant
from app.core.tenancy import get_tenant, set_tenant
from app.modules.hrd.compliance_digest import build_digest, send_weekly_digest, week_key

from tests.conftest import _auth_header
from tests.test_hrd import _placement_id

TODAY = date(2026, 10, 12)  # Senin, minggu ISO 2026-W42


def _employee(client, headers, *, bpjs_kes=None, bpjs_tk=None):
    resp = client.post(
        "/api/v1/employees/onboard",
        headers=headers,
        json={"placement_id": _placement_id(client, headers)},
    )
    assert resp.status_code == 201, resp.text
    emp = resp.json()
    patch = {}
    if bpjs_kes:
        patch["bpjs_kesehatan_no"] = bpjs_kes
    if bpjs_tk:
        patch["bpjs_ketenagakerjaan_no"] = bpjs_tk
    if patch:
        assert client.patch(
            f"/api/v1/employees/{emp['id']}", headers=headers, json=patch
        ).is_success
    return emp


def _contract(client, headers, emp_id, end: date, previous=None):
    body = {"start_date": (end - timedelta(days=365)).isoformat(), "end_date": end.isoformat()}
    if previous:
        body["previous_contract_id"] = previous
    resp = client.post(f"/api/v1/employees/{emp_id}/contracts", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


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


def test_digest_lists_ending_lapsed_and_bpjs_gaps(client, tenant_db):
    h = _auth_header(client)
    ending = _employee(client, h, bpjs_kes="0001", bpjs_tk="0002")
    _contract(client, h, ending["id"], TODAY + timedelta(days=5))

    lapsed = _employee(client, h, bpjs_kes="0003", bpjs_tk="0004")
    _contract(client, h, lapsed["id"], TODAY - timedelta(days=10))

    renewed = _employee(client, h, bpjs_kes="0005", bpjs_tk="0006")
    old = _contract(client, h, renewed["id"], TODAY - timedelta(days=40))
    _contract(client, h, renewed["id"], TODAY + timedelta(days=300), previous=old)

    no_bpjs = _employee(client, h, bpjs_kes="0007")  # Ketenagakerjaan kosong

    digest = build_digest(tenant_db, TODAY)
    assert digest["week"] == "2026-W42"
    assert [c["employee_id"] for c in digest["contracts_ending"]] == [ending["id"]]
    assert digest["contracts_ending"][0]["action"].startswith("Segera putuskan")
    # Kontrak lama yang sudah diperpanjang TIDAK dianggap lewat.
    assert [c["employee_id"] for c in digest["contracts_lapsed"]] == [lapsed["id"]]
    assert digest["contracts_lapsed"][0]["days_overdue"] == 10
    gaps = {b["employee_id"]: b["missing"] for b in digest["bpjs_missing"]}
    assert gaps == {no_bpjs["id"]: ["Ketenagakerjaan"]}


def test_weekly_digest_sent_once_per_week_to_admin_and_hr(client, tenant_db):
    h = _auth_header(client)
    _employee(client, h)  # tanpa BPJS -> ada temuan
    assert send_weekly_digest(tenant_db, TODAY) == 1  # admin seeding
    assert send_weekly_digest(tenant_db, TODAY + timedelta(days=3)) == 0  # minggu sama
    assert send_weekly_digest(tenant_db, TODAY + timedelta(days=7)) == 1  # minggu baru

    items = client.get("/api/v1/me/notifications", headers=h).json()
    digests = [n for n in items if (n["entity_type"] or "").startswith("compliance_digest:")]
    assert {n["entity_type"] for n in digests} == {
        "compliance_digest:2026-W42",
        "compliance_digest:2026-W43",
    }
    assert "belum lengkap BPJS" in digests[0]["title"]


def test_badge_safety_net_creates_this_weeks_digest_without_cron(client):
    h = _auth_header(client)
    client.get("/api/v1/me/notifications/unread-count", headers=h)
    client.get("/api/v1/me/notifications/unread-count", headers=h)  # idempoten
    items = client.get("/api/v1/me/notifications", headers=h).json()
    markers = [n["entity_type"] for n in items if n["category"] == "compliance"]
    assert markers == [f"compliance_digest:{week_key(date.today())}"]


def test_internal_endpoint_requires_platform_admin(client):
    resp = client.post("/api/v1/platform/internal/run-weekly-digest", headers=_auth_header(client))
    assert resp.status_code == 403


def test_compliance_digest_endpoint(client):
    h = _auth_header(client)
    resp = client.get("/api/v1/employees/compliance-digest", headers=h)
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["counts"]) == {"contracts_ending", "contracts_lapsed", "bpjs_missing"}


def test_cron_endpoint_runs_for_active_tenants_once(client):
    from tests.conftest import _platform_admin_header

    _auth_header(client)  # tenant default + admin
    platform = _platform_admin_header(client)
    first = client.post("/api/v1/platform/internal/run-weekly-digest", headers=platform)
    assert first.status_code == 200, first.text
    assert first.json()["tenants_sent"] == 1
    again = client.post("/api/v1/platform/internal/run-weekly-digest", headers=platform)
    assert again.json()["tenants_sent"] == 0  # idempoten per minggu
