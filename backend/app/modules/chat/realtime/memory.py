"""Implementasi in-memory (satu proses) untuk kontrak realtime chat.

PERINGATAN: state hanya hidup di proses ini. Selama belum ada implementasi
Redis, server WAJIB berjalan dengan satu worker uvicorn (lihat Dockerfile) —
dengan >1 worker, user di worker berbeda tidak saling melihat presence,
typing, maupun event `message.*`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.chat.realtime.contracts import (
    ConnStatus,
    EventHandler,
    PresenceTransition,
    RealtimeEvent,
    Status,
    TypingKey,
    TypingStart,
)

PRESENCE_GRACE_SECONDS = 10.0
TYPING_THROTTLE_SECONDS = 3.0
TYPING_TTL_SECONDS = 6.0
TYPING_MAX_ACTIVE_PER_USER = 5


def _aggregate(statuses: dict[str, ConnStatus]) -> Status:
    if not statuses:
        return "offline"
    return "online" if any(s == "online" for s in statuses.values()) else "away"


class InMemoryPresenceStore:
    """Presence agregat per user dari banyak koneksi (multi-tab/perangkat).

    - online: ada >=1 koneksi berstatus online
    - away: semua koneksi away
    - offline: nol koneksi selama masa grace (default 10 dtk) — reconnect
      dalam masa grace (mis. reload halaman) tidak memancarkan event apa pun.
    """

    def __init__(self, grace_seconds: float = PRESENCE_GRACE_SECONDS) -> None:
        self.grace_seconds = grace_seconds
        self._conns: dict[tuple[str, str], dict[str, ConnStatus]] = {}
        self._emitted: dict[tuple[str, str], Status] = {}
        self._pending_offline: dict[tuple[str, str], float] = {}

    def _transition(self, key: tuple[str, str]) -> PresenceTransition | None:
        conns = self._conns.get(key) or {}
        if not conns and key in self._pending_offline:
            return None  # status offline ditunda sampai grace habis
        new = _aggregate(conns)
        if new == self._emitted.get(key, "offline"):
            return None
        if new == "offline":
            self._emitted.pop(key, None)
        else:
            self._emitted[key] = new
        return PresenceTransition(tenant_id=key[0], user_id=key[1], status=new)

    async def add_conn(
        self, tenant_id: str, user_id: str, conn_id: str, now: float
    ) -> PresenceTransition | None:
        key = (tenant_id, user_id)
        self._conns.setdefault(key, {})[conn_id] = "online"
        self._pending_offline.pop(key, None)
        return self._transition(key)

    async def set_status(
        self, tenant_id: str, user_id: str, conn_id: str, status: ConnStatus, now: float
    ) -> PresenceTransition | None:
        key = (tenant_id, user_id)
        conns = self._conns.get(key)
        if conns is None or conn_id not in conns:
            return None
        conns[conn_id] = status
        return self._transition(key)

    async def remove_conn(
        self, tenant_id: str, user_id: str, conn_id: str, now: float
    ) -> PresenceTransition | None:
        key = (tenant_id, user_id)
        conns = self._conns.get(key)
        if conns is None:
            return None
        conns.pop(conn_id, None)
        if conns:
            return self._transition(key)
        del self._conns[key]
        if key in self._emitted:
            self._pending_offline[key] = now + self.grace_seconds
        return None

    async def expire(self, now: float) -> list[PresenceTransition]:
        out: list[PresenceTransition] = []
        for key, deadline in list(self._pending_offline.items()):
            if deadline > now:
                continue
            del self._pending_offline[key]
            if key in self._conns:
                continue
            transition = self._transition(key)
            if transition is not None:
                out.append(transition)
        return out

    async def snapshot(self, tenant_id: str) -> dict[str, Status]:
        return {uid: st for (tid, uid), st in self._emitted.items() if tid == tenant_id}

    def has_state(self) -> bool:
        return bool(self._conns or self._pending_offline)


@dataclass
class _TypingState:
    conn_id: str
    expires_at: float
    last_emit: float


class InMemoryTypingStore:
    """Typing per (tenant, channel, thread, user) dengan throttle & TTL.

    - `start` pertama langsung dipancarkan; berikutnya dalam 3 dtk hanya
      memperpanjang TTL ("throttled").
    - Tanpa refresh 6 dtk -> kedaluwarsa (hub memancarkan `stop`).
    - Maks 5 typing aktif per user (anti-spam lintas channel).
    """

    def __init__(
        self,
        throttle_seconds: float = TYPING_THROTTLE_SECONDS,
        ttl_seconds: float = TYPING_TTL_SECONDS,
        max_active_per_user: int = TYPING_MAX_ACTIVE_PER_USER,
    ) -> None:
        self.throttle_seconds = throttle_seconds
        self.ttl_seconds = ttl_seconds
        self.max_active_per_user = max_active_per_user
        self._active: dict[TypingKey, _TypingState] = {}

    async def start(self, key: TypingKey, conn_id: str, now: float) -> TypingStart:
        state = self._active.get(key)
        if state is not None:
            state.expires_at = now + self.ttl_seconds
            state.conn_id = conn_id
            if now - state.last_emit >= self.throttle_seconds:
                state.last_emit = now
                return "emit"
            return "throttled"
        active_for_user = sum(
            1 for k in self._active if k.tenant_id == key.tenant_id and k.user_id == key.user_id
        )
        if active_for_user >= self.max_active_per_user:
            return "limit"
        self._active[key] = _TypingState(
            conn_id=conn_id, expires_at=now + self.ttl_seconds, last_emit=now
        )
        return "emit"

    async def stop(self, key: TypingKey) -> bool:
        return self._active.pop(key, None) is not None

    async def clear_user_channel(
        self, tenant_id: str, channel_id: str, user_id: str
    ) -> list[TypingKey]:
        keys = [
            k
            for k in self._active
            if k.tenant_id == tenant_id and k.channel_id == channel_id and k.user_id == user_id
        ]
        for k in keys:
            del self._active[k]
        return keys

    async def drop_conn(self, conn_id: str) -> list[TypingKey]:
        keys = [k for k, st in self._active.items() if st.conn_id == conn_id]
        for k in keys:
            del self._active[k]
        return keys

    async def expire(self, now: float) -> list[TypingKey]:
        keys = [k for k, st in self._active.items() if st.expires_at <= now]
        for k in keys:
            del self._active[k]
        return keys

    def has_state(self) -> bool:
        return bool(self._active)


class InMemoryEventBus:
    """Bus satu proses: publish langsung memanggil handler lokal (hub)."""

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    async def publish(self, tenant_id: str, event: RealtimeEvent) -> None:
        for handler in list(self._handlers):
            await handler(tenant_id, event)

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)
