"""Cache audience realtime + loader DB bersesi pendek.

Handler WS TIDAK menahan sesi DB sepanjang koneksi (satu koneksi pool per
user online akan menghabiskan pool). Setiap resolusi membuka `SessionLocal()`
di threadpool, di dalam `tenant_context(tenant)` (middleware tenancy hanya
menangani HTTP — tanpa ini filter tenant ORM tidak aktif di jalur WS), lalu
langsung ditutup. Hasilnya di-cache dengan TTL + invalidasi eksplisit.

TTL default: scope direktori 60 dtk, audience channel 30 dtk, izin typing
30 dtk. Dengan >1 node, invalidasi hanya lokal; staleness dibatasi TTL.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.modules.chat.scope import DirectoryScope

SCOPE_TTL_SECONDS = 60.0
CHANNEL_TTL_SECONDS = 30.0
PERMISSION_TTL_SECONDS = 30.0

_EMPTY_SCOPE = DirectoryScope(all_tenant=False)


def _with_session[T](tenant_id: str, fn: Callable[[Session], T]) -> T:
    """Jalankan `fn(db)` dengan sesi pendek ber-konteks tenant (dipanggil di thread)."""
    from app.core import database
    from app.core.tenancy import tenant_context

    with tenant_context(UUID(tenant_id)):
        db = database.SessionLocal()
        try:
            return fn(db)
        finally:
            db.close()


def _parse(value: str | None) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _load_user(db: Session, tenant_id: str, user_id: str):
    from app.modules.auth.models import User

    user = db.get(User, _parse(user_id))
    if user is None or str(user.tenant_id) != tenant_id or not user.is_active:
        return None
    return user


def load_directory_scope(tenant_id: str, user_id: str) -> DirectoryScope:
    from app.modules.chat.scope import resolve_directory_scope

    def run(db: Session) -> DirectoryScope:
        user = _load_user(db, tenant_id, user_id)
        return _EMPTY_SCOPE if user is None else resolve_directory_scope(db, user)

    return _with_session(tenant_id, run)


def load_channel_audience(tenant_id: str, channel_id: str) -> frozenset[str] | None:
    from app.modules.chat.models import Channel
    from app.modules.chat.service import _channel_audience_ids

    def run(db: Session) -> frozenset[str] | None:
        channel = db.get(Channel, _parse(channel_id))
        if channel is None or str(channel.tenant_id) != tenant_id:
            return None
        return frozenset(_channel_audience_ids(db, channel))

    return _with_session(tenant_id, run)


def load_can_type(tenant_id: str, user_id: str, channel_id: str, parent_id: str | None) -> bool:
    """Boleh mengetik = boleh memposting (aturan REST `_assert_can_post`)."""
    from fastapi import HTTPException

    from app.modules.chat.models import Channel, ChatMessage
    from app.modules.chat.service import _assert_can_post

    def run(db: Session) -> bool:
        user = _load_user(db, tenant_id, user_id)
        channel = db.get(Channel, _parse(channel_id))
        if user is None or channel is None or str(channel.tenant_id) != tenant_id:
            return False
        try:
            _assert_can_post(db, user, channel)
        except HTTPException:
            return False
        if parent_id is not None:
            parent = db.get(ChatMessage, _parse(parent_id))
            if parent is None or parent.channel_id != channel.id:
                return False
        return True

    return _with_session(tenant_id, run)


def load_session_valid(tenant_id: str, user_id: str, token_payload: dict) -> bool:
    """Revalidasi berkala koneksi WS: user aktif, versi token cocok, belum exp."""
    from app.core.security import token_version_matches

    exp = token_payload.get("exp")
    if isinstance(exp, int | float) and exp <= time.time():
        return False

    def run(db: Session) -> bool:
        user = _load_user(db, tenant_id, user_id)
        return user is not None and token_version_matches(token_payload, user)

    return _with_session(tenant_id, run)


class AudienceCache:
    def __init__(
        self,
        clock: Callable[[], float],
        *,
        scope_ttl: float = SCOPE_TTL_SECONDS,
        channel_ttl: float = CHANNEL_TTL_SECONDS,
        permission_ttl: float = PERMISSION_TTL_SECONDS,
    ) -> None:
        self._clock = clock
        self.scope_ttl = scope_ttl
        self.channel_ttl = channel_ttl
        self.permission_ttl = permission_ttl
        self._scope: dict[tuple[str, str], tuple[float, DirectoryScope]] = {}
        self._channel: dict[tuple[str, str], tuple[float, frozenset[str] | None]] = {}
        self._perm: dict[tuple[str, str, str, str | None], tuple[float, bool]] = {}

    async def directory_scope(self, tenant_id: str, user_id: str) -> DirectoryScope:
        key = (tenant_id, user_id)
        hit = self._scope.get(key)
        now = self._clock()
        if hit is not None and hit[0] > now:
            return hit[1]
        scope = await run_in_threadpool(load_directory_scope, tenant_id, user_id)
        self._scope[key] = (now + self.scope_ttl, scope)
        return scope

    async def channel_audience(self, tenant_id: str, channel_id: str) -> frozenset[str] | None:
        key = (tenant_id, channel_id)
        hit = self._channel.get(key)
        now = self._clock()
        if hit is not None and hit[0] > now:
            return hit[1]
        audience = await run_in_threadpool(load_channel_audience, tenant_id, channel_id)
        self._channel[key] = (now + self.channel_ttl, audience)
        return audience

    async def can_type(
        self, tenant_id: str, user_id: str, channel_id: str, parent_id: str | None
    ) -> bool:
        key = (tenant_id, user_id, channel_id, parent_id)
        hit = self._perm.get(key)
        now = self._clock()
        if hit is not None and hit[0] > now:
            return hit[1]
        allowed = await run_in_threadpool(load_can_type, tenant_id, user_id, channel_id, parent_id)
        self._perm[key] = (now + self.permission_ttl, allowed)
        return allowed

    def invalidate_channel(self, tenant_id: str, channel_id: str) -> None:
        """Keanggotaan channel berubah (create/add_member/channel proyek)."""
        self._channel.pop((tenant_id, channel_id), None)
        for key in [k for k in self._perm if k[0] == tenant_id and k[2] == channel_id]:
            self._perm.pop(key, None)

    def invalidate_tenant(self, tenant_id: str) -> None:
        """Scope direktori tenant mungkin berubah (placement/role/user nonaktif)."""
        for scope_key in [k for k in self._scope if k[0] == tenant_id]:
            self._scope.pop(scope_key, None)
        for ch_key in [k for k in self._channel if k[0] == tenant_id]:
            self._channel.pop(ch_key, None)
        for perm_key in [k for k in self._perm if k[0] == tenant_id]:
            self._perm.pop(perm_key, None)
