"""Rate limiter sliding-window sederhana berbasis memori proses.

Cukup untuk monolith 1-2 worker; batasan: counter tidak dibagi antar
worker/instance. Karena endpoint login sudah tercatat di audit + password
policy, risiko ini dapat diterima untuk v1 (lihat docs keamanan).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, max_attempts: int, window_seconds: int) -> tuple[bool, int]:
        """True bila masih boleh lewat; selain itu (False, retry_after_detik)."""
        now = time.monotonic()
        dq = self._hits[key]
        while dq and now - dq[0] > window_seconds:
            dq.popleft()
        if len(dq) >= max_attempts:
            retry_after = int(window_seconds - (now - dq[0])) + 1
            return False, max(retry_after, 1)
        return True, 0

    def hit(self, key: str, window_seconds: int) -> None:
        dq = self._hits[key]
        dq.append(time.monotonic())
        while dq and time.monotonic() - dq[0] > window_seconds:
            dq.popleft()

    def clear(self, key: str) -> None:
        self._hits.pop(key, None)

    def reset_all(self) -> None:
        self._hits.clear()


_limiters: dict[str, SlidingWindowLimiter] = {}


def get_limiter(namespace: str) -> SlidingWindowLimiter:
    if namespace not in _limiters:
        _limiters[namespace] = SlidingWindowLimiter()
    return _limiters[namespace]


def reset_all_limiters() -> None:
    for limiter in _limiters.values():
        limiter.reset_all()
