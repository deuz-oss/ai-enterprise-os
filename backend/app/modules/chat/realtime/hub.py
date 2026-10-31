"""RealtimeHub: registry koneksi WS chat + presence + typing (PRD §9.2 & §9.4).

Kontrak pesan (JSON, maks 4 KB per frame):

Klien -> server
- {"type": "hello", "features": ["presence", "typing"]}
- {"type": "ping"}
- {"type": "presence.set", "status": "online" | "away"}
- {"type": "typing.start" | "typing.stop", "channel_id": "<uuid>", "parent_id": null | "<uuid>"}

Server -> klien
- {"event": "message.*", "channel_id": "..."}  (lama; ke SEMUA klien, tanpa hello)
- {"event": "pong"}
- {"event": "presence.snapshot", "users": [{"user_id": "...", "status": "online|away"}]}
- {"event": "presence.updated", "user_id": "...", "status": "online|away|offline"}
- {"event": "typing", "channel_id": "...", "parent_id": null | "...", "user_id": "...",
   "user_name": "...", "state": "start" | "stop"}
- {"event": "error", "code": "bad_request" | "typing_rejected" | "rate_limited"}

Presence & typing hanya dikirim ke koneksi yang sudah `hello` dengan fitur
terkait (opt-in -> klien lama tidak terganggu). Semua penyaringan audience
memakai aturan scope yang sama dengan REST (`chat/scope.py`, `service.py`).
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import time
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from starlette.concurrency import run_in_threadpool

from app.modules.chat.realtime.cache import AudienceCache, load_session_valid
from app.modules.chat.realtime.contracts import (
    FEATURE_PRESENCE,
    FEATURE_TYPING,
    AllInTenant,
    Audience,
    ConnStatus,
    EventBus,
    PresenceOf,
    PresenceStore,
    PresenceTransition,
    RealtimeEvent,
    TypingIn,
    TypingKey,
    TypingStore,
    UserSet,
)
from app.modules.chat.realtime.memory import (
    InMemoryEventBus,
    InMemoryPresenceStore,
    InMemoryTypingStore,
)

logger = logging.getLogger(__name__)

IDLE_CLOSE_SECONDS = 70.0
RATE_LIMIT_FRAMES = 20
RATE_LIMIT_WINDOW_SECONDS = 10.0
REVALIDATE_SECONDS = 60.0
MAX_FRAME_BYTES = 4096
SWEEP_INTERVAL_SECONDS = 1.0

_KNOWN_FEATURES = {FEATURE_PRESENCE, FEATURE_TYPING}
_conn_seq = itertools.count(1)


@dataclass(eq=False)
class Connection:
    conn_id: str
    tenant_id: str
    user_id: str
    user_name: str
    ws: Any
    token_payload: dict
    last_frame_at: float
    revalidate_at: float
    features: set[str] = field(default_factory=set)
    hello: bool = False
    frame_times: deque[float] = field(default_factory=deque)
    closed: bool = False


def _uuid_str(value: object) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


class RealtimeHub:
    def __init__(
        self,
        *,
        presence: PresenceStore | None = None,
        typing: TypingStore | None = None,
        bus: EventBus | None = None,
        clock: Callable[[], float] = time.monotonic,
        cache: AudienceCache | None = None,
        sweeper: bool = True,
        idle_close_seconds: float = IDLE_CLOSE_SECONDS,
        rate_limit_frames: int = RATE_LIMIT_FRAMES,
        rate_limit_window: float = RATE_LIMIT_WINDOW_SECONDS,
        revalidate_seconds: float = REVALIDATE_SECONDS,
    ) -> None:
        self.presence: PresenceStore = presence or InMemoryPresenceStore()
        self.typing: TypingStore = typing or InMemoryTypingStore()
        self.bus: EventBus = bus or InMemoryEventBus()
        self.clock = clock
        self.cache = cache or AudienceCache(clock)
        self.sweeper_enabled = sweeper
        self.idle_close_seconds = idle_close_seconds
        self.rate_limit_frames = rate_limit_frames
        self.rate_limit_window = rate_limit_window
        self.revalidate_seconds = revalidate_seconds
        # tenant_id -> user_id -> conn_id -> Connection
        self._conns: dict[str, dict[str, dict[str, Connection]]] = {}
        self._names: dict[tuple[str, str], str] = {}
        self._dirty_tenants: set[str] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sweeper_task: asyncio.Task | None = None
        self.bus.subscribe(self._deliver)

    # ---------- siklus hidup koneksi ----------

    async def connect(
        self,
        tenant_id: str,
        user_id: str,
        ws: Any,
        *,
        user_name: str = "",
        token_payload: dict | None = None,
    ) -> Connection:
        await ws.accept()
        self._loop = asyncio.get_running_loop()
        now = self.clock()
        conn = Connection(
            conn_id=f"c{next(_conn_seq)}",
            tenant_id=tenant_id,
            user_id=user_id,
            user_name=user_name,
            ws=ws,
            token_payload=token_payload or {},
            last_frame_at=now,
            revalidate_at=now + self.revalidate_seconds,
        )
        self._conns.setdefault(tenant_id, {}).setdefault(user_id, {})[conn.conn_id] = conn
        self._names[(tenant_id, user_id)] = user_name
        logger.info("Chat WS connect tenant=%s user=%s", tenant_id[:8], user_id[:8])
        await self._publish_presence(
            await self.presence.add_conn(tenant_id, user_id, conn.conn_id, now)
        )
        self._ensure_sweeper()
        return conn

    async def disconnect(self, conn: Connection) -> None:
        """Idempoten: aman dipanggil dari router (finally) maupun saat hub menutup."""
        user_conns = self._conns.get(conn.tenant_id, {}).get(conn.user_id)
        if user_conns is None or user_conns.pop(conn.conn_id, None) is None:
            return
        if not user_conns:
            self._conns[conn.tenant_id].pop(conn.user_id, None)
            if not self._conns[conn.tenant_id]:
                self._conns.pop(conn.tenant_id, None)
        logger.info("Chat WS disconnect tenant=%s user=%s", conn.tenant_id[:8], conn.user_id[:8])
        now = self.clock()
        for key in await self.typing.drop_conn(conn.conn_id):
            await self._publish_typing(key, "stop")
        await self._publish_presence(
            await self.presence.remove_conn(conn.tenant_id, conn.user_id, conn.conn_id, now)
        )

    async def close(self, conn: Connection, code: int) -> None:
        if not conn.closed:
            conn.closed = True
            try:
                await conn.ws.close(code=code)
            except Exception:  # noqa: BLE001 - socket mungkin sudah putus
                pass
        await self.disconnect(conn)

    # ---------- pesan masuk ----------

    async def handle(self, conn: Connection, text: str) -> bool:
        """Proses satu frame klien. False = koneksi sudah ditutup hub."""
        now = self.clock()
        conn.last_frame_at = now
        conn.frame_times.append(now)
        while conn.frame_times and conn.frame_times[0] <= now - self.rate_limit_window:
            conn.frame_times.popleft()
        if len(conn.frame_times) > self.rate_limit_frames:
            await self._send(conn, {"event": "error", "code": "rate_limited"})
            await self.close(conn, 1008)
            return False
        if len(text.encode("utf-8")) > MAX_FRAME_BYTES:
            await self._error(conn, "bad_request")
            return True
        try:
            msg = json.loads(text)
        except ValueError:
            msg = None
        if not isinstance(msg, dict):
            await self._error(conn, "bad_request")
            return True
        kind = msg.get("type")
        if kind == "ping":
            await self._send(conn, {"event": "pong"})
        elif kind == "hello":
            await self._on_hello(conn, msg)
        elif kind == "presence.set":
            await self._on_presence_set(conn, msg)
        elif kind in ("typing.start", "typing.stop"):
            await self._on_typing(conn, msg, start=kind == "typing.start")
        else:
            await self._error(conn, "bad_request")
        return True

    async def _on_hello(self, conn: Connection, msg: dict) -> None:
        raw = msg.get("features")
        features = {f for f in raw if isinstance(f, str)} if isinstance(raw, list) else set()
        conn.features = features & _KNOWN_FEATURES
        conn.hello = True
        if FEATURE_PRESENCE in conn.features:
            await self._send_snapshot(conn)

    async def _on_presence_set(self, conn: Connection, msg: dict) -> None:
        status = msg.get("status")
        if status not in ("online", "away"):
            await self._error(conn, "bad_request")
            return
        conn_status: ConnStatus = "online" if status == "online" else "away"
        await self._publish_presence(
            await self.presence.set_status(
                conn.tenant_id, conn.user_id, conn.conn_id, conn_status, self.clock()
            )
        )

    async def _on_typing(self, conn: Connection, msg: dict, *, start: bool) -> None:
        channel_id = _uuid_str(msg.get("channel_id"))
        raw_parent = msg.get("parent_id")
        parent_id = _uuid_str(raw_parent) if raw_parent is not None else None
        if channel_id is None or (raw_parent is not None and parent_id is None):
            await self._error(conn, "bad_request")
            return
        key = TypingKey(conn.tenant_id, channel_id, parent_id, conn.user_id)
        if not start:
            if await self.typing.stop(key):
                await self._publish_typing(key, "stop")
            return
        # Satu kode error untuk channel tak ada / tenant lain / non-member /
        # broadcast: tidak ada oracle keberadaan channel.
        if not await self.cache.can_type(conn.tenant_id, conn.user_id, channel_id, parent_id):
            await self._error(conn, "typing_rejected")
            return
        result = await self.typing.start(key, conn.conn_id, self.clock())
        if result == "limit":
            await self._error(conn, "rate_limited")
        elif result == "emit":
            await self._publish_typing(key, "start")

    # ---------- publikasi ----------

    async def _publish_presence(self, transition: PresenceTransition | None) -> None:
        if transition is None:
            return
        await self.bus.publish(
            transition.tenant_id,
            RealtimeEvent(
                payload={
                    "event": "presence.updated",
                    "user_id": transition.user_id,
                    "status": transition.status,
                },
                audience=PresenceOf(transition.user_id),
                feature=FEATURE_PRESENCE,
                exclude_user_id=transition.user_id,
            ),
        )

    async def _publish_typing(self, key: TypingKey, state: str) -> None:
        audience = await self.cache.channel_audience(key.tenant_id, key.channel_id)
        if not audience:
            return
        await self.bus.publish(
            key.tenant_id,
            RealtimeEvent(
                payload={
                    "event": "typing",
                    "channel_id": key.channel_id,
                    "parent_id": key.parent_id,
                    "user_id": key.user_id,
                    "user_name": self._names.get((key.tenant_id, key.user_id), ""),
                    "state": state,
                },
                audience=TypingIn(key.channel_id, key.user_id, audience),
                feature=FEATURE_TYPING,
                exclude_user_id=key.user_id,
            ),
        )

    async def broadcast(
        self, tenant_id: str, payload: dict, user_ids: set[str] | None = None
    ) -> None:
        """API lama (event `message.*`): ke semua koneksi tenant atau `user_ids`,
        termasuk klien yang tidak mengirim `hello`."""
        audience: Audience = (
            AllInTenant() if user_ids is None else UserSet(frozenset(str(u) for u in user_ids))
        )
        await self.bus.publish(tenant_id, RealtimeEvent(payload=payload, audience=audience))

    async def _deliver(self, tenant_id: str, event: RealtimeEvent) -> None:
        for user_id, conns in list(self._conns.get(tenant_id, {}).items()):
            if user_id == event.exclude_user_id:
                continue
            targets = [
                c for c in conns.values() if event.feature is None or event.feature in c.features
            ]
            if not targets or not await self._allowed(tenant_id, user_id, event.audience):
                continue
            for conn in targets:
                await self._send(conn, event.payload)

    async def _allowed(self, tenant_id: str, viewer_id: str, audience: Audience) -> bool:
        if isinstance(audience, AllInTenant):
            return True
        if isinstance(audience, UserSet):
            return viewer_id in audience.user_ids
        if isinstance(audience, PresenceOf):
            if audience.subject_id == viewer_id:
                return False
            scope = await self.cache.directory_scope(tenant_id, viewer_id)
            return scope.can_see(audience.subject_id)
        if isinstance(audience, TypingIn):
            if viewer_id not in audience.audience:
                return False
            # STRICT (PRD §9.2): penerima karyawan hanya melihat typing dari
            # user dalam scope direktorinya, walau sama-sama member channel.
            scope = await self.cache.directory_scope(tenant_id, viewer_id)
            return scope.can_see(audience.sender_id)
        return False

    async def _send_snapshot(self, conn: Connection) -> None:
        snapshot = await self.presence.snapshot(conn.tenant_id)
        scope = await self.cache.directory_scope(conn.tenant_id, conn.user_id)
        users = [
            {"user_id": uid, "status": status}
            for uid, status in sorted(snapshot.items())
            if uid != conn.user_id and scope.can_see(uid)
        ]
        await self._send(conn, {"event": "presence.snapshot", "users": users})

    async def _send(self, conn: Connection, payload: dict) -> None:
        if conn.closed:
            return
        try:
            await conn.ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:  # noqa: BLE001 - socket putus ditangani router
            pass

    async def _error(self, conn: Connection, code: str) -> None:
        await self._send(conn, {"event": "error", "code": code})

    # ---------- pemeliharaan berkala ----------

    async def tick(self) -> None:
        """Kedaluwarsa presence/typing, tutup koneksi idle/tidak valid, kirim
        ulang snapshot untuk tenant yang scope-nya di-invalidate."""
        now = self.clock()
        for transition in await self.presence.expire(now):
            await self._publish_presence(transition)
        for key in await self.typing.expire(now):
            await self._publish_typing(key, "stop")
        for conn in self._all_conns():
            if conn.hello and now - conn.last_frame_at > self.idle_close_seconds:
                await self.close(conn, 1001)
                continue
            if now >= conn.revalidate_at:
                conn.revalidate_at = now + self.revalidate_seconds
                valid = await run_in_threadpool(
                    load_session_valid, conn.tenant_id, conn.user_id, conn.token_payload
                )
                if not valid:
                    await self.close(conn, 1008)
        dirty, self._dirty_tenants = self._dirty_tenants, set()
        for tenant_id in dirty:
            for conn in self._all_conns(tenant_id):
                if FEATURE_PRESENCE in conn.features:
                    await self._send_snapshot(conn)

    def _all_conns(self, tenant_id: str | None = None) -> list[Connection]:
        tenants = [tenant_id] if tenant_id is not None else list(self._conns)
        return [
            conn
            for tid in tenants
            for conns in list(self._conns.get(tid, {}).values())
            for conn in list(conns.values())
        ]

    def _has_state(self) -> bool:
        return bool(self._conns) or self.presence.has_state() or self.typing.has_state()

    def _ensure_sweeper(self) -> None:
        if not self.sweeper_enabled:
            return
        if self._sweeper_task is None or self._sweeper_task.done():
            self._sweeper_task = asyncio.get_running_loop().create_task(self._sweep_loop())

    async def _sweep_loop(self) -> None:
        while True:
            await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
            try:
                await self.tick()
            except Exception:  # noqa: BLE001 - sweeper tidak boleh mati diam-diam
                logger.exception("Chat realtime sweeper gagal")
            if not self._has_state():
                return

    # ---------- jembatan dari kode sync (service REST di threadpool) ----------

    def _submit(self, factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """Jadwalkan coroutine di event loop hub dari konteks mana pun.

        Endpoint REST `def` berjalan di threadpool tanpa event loop — dulu
        `_notify_channel` memakai `asyncio.get_running_loop()` di sana sehingga
        event `message.*` tidak pernah terkirim. Sekarang dijadwalkan ke loop
        tempat koneksi WS hidup via `run_coroutine_threadsafe`.
        """
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is not None:
            running.create_task(factory())
            return
        loop = self._loop
        if loop is None or loop.is_closed() or not loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(factory(), loop)

    def _call_soon(self, fn: Callable[[], None]) -> None:
        loop = self._loop
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if loop is None or loop is running or loop.is_closed() or not loop.is_running():
            fn()
        else:
            loop.call_soon_threadsafe(fn)

    def has_tenant_connections(self, tenant_id: str) -> bool:
        """Ada koneksi WS lokal di tenant ini? (bus in-memory: tanpa koneksi,
        tidak perlu menghitung audience sama sekali). Versi Redis kelak harus
        selalu True karena koneksi bisa berada di node lain."""
        return tenant_id in self._conns

    def broadcast_threadsafe(
        self, tenant_id: str, payload: dict, user_ids: set[str] | None = None
    ) -> None:
        if tenant_id not in self._conns:
            return  # tidak ada koneksi lokal di tenant ini (bus in-memory)
        self._submit(lambda: self.broadcast(tenant_id, payload, user_ids))

    def clear_typing_threadsafe(self, tenant_id: str, channel_id: str, user_id: str) -> None:
        """Pengirim baru saja memposting pesan -> hentikan indikator typing-nya."""
        if tenant_id not in self._conns:
            return

        async def run() -> None:
            for key in await self.typing.clear_user_channel(tenant_id, channel_id, user_id):
                await self._publish_typing(key, "stop")

        self._submit(run)

    def invalidate_channel(self, tenant_id: str, channel_id: str) -> None:
        self._call_soon(lambda: self.cache.invalidate_channel(tenant_id, channel_id))

    def invalidate_tenant_scope(self, tenant_id: str) -> None:
        def run() -> None:
            self.cache.invalidate_tenant(tenant_id)
            self._dirty_tenants.add(tenant_id)

        self._call_soon(run)
