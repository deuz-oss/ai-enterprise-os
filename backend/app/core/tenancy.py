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
# Identitas pemanggil & asal request untuk kebutuhan audit (diisi middleware
# dari klaim JWT + header, tanpa DB).
_current_user: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)
_current_ip: ContextVar[str | None] = ContextVar("current_request_ip", default=None)
_current_agent: ContextVar[str | None] = ContextVar("current_request_ua", default=None)


def set_tenant(tenant_id: UUID | None) -> None:
    _current_tenant.set(tenant_id)


def get_tenant() -> UUID | None:
    return _current_tenant.get()


def set_requester(
    *, user_id: UUID | None = None, ip: str | None = None, user_agent: str | None = None
) -> None:
    if user_id is not None:
        _current_user.set(user_id)
    if ip is not None:
        _current_ip.set(ip)
    if user_agent is not None:
        _current_agent.set(user_agent[:300])


def get_requester_user() -> UUID | None:
    return _current_user.get()


def get_request_meta() -> tuple[str | None, str | None]:
    return _current_ip.get(), _current_agent.get()


class TenantMixin:
    """Mixin untuk model bisnis milik satu tenant.

    Catatan: subclass boleh meng-override `tenant_id` menjadi nullable
    (mis. tabel audit untuk event pra-login) — tetap tercakup filter otomatis
    karena kriteria loader menargetkan mixin ini.
    """

    @declared_attr
    @classmethod
    def tenant_id(cls) -> Mapped[UUID]:
        return mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)


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

    # PostgreSQL RLS lapis kedua: set app.current_tenant sebelum TIAP
    # statement (bukan cuma sekali per transaksi -- lihat catatan kejujuran
    # di bawah kenapa itu tidak cukup), di level Core (`before_cursor_execute`)
    # supaya berlaku untuk ORM select/insert/update/delete DAN raw SQL sama
    # rata. Engine-level (bukan Session-level) karena butuh akses cursor
    # mentah langsung -- lihat komentar performa di bawah.
    #
    # CATATAN KEJUJURAN (ditemukan lewat bug produksi nyata, bukan teori):
    # versi awal fungsi ini pakai `after_transaction_create` (sekali per
    # transaksi). Itu SALAH untuk pola yang sudah lama dipakai di codebase
    # ini: banyak fungsi query sesuatu dulu (mis. cari Tenant by slug) BARU
    # panggil `set_tenant()` setelah baris ditemukan, semua dalam transaksi
    # yang SAMA (tanpa commit di antaranya). `after_transaction_create` sudah
    # kadung fire di query pertama (tenant masih None/lama saat itu) --
    # statement BERIKUTNYA di transaksi yang sama tidak pernah dapat
    # kesempatan menyetel ulang config, walau `set_tenant()` sudah dipanggil
    # dengan benar sebelum statement itu. Konkret: `platform/service.py::
    # get_or_create_default_tenant()` query Tenant dulu, baru `ensure_coa()`
    # (yang panggil `set_tenant()`) menulis Account -- INSERT itu gagal
    # "new row violates row-level security policy" begitu RLS+FORCE
    # sungguhan aktif, karena config sudah telanjur ke-lock ke transaksi
    # sebelum tenant diketahui. Ditemukan saat backend gagal start sama
    # sekali sesudah RLS diperluas (lihat migrasi g8h9i0j1k2l3).
    from app.core.database import engine as _engine

    @event.listens_for(_engine, "before_cursor_execute")
    def _sync_pg_rls_tenant(conn, cursor, statement, parameters, context, executemany):
        if conn.dialect.name != "postgresql":
            return
        tid = get_tenant()
        current = str(tid) if tid else ""
        # SENGAJA TANPA cache/skip -- versi awal fungsi ini pakai
        # `conn.info` untuk skip SET kalau tenant "belum berubah sejak
        # statement sebelumnya di koneksi yang sama". Itu SALAH dan
        # ketahuan lewat bug produksi nyata: `GET /job-orders` FLAKY
        # (kadang 200 dgn 21 baris, kadang 200 dgn array kosong) --
        # `conn.info` (Python-side, di proses ini) dan session-level
        # `app.current_tenant` di Postgres (server-side, per physical
        # connection) TERNYATA tidak selalu sinkron satu sama lain begitu
        # connection pool + `--workers 2` terlibat; asumsi "aman di-cache"
        # tidak terbukti benar. Set TANPA SYARAT di sini -- satu extra
        # `SET` per statement, tapi tenant isolation adalah properti
        # keamanan yang TIDAK BOLEH bergantung pada optimisasi yang
        # asumsinya sendiri belum benar-benar diverifikasi.
        cursor.execute("SELECT set_config('app.current_tenant', %s, false)", (current,))

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

            headers = Headers(scope=scope)
            auth = headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                from app.core.security import decode_token_payload

                payload = decode_token_payload(auth[len("Bearer ") :]) or {}
                set_tenant(tenant_from_token(auth[len("Bearer ") :]))
                sub = payload.get("sub")
                try:
                    requester = UUID(str(sub)) if sub else None
                except ValueError:
                    requester = None
            else:
                set_tenant(None)
                requester = None
            client_host = (scope.get("client") or (None, None))[0]
            set_requester(
                user_id=requester,
                ip=client_host,
                user_agent=headers.get("user-agent"),
            )
        try:
            await self.app(scope, receive, send)
        finally:
            set_tenant(None)


install_tenancy_listeners()
