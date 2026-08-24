"""Pencatatan & pembacaan jejak audit.

`log_event` aman dipanggil dari mana saja: identitas user, IP, dan
user-agent diambil dari konteks request (middleware), tenant dari
konteks yang sama. Kegagalan pencatatan TIDAK boleh menggagalkan operasi
bisnis — hanya dicatat ke logger.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.tenancy import get_request_meta, get_requester_user
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditLogOut

logger = logging.getLogger(__name__)


def log_event(
    db: Session,
    *,
    action: str,
    entity_type: str | None = None,
    entity_id: UUID | str | None = None,
    object_key: str | None = None,
    detail: dict | list | None = None,
    actor: UUID | None = None,
    tenant_id: UUID | None = None,
) -> None:
    """Catat event audit.

    `actor`/`tenant_id` opsional untuk event yang berjalan di luar konteks
    request (mis. login sukses — konteks tenant belum terpasang).
    """
    try:
        ip, agent = get_request_meta()
        resolved_actor = actor if actor is not None else get_requester_user()
        db.add(
            AuditLog(
                action=action,
                tenant_id=tenant_id,
                user_id=resolved_actor,
                entity_type=entity_type,
                entity_id=(
                    entity_id if isinstance(entity_id, UUID) else UUID(str(entity_id))
                )
                if entity_id
                else None,
                object_key=object_key[:500] if object_key else None,
                ip=ip,
                user_agent=agent,
                detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
            )
        )
        # commit disengaja di sini: log harus tersimpan walau caller belum commit.
        db.commit()
    except Exception:  # noqa: BLE001 - audit tidak boleh mematahkan bisnis
        logger.exception("Gagal mencatat audit event action=%s", action)
        db.rollback()


def query_logs(
    db: Session,
    *,
    action_prefix: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    user_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    count_stmt = select(func.count(AuditLog.id))
    if action_prefix:
        cond = AuditLog.action.startswith(action_prefix)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
        count_stmt = count_stmt.where(AuditLog.entity_id == entity_id)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)

    total = db.scalar(count_stmt) or 0
    rows = list(db.scalars(stmt.limit(min(limit, 500)).offset(max(offset, 0))).all())
    return rows, int(total)


def to_out(row: AuditLog) -> AuditLogOut:
    detail = None
    if row.detail_json:
        try:
            detail = json.loads(row.detail_json)
        except json.JSONDecodeError:
            detail = {"raw": row.detail_json}
    return AuditLogOut(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        object_key=row.object_key,
        ip=row.ip,
        created_at=row.created_at,
        detail=detail,
    )
