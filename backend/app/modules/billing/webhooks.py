"""Dispatcher webhook gateway pembayaran (Fase 28 lanjutan, rencana §7).

Urutan: verifikasi token (di router) -> normalisasi adapter -> simpan event
(`payment_webhook_events`, dedup unik per `(provider, dedup_key)`) ->
resolusi tenant dari `reference_id` buatan Aeos (`aeos-{jenis}-{tenant}-...`)
-> efek bisnis + status event `processed` dalam SATU transaksi. Gagal ->
rollback efek, event `failed`, respons 5xx agar gateway mengirim ulang
(event `failed` boleh diproses ulang; `processed`/`ignored` = duplikat).

Status bisnis bersifat monoton (compare-and-set): event lama/terlambat tidak
pernah menimpa status terminal (`paid`, `succeeded`, `removed`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.payment.base import WebhookEvent
from app.core.tenancy import tenant_context
from app.modules.billing.models import (
    ChargeStatus,
    PaymentCharge,
    PaymentWebhookEvent,
    WebhookEventStatus,
)
from app.modules.billing.service import audit_add

logger = logging.getLogger(__name__)

_REFERENCE_RE = re.compile(
    r"^aeos-[a-z]+-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-"
)
# Field yang tidak boleh tersimpan walau suatu saat muncul di payload.
_SENSITIVE_KEYS = {"card_number", "cvv", "cvn", "cvc", "account_number", "card_cvn"}


def tenant_from_reference(reference_id: str | None) -> UUID | None:
    if not reference_id:
        return None
    match = _REFERENCE_RE.match(reference_id)
    if not match:
        return None
    try:
        return UUID(match.group(1))
    except ValueError:
        return None


def _scrub(value: object) -> object:
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _SENSITIVE_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _store_event(
    db: Session, provider: str, event: WebhookEvent, payload: dict
) -> tuple[PaymentWebhookEvent, bool]:
    """(baris event, perlu_diproses). Duplikat processed/ignored -> False."""
    raw = json.dumps(_scrub(payload), ensure_ascii=False, sort_keys=True, default=str)
    row = PaymentWebhookEvent(
        provider=provider,
        dedup_key=event.dedup_key,
        event_type=event.event_type,
        object_id=event.object_id,
        payload_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        payload_json=raw,
        status=WebhookEventStatus.received,
    )
    db.add(row)
    try:
        db.commit()
        return row, True
    except IntegrityError:
        db.rollback()
    existing = db.execute(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == provider,
            PaymentWebhookEvent.dedup_key == event.dedup_key,
        )
    ).scalar_one()
    return existing, existing.status == WebhookEventStatus.failed


def handle_webhook(db: Session, headers: dict[str, str], payload: dict) -> dict:
    """Proses satu callback gateway yang SUDAH lolos verifikasi token."""
    from app.modules.billing.payment_service import get_adapter

    adapter = get_adapter()
    event = adapter.parse_webhook(headers, payload)
    row, should_process = _store_event(db, adapter.provider_name, event, payload)
    if not should_process:
        return {"status": "duplicate", "event_id": str(row.id)}
    row_id = row.id
    try:
        outcome = _dispatch(db, row_id, event)
    except Exception as exc:
        db.rollback()
        failed = db.get(PaymentWebhookEvent, row_id)
        if failed is not None:
            failed.status = WebhookEventStatus.failed
            failed.error = f"{type(exc).__name__}: {exc}"[:300]
            audit_add(
                db,
                action="billing.webhook_failed",
                entity_type="payment_webhook_event",
                entity_id=row_id,
                detail={"event_type": event.event_type, "error": type(exc).__name__},
                tenant_id=failed.tenant_id,
            )
            db.commit()
        logger.exception("Webhook %s gagal diproses", event.event_type)
        raise HTTPException(status_code=500, detail="Webhook gagal diproses") from exc
    return {"status": outcome, "event_id": str(row_id)}


def _finish(db: Session, row_id: UUID, status: WebhookEventStatus, tenant_id: UUID | None) -> None:
    row = db.get(PaymentWebhookEvent, row_id)
    assert row is not None
    row.status = status
    row.tenant_id = tenant_id
    row.processed_at = datetime.now(UTC)
    row.error = None


def _dispatch(db: Session, row_id: UUID, event: WebhookEvent) -> str:
    from app.modules.billing import payment_service

    if event.event_type in ("invoice.paid", "invoice.expired"):
        intent = payment_service.find_intent(db, event.object_id or "")
        if intent is None:
            _finish(db, row_id, WebhookEventStatus.ignored, None)
            db.commit()
            return "ignored"
        tenant_id = intent.tenant_id
        was_pending = intent.status.value == "pending"
        with tenant_context(tenant_id):
            if event.event_type == "invoice.paid":
                payment_service.reconcile_payment(
                    db,
                    event.object_id or "",
                    payment_channel_label=_invoice_label(event.payment_channel_label),
                    commit=False,
                )
                changed = was_pending
            else:
                # EXPIRED setelah PAID: status terminal tidak ditimpa.
                changed = payment_service.expire_intent(db, event.object_id or "")
            status = WebhookEventStatus.processed if changed else WebhookEventStatus.ignored
            _finish(db, row_id, status, tenant_id)
            db.commit()
        return "ok" if changed else "ignored"

    ref_tenant = tenant_from_reference(event.reference_id)
    if ref_tenant is None:
        _finish(db, row_id, WebhookEventStatus.ignored, None)
        db.commit()
        return "ignored"

    with tenant_context(ref_tenant):
        if event.event_type.startswith("payment_method."):
            return _dispatch_payment_method(db, row_id, event, ref_tenant)
        if event.event_type.startswith("payment."):
            return _dispatch_charge(db, row_id, event, ref_tenant)
        _finish(db, row_id, WebhookEventStatus.ignored, ref_tenant)
        db.commit()
        return "ignored"


def _invoice_label(channel: str | None) -> str:
    return f"Invoice Xendit ({channel})" if channel else "Invoice Xendit"


def _dispatch_payment_method(
    db: Session, row_id: UUID, event: WebhookEvent, tenant_id: UUID
) -> str:
    from app.modules.billing import payment_methods

    pm = payment_methods.find_by_reference(db, event.reference_id or "")
    if pm is None or pm.tenant_id != tenant_id:
        _finish(db, row_id, WebhookEventStatus.ignored, tenant_id)
        db.commit()
        return "ignored"
    changed = payment_methods.apply_payment_method_event(
        db,
        pm,
        status=event.status,
        display=event.display,
        failure_reason=event.failure_code,
    )
    _finish(
        db,
        row_id,
        WebhookEventStatus.processed if changed else WebhookEventStatus.ignored,
        tenant_id,
    )
    db.commit()
    return "ok" if changed else "ignored"


def _dispatch_charge(db: Session, row_id: UUID, event: WebhookEvent, tenant_id: UUID) -> str:
    from app.modules.billing import charges

    charge = db.execute(
        select(PaymentCharge).where(PaymentCharge.idempotency_key == (event.reference_id or ""))
    ).scalar_one_or_none()
    if charge is None or charge.tenant_id != tenant_id:
        _finish(db, row_id, WebhookEventStatus.ignored, tenant_id)
        db.commit()
        return "ignored"
    # Event dicatat processed SEBELUM efek -- efek (charges.*) commit di
    # transaksi yang sama, sehingga status event & efek tersimpan bersama.
    _finish(db, row_id, WebhookEventStatus.processed, tenant_id)
    if event.event_type == "payment.succeeded":
        applied = charges.apply_charge_success(db, charge, provider_charge_id=event.object_id)
    elif event.event_type == "payment.failed":
        if charge.status == ChargeStatus.succeeded:
            logger.warning("payment.failed setelah succeeded untuk charge %s diabaikan", charge.id)
            applied = False
        else:
            applied = charges.apply_charge_failure(
                db,
                charge,
                code=event.failure_code or "FAILED",
                message=None,
                provider_charge_id=event.object_id,
            )
    else:
        applied = False
    if not applied:
        # CAS kalah (sudah diterapkan) / event non-terminal: tandai ignored.
        _finish(db, row_id, WebhookEventStatus.ignored, tenant_id)
    db.commit()
    return "ok" if applied else "ignored"
