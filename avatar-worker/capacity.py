"""Kapasitas sesi avatar paralel (AVATAR_MAX_SESSIONS).

Antrean sengaja SEDERHANA: tidak ada daftar tunggu. Sesi yang datang saat
penuh dijawab 503 dan agen menjalankannya voice-only -- kandidat tidak
pernah ditolak atau disuruh menunggu karena GPU sibuk.
"""

from __future__ import annotations


class SessionSlots:
    def __init__(self, max_sessions: int) -> None:
        self.max_sessions = max(0, max_sessions)
        self._rooms: set[str] = set()

    @property
    def active(self) -> int:
        return len(self._rooms)

    def holds(self, room: str) -> bool:
        return room in self._rooms

    def try_acquire(self, room: str) -> bool:
        if room in self._rooms:
            return True
        if len(self._rooms) >= self.max_sessions:
            return False
        self._rooms.add(room)
        return True

    def release(self, room: str) -> None:
        self._rooms.discard(room)
