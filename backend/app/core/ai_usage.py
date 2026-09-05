"""Pencatatan pemakaian AI (token+biaya) per tenant — dasar penagihan AI Add-on.

Dipanggil sentral dari `core/llm.py` (bukan di-inject manual ke tiap titik
panggil) supaya tidak ada yang lupa terinstrumen. `record_usage()` tidak
boleh pernah melempar exception (prinsip sama seperti `audit.log_event`) —
kegagalan pencatatan tidak boleh menggagalkan operasi bisnis AI yang sudah
terlanjur jalan.

Menulis lewat `SessionLocal()` ad-hoc (bukan `db` dari caller): banyak
titik panggil AI (mis. `recruitment/service.py::_llm_rerank_explain`,
`ai/collab.py::_narrate`) tidak punya `db: Session` dalam scope, dan
biaya vendor sudah dibebankan begitu response diterima terlepas dari
apakah transaksi DB caller akhirnya commit atau rollback — event usage
harus tetap tercatat independen. Pola `SessionLocal()` ad-hoc ini sudah
ada presedennya di `chat/router.py::chat_ws` (WebSocket, DI FastAPI tidak
berlaku).
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base, SessionLocal
from app.core.tenancy import TenantMixin, get_requester_user, get_tenant

logger = logging.getLogger(__name__)


class AIUsageEvent(TenantMixin, Base):
    __tablename__ = "ai_usage_events"
    __table_args__ = (
        Index("ix_ai_usage_tenant_created", "tenant_id", "created_at"),
        Index("ix_ai_usage_tenant_feature_created", "tenant_id", "feature", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    call_type: Mapped[str] = mapped_column(String(20))  # "chat" | "vision" | "embedding"
    feature: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20))  # "success" | "error"
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_idr: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Estimasi biaya vendor per 1k token (Rupiah): {model: (harga_prompt, harga_completion)}.
# Snapshot manual, BUKAN sumber kebenaran tagihan resmi — model tak terdaftar => cost_idr None.
_MODEL_PRICE_IDR_PER_1K: dict[str, tuple[float, float]] = {}

# Tarif TENANT AI Add-on (Fase 28, PRD §4.3) -- flat per 1k token total,
# terlepas dari model. SENGAJA terpisah dari _MODEL_PRICE_IDR_PER_1K di atas:
# yang itu estimasi biaya VENDOR (untuk margin, boleh kosong), ini yang
# benar-benar dipotong dari saldo tenant lewat credit_transactions.
_TENANT_RATE_IDR_PER_1K_TOKEN = 300.0


def _estimate_cost_idr(model: str, usage: dict | None) -> float | None:
    price = _MODEL_PRICE_IDR_PER_1K.get(model)
    if price is None or not usage:
        return None
    prompt_price, completion_price = price
    prompt_tokens = usage.get("prompt_tokens") or 0
    completion_tokens = usage.get("completion_tokens") or 0
    return (prompt_tokens / 1000) * prompt_price + (completion_tokens / 1000) * completion_price


def _tenant_charge_idr(usage: dict | None) -> float:
    total_tokens = (usage or {}).get("total_tokens") or 0
    return (total_tokens / 1000) * _TENANT_RATE_IDR_PER_1K_TOKEN


def record_usage(
    *,
    call_type: str,
    feature: str | None,
    model: str,
    usage: dict | None,
    status: str,
    http_status: int | None = None,
    error_detail: str | None = None,
) -> None:
    tenant_id = get_tenant()
    if tenant_id is None:
        return  # tidak ada konteks tenant (panggilan sistem/bootstrap) — lewati, bukan error
    db = SessionLocal()
    try:
        event = AIUsageEvent(
            tenant_id=tenant_id,
            user_id=get_requester_user(),
            call_type=call_type,
            feature=feature,
            model=model,
            status=status,
            prompt_tokens=(usage or {}).get("prompt_tokens"),
            completion_tokens=(usage or {}).get("completion_tokens"),
            total_tokens=(usage or {}).get("total_tokens"),
            cost_idr=_estimate_cost_idr(model, usage),
            http_status=http_status,
            error_detail=(error_detail or "")[:500] or None,
        )
        db.add(event)
        db.commit()
    except Exception:
        logger.exception("Gagal mencatat AI usage event")
        db.rollback()
        db.close()
        return

    # Debit ledger (Fase 28) -- sesi terpisah SENGAJA dipertahankan (lihat
    # docstring modul): banyak call site AI tidak punya `db` caller dalam
    # scope, dan biaya vendor sudah terlanjur dikeluarkan begitu response
    # diterima -- tidak ada "titik batal" untuk fail-closed di sini seperti
    # aksi metered lain (match/invoice/faktur). Karena itu pakai
    # `allow_negative=True`, bukan `charge_metered_event`: saldo boleh
    # minus, direkonsiliasi lewat pembayaran berikutnya, tapi panggilan AI
    # yang SUDAH terjadi tidak pernah ditolak pasca-fakta.
    if status == "success":
        try:
            charge = _tenant_charge_idr(usage)
            if charge > 0:
                from app.modules.billing.service import record_credit_transaction

                record_credit_transaction(
                    db,
                    amount=-charge,
                    ref_event="ai_usage",
                    ref_entity_type="ai_usage_event",
                    ref_entity_id=str(event.id),
                    allow_negative=True,
                )
                db.commit()
        except Exception:
            logger.exception("Gagal mencatat debit kredit AI usage")
            db.rollback()
    db.close()
