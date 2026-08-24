"""Fondasi multi-tenant: shared schema dengan kolom tenant_id.

Mekanisme:
- `TenantMixin` ditambahkan ke semua model bisnis (kolom tenant_id NOT NULL).
- ContextVar `current_tenant_id` diisi per request oleh `get_current_user`
  berdasarkan akun yang login.
- Event `do_orm_execute` menyuntikkan filter tenant otomatis ke SEMUA select
  ORM — service tidak perlu (dan tidak boleh) memfilter manual.
- Event `before_flush` mengisi tenant_id pada objek baru dari konteks.

Objek tanpa kolom tenant_id (mis. tabel tenants itu sendiri) tidak
terdampak. Operasi sistem tanpa konteks tenant (bootstrap/provisioning)
tetap bisa menulis dengan menyetel tenant_id secara eksplisit.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, event
from sqlalchemy.orm import (
    Mapped,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)
from sqlalchemy.orm.session import ORMExecuteState

_current_tenant: ContextVar[UUID | None] = ContextVar("current_tenant_id", default=None)


def set_tenant(tenant_id: UUID | None) -> None:
    _current_tenant.set(tenant_id)


def get_tenant() -> UUID | None:
    return _current_tenant.get()


class TenantMixin:
    """Mixin untuk model bisnis milik satu tenant."""

    @declared_attr
    @classmethod
    def tenant_id(cls) -> Mapped[UUID]:
        return mapped_column(
            ForeignKey("tenants.id"), nullable=False, index=True
        )


def tenant_from_token(token: str) -> UUID | None:
    """Ambil klaim tid dari JWT tanpa DB (dipakai middleware konteks).

    Konteks disetel di middleware (bukan dependency sync) karena FastAPI
    menjalankan dependency/endpoint sync di threadpool terpisah — ContextVar
    yang diubah di sana tidak terbawa ke endpoint. Middleware berjalan di
    event loop sebelum task downstream dibuat, sehingga nilai terwarisi.
    """
    from app.core.security import decode_token_payload

    payload = decode_token_payload(token)
    if not payload:
        return None
    raw = payload.get("tid")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


def install_tenancy_listeners() -> None:
    """Pasang listener sekali untuk semua Session (termasuk session test)."""
    """Pasang listener sekali untuk semua Session (termasuk session test)."""

    @event.listens_for(Session, "do_orm_execute")
    def _add_tenant_filter(execute_state: ORMExecuteState) -> None:
        tenant_id = get_tenant()
        if tenant_id is None or not execute_state.is_select:
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantMixin,
                lambda cls: cls.tenant_id == tenant_id,
                include_aliases=True,
            )
        )

    @event.listens_for(Session, "before_flush")
    def _inject_tenant(
        session: Session, flush_context: Any, instances: Sequence[Any] | None
    ) -> None:
        del flush_context, instances
        tenant_id = get_tenant()
        if tenant_id is None:
            return
        for obj in session.new:
            table = getattr(type(obj), "__table__", None)
            if table is not None and "tenant_id" in table.columns:
                if getattr(obj, "tenant_id", None) is None:
                    obj.tenant_id = tenant_id


class TenantContextMiddleware:
    """ASGI middleware: setel konteks tenant dari klaim `tid` JWT.

    Sengaja pure-ASGI (bukan BaseHTTPMiddleware) agar berjalan di event loop
    dan task downstream mewarisi ContextVar ini. Reset di finally agar thread
    pool tidak membawa sisa konteks request sebelumnya.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            from starlette.datastructures import Headers

            auth = Headers(scope=scope).get("Authorization", "")
            if auth.startswith("Bearer "):
                set_tenant(tenant_from_token(auth[len("Bearer ") :]))
            else:
                set_tenant(None)
        try:
            await self.app(scope, receive, send)
        finally:
            set_tenant(None)


install_tenancy_listeners()
