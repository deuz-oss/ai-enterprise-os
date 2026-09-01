"""AI Usage Metering — instrumentasi sentral di core/llm.py (core/ai_usage.py).

Mock httpx.post di level core.llm (bukan mock chat_completion/embed_texts
langsung) supaya _post_chat/embed_texts ASLI yang jalan — instrumentasi
teruji end-to-end, bukan cuma diasumsikan terpanggil.
"""

from __future__ import annotations

import httpx
import pytest
from app.core.ai_usage import AIUsageEvent
from app.core.bootstrap import ensure_default_tenant
from app.core.config import get_settings
from app.core.tenancy import set_tenant
from sqlalchemy import select

from tests.conftest import _auth_header

_URL = "http://fake-ai.test/v1"


@pytest.fixture(autouse=True)
def _reset_tenant_context():
    """Test ini memanggil chat_completion/embed_texts LANGSUNG (bukan lewat
    endpoint HTTP), jadi `set_tenant()` dipanggil manual tanpa middleware yang
    biasanya me-reset di `finally`. Reset di sini supaya tidak bocor ke test
    lain yang berjalan setelahnya di proses yang sama."""
    yield
    set_tenant(None)


@pytest.fixture()
def ai_settings(monkeypatch):
    """Aktifkan `ai_configured` tanpa menyentuh .env — settings itu singleton
    (lru_cache), jadi monkeypatch atribut langsung di objeknya."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_base_url", _URL)
    monkeypatch.setattr(settings, "ai_model", "test-chat-model")
    monkeypatch.setattr(settings, "ai_embedding_model", "test-embed-model")
    return settings


def _tenant_context(client):
    """Login (bikin tenant default via seed) lalu aktifkan konteksnya di
    contextvar proses ini — chat_completion/embed_texts dipanggil LANGSUNG
    (bukan lewat endpoint HTTP), jadi konteks tenant per-request middleware
    tidak berlaku; disetel manual di sini."""
    _auth_header(client)
    db = client.testing_session()
    try:
        tenant = ensure_default_tenant(db)
    finally:
        db.close()
    set_tenant(tenant.id)
    return tenant.id


def _usage_rows(client) -> list[AIUsageEvent]:
    db = client.testing_session()
    try:
        return list(db.execute(select(AIUsageEvent)).scalars())
    finally:
        db.close()


def _fake_chat_response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", _URL + "/chat/completions"),
    )


def _fake_embed_response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", _URL + "/embeddings"),
    )


def test_chat_completion_success_records_usage(client, ai_settings, monkeypatch):
    import app.core.llm as llm_module

    tenant_id = _tenant_context(client)
    monkeypatch.setattr(
        llm_module.httpx,
        "post",
        lambda *a, **kw: _fake_chat_response(
            200,
            {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            },
        ),
    )

    result = llm_module.chat_completion("system", "user", feature="test.chat_feature")
    assert result == {"ok": True}

    rows = _usage_rows(client)
    assert len(rows) == 1
    row = rows[0]
    assert row.tenant_id == tenant_id
    assert row.call_type == "chat"
    assert row.feature == "test.chat_feature"
    assert row.status == "success"
    assert row.model == "test-chat-model"
    assert row.prompt_tokens == 12
    assert row.completion_tokens == 3
    assert row.total_tokens == 15


def test_embedding_success_records_usage_with_embedding_call_type(client, ai_settings, monkeypatch):
    import app.core.llm as llm_module

    _tenant_context(client)
    monkeypatch.setattr(
        llm_module.httpx,
        "post",
        lambda *a, **kw: _fake_embed_response(
            200,
            {
                "data": [{"index": 0, "embedding": [0.1, 0.2]}],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        ),
    )

    vectors = llm_module.embed_texts(["halo"], feature="test.embed_feature")
    assert vectors == [[0.1, 0.2]]

    rows = _usage_rows(client)
    assert len(rows) == 1
    assert rows[0].call_type == "embedding"
    assert rows[0].feature == "test.embed_feature"
    assert rows[0].status == "success"
    assert rows[0].model == "test-embed-model"
    assert rows[0].total_tokens == 5


def test_provider_http_error_records_error_status_and_still_raises(
    client, ai_settings, monkeypatch
):
    import app.core.llm as llm_module
    from fastapi import HTTPException

    _tenant_context(client)
    monkeypatch.setattr(
        llm_module.httpx,
        "post",
        lambda *a, **kw: _fake_chat_response(502, {"error": "provider down"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        llm_module.chat_completion("system", "user", feature="test.chat_feature")
    assert exc_info.value.status_code == 502

    rows = _usage_rows(client)
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "error"
    assert row.http_status == 502
    assert row.prompt_tokens is None
    assert row.total_tokens is None


def test_timeout_records_error_without_http_status(client, ai_settings, monkeypatch):
    import app.core.llm as llm_module
    from fastapi import HTTPException

    _tenant_context(client)

    def _raise_timeout(*a, **kw):
        raise httpx.ConnectTimeout("timeout mencapai provider")

    monkeypatch.setattr(llm_module.httpx, "post", _raise_timeout)

    with pytest.raises(HTTPException) as exc_info:
        llm_module.chat_completion("system", "user", feature="test.chat_feature")
    assert exc_info.value.status_code == 502

    rows = _usage_rows(client)
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].http_status is None


def test_no_tenant_context_records_nothing_and_does_not_raise(client, ai_settings, monkeypatch):
    import app.core.llm as llm_module

    set_tenant(None)  # tanpa konteks tenant (mis. panggilan sistem/bootstrap)
    monkeypatch.setattr(
        llm_module.httpx,
        "post",
        lambda *a, **kw: _fake_chat_response(
            200,
            {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        ),
    )

    result = llm_module.chat_completion("system", "user", feature="test.chat_feature")
    assert result == {"ok": True}
    assert _usage_rows(client) == []


def test_record_usage_write_failure_does_not_break_chat_completion(
    client, ai_settings, monkeypatch
):
    import app.core.ai_usage as ai_usage_module
    import app.core.llm as llm_module

    _tenant_context(client)
    monkeypatch.setattr(
        llm_module.httpx,
        "post",
        lambda *a, **kw: _fake_chat_response(
            200,
            {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        ),
    )

    class _BrokenSession:
        def add(self, *a, **kw):
            pass

        def commit(self):
            raise RuntimeError("DB down")

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(ai_usage_module, "SessionLocal", lambda: _BrokenSession())

    result = llm_module.chat_completion("system", "user", feature="test.chat_feature")
    assert result == {"ok": True}
