"""Kontrak realtime chat (PRD §9.4): presence, typing, dan event bus.

Semua state realtime bersifat ephemeral (tidak dipersisten). Implementasi
v1 in-memory (`memory.py`); scale-out multi-instance kelak cukup menyediakan
implementasi Redis untuk ketiga Protocol di bawah tanpa mengubah caller
(`RealtimeHub`, router WS, `service._notify_channel`).

Prinsip audience: event membawa SPESIFIKASI audience, bukan daftar socket.
Penyaringan terjadi di tepi (per koneksi lokal tiap node) sehingga dengan
Redis pub/sub tiap node cukup subscribe topik per tenant lalu menyaring
koneksinya sendiri dengan cache scope lokal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol

Status = Literal["online", "away", "offline"]
ConnStatus = Literal["online", "away"]
TypingStart = Literal["emit", "throttled", "limit"]

FEATURE_PRESENCE = "presence"
FEATURE_TYPING = "typing"


@dataclass(frozen=True)
class PresenceTransition:
    """Perubahan status agregat seorang user (hanya dipancarkan bila berubah)."""

    tenant_id: str
    user_id: str
    status: Status


@dataclass(frozen=True)
class TypingKey:
    tenant_id: str
    channel_id: str
    parent_id: str | None
    user_id: str


# ---------- Spesifikasi audience ----------


@dataclass(frozen=True)
class AllInTenant:
    """Seluruh koneksi tenant (dipakai broadcast lama tanpa `user_ids`)."""


@dataclass(frozen=True)
class UserSet:
    """Hanya user tertentu (audience channel untuk event `message.*`)."""

    user_ids: frozenset[str]


@dataclass(frozen=True)
class PresenceOf:
    """Viewer menerima bila `scope(viewer).can_see(subject_id)`."""

    subject_id: str


@dataclass(frozen=True)
class TypingIn:
    """Viewer menerima bila ada di audience channel DAN (bila viewer karyawan)
    `scope(viewer).can_see(sender_id)` — mode STRICT PRD §9.2."""

    channel_id: str
    sender_id: str
    audience: frozenset[str]


Audience = AllInTenant | UserSet | PresenceOf | TypingIn


@dataclass(frozen=True)
class RealtimeEvent:
    payload: dict
    audience: Audience
    # None = event lama (`message.*`) untuk semua klien termasuk yang tidak
    # mengirim `hello`; selain itu hanya ke koneksi yang mendeklarasikan fitur.
    feature: str | None = None
    exclude_user_id: str | None = None


# ---------- Protocol (titik ganti Redis) ----------


class PresenceStore(Protocol):
    async def add_conn(
        self, tenant_id: str, user_id: str, conn_id: str, now: float
    ) -> PresenceTransition | None: ...

    async def set_status(
        self, tenant_id: str, user_id: str, conn_id: str, status: ConnStatus, now: float
    ) -> PresenceTransition | None: ...

    async def remove_conn(
        self, tenant_id: str, user_id: str, conn_id: str, now: float
    ) -> PresenceTransition | None: ...

    async def expire(self, now: float) -> list[PresenceTransition]: ...

    async def snapshot(self, tenant_id: str) -> dict[str, Status]: ...

    def has_state(self) -> bool: ...


class TypingStore(Protocol):
    async def start(self, key: TypingKey, conn_id: str, now: float) -> TypingStart: ...

    async def stop(self, key: TypingKey) -> bool: ...

    async def clear_user_channel(
        self, tenant_id: str, channel_id: str, user_id: str
    ) -> list[TypingKey]: ...

    async def drop_conn(self, conn_id: str) -> list[TypingKey]: ...

    async def expire(self, now: float) -> list[TypingKey]: ...

    def has_state(self) -> bool: ...


EventHandler = Callable[[str, RealtimeEvent], Awaitable[None]]


class EventBus(Protocol):
    async def publish(self, tenant_id: str, event: RealtimeEvent) -> None: ...

    def subscribe(self, handler: EventHandler) -> None: ...
