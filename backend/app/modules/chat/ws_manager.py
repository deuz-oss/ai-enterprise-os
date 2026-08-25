"""Pluggable WebSocket manager untuk chat.

Design per PRD §9.4: manager koneksi dibuat pluggable agar scale-out
multi-instance kelak memakai Redis pub/sub tanpa mengubah caller.
v1 memakai in-memory dict; kunci: tenant_id + channel_id.
"""

import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ChatWSManager:
    def __init__(self) -> None:
        # tenant_id -> user_id -> WebSocket
        self._conns: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        # channel membership cache sederhana untuk routing

    async def connect(self, tenant_id: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._conns[tenant_id][user_id] = ws
        logger.info("Chat WS connect tenant=%s user=%s", tenant_id[:8], user_id[:8])

    async def disconnect(self, tenant_id: str, user_id: str) -> None:
        self._conns.get(tenant_id, {}).pop(user_id, None)
        logger.info("Chat WS disconnect tenant=%s user=%s", tenant_id[:8], user_id[:8])

    async def broadcast(self, channel_id: str, payload: dict) -> None:
        """v1: broadcast ke semua tenant (plugin Redis akan menyaring)."""
        text = json.dumps(payload, ensure_ascii=False)
        for by_tenant in list(self._conns.values()):
            for ws in list(by_tenant.values()):
                try:
                    await ws.send_text(text)
                except Exception:
                    pass

    def tenant_store(self) -> dict:
        return self._conns


manager = ChatWSManager()
