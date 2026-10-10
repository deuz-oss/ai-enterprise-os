"""Kalimat bebas ⌘K -> daftar terfilter (ai/nav_query.py, peluang AI #5)."""

from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import app.core.llm as llm
import pytest

from tests.conftest import _auth_header, _login_header

URL = "/api/v1/ai/nav-query"


@pytest.fixture()
def llm_reply(monkeypatch):
    """AI aktif; balasan LLM diatur per test lewat state["reply"]."""
    state: dict = {"reply": {}}
    monkeypatch.setattr(llm, "ai_configured", lambda: True)
    monkeypatch.setattr(llm, "chat_completion", lambda *a, **k: state["reply"])
    return state


def _clients(client, headers, *names):
    return {
        n: client.post("/api/v1/clients", headers=headers, json={"name": n}).json()["id"]
        for n in names
    }


def _ask(client, headers, text="apa saja"):
    resp = client.post(URL, headers=headers, json={"text": text})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _params(path):
    return {k: v[0] for k, v in parse_qs(urlparse(path).query).items()}


def test_employees_client_and_contract_end(client, llm_reply):
    headers = _auth_header(client)
    ids = _clients(client, headers, "PT Maju Jaya", "PT Sinar Abadi")
    ends_by = date.today() + timedelta(days=40)
    llm_reply["reply"] = {
        "page": "employees",
        "status": "aktif",
        "client": "PT Maju",  # sebagian nama, unik -> cocok
        "contract_ends_by": ends_by.isoformat(),
    }
    out = _ask(client, headers, "karyawan PT Maju kontrak habis bulan depan")
    assert out["source"] == "ai" and out["page"] == "Karyawan"
    assert urlparse(out["path"]).path == "/employees"
    assert _params(out["path"]) == {
        "status": "aktif",
        "client": ids["PT Maju Jaya"],
        "contract_days": "40",
    }
    assert "Klien: PT Maju Jaya" in out["applied"]
    assert out["ignored"] == []


def test_whitelist_and_ambiguity_are_enforced(client, llm_reply):
    headers = _auth_header(client)
    _clients(client, headers, "PT Sinar Abadi", "PT Sinar Mas")
    llm_reply["reply"] = {
        "page": "job_orders",
        "status": "selesai",  # bukan status job order
        "client": "Sinar",  # dua klien cocok -> ambigu
        "overdue": True,  # hanya untuk invoice
        "contract_ends_by": "2026-12-31",  # hanya untuk karyawan
    }
    out = _ask(client, headers)
    assert out["path"] == "/job-orders"
    assert out["applied"] == []
    assert any("selesai" in i for i in out["ignored"])
    assert any("ambigu" in i for i in out["ignored"])


def test_invoices_overdue_and_status(client, llm_reply):
    headers = _auth_header(client)
    llm_reply["reply"] = {"page": "invoices", "status": "Terkirim", "overdue": True}
    out = _ask(client, headers, "invoice terkirim yang telat bayar")
    assert urlparse(out["path"]).path == "/finance"
    assert _params(out["path"]) == {"status": "terkirim", "overdue": "1"}


def test_unknown_page_or_contract_date_out_of_range(client, llm_reply):
    headers = _auth_header(client)
    llm_reply["reply"] = {"page": "payroll"}
    assert _ask(client, headers)["path"] is None
    llm_reply["reply"] = {"page": "employees", "contract_ends_by": "2020-01-01"}
    out = _ask(client, headers)
    assert out["path"] == "/employees"
    assert any("1-365" in i for i in out["ignored"])


def test_ai_off_returns_nothing(client):
    out = _ask(client, _auth_header(client), "karyawan aktif")
    assert out == {"page": None, "path": None, "applied": [], "ignored": [], "source": "none"}


def test_employee_role_cannot_use_palette_query(client, llm_reply):
    admin = _auth_header(client)
    resp = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={
            "email": "ess@example.com",
            "full_name": "Karyawan",
            "password": "password123",
            "role": "karyawan",
        },
    )
    assert resp.status_code == 201, resp.text
    ess = _login_header(client, "ess@example.com", "password123")
    assert client.post(URL, headers=ess, json={"text": "karyawan"}).status_code == 403
