"""Titik akses manager WebSocket chat (kompatibel dengan caller lama).

Design per PRD §9.4: manager koneksi dibuat pluggable agar scale-out
multi-instance kelak memakai Redis pub/sub tanpa mengubah caller.
Implementasinya kini `RealtimeHub` (presence, typing, multi-koneksi per
user) dengan store & bus in-memory; lihat `realtime/contracts.py` untuk
Protocol yang perlu diimplementasikan versi Redis.

Selalu ambil hub lewat `get_hub()` (atau atribut modul `manager` saat
dipanggil) supaya test bisa mengganti instance-nya.
"""

from app.modules.chat.realtime.hub import Connection, RealtimeHub

# Alias lama: test & kode yang masih memakai nama ChatWSManager.
ChatWSManager = RealtimeHub

manager = RealtimeHub()


def get_hub() -> RealtimeHub:
    # Dibaca dari globals modul saat dipanggil -> ikut monkeypatch `manager`.
    return manager


__all__ = ["ChatWSManager", "Connection", "RealtimeHub", "get_hub", "manager"]
