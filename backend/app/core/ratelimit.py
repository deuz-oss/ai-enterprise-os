"""Rate limiter sliding-window berbasis Postgres (tabel `rate_limit_hits`).

Dulu murni in-memory per-proses (`dict[str, deque]`) — cukup utk 1 worker,
tapi tidak dibagi antar worker/instance saat di-scale horizontal. Sekarang
counter disimpan di Postgres (sudah jadi sumber kebenaran bersama utk semua
hal lain di app ini), jadi benar walau backend jalan >1 worker/instance —
tanpa menambah infra baru (tidak ada Redis di stack).

Tabel ini SENGAJA tidak pakai `TenantMixin`/scoping tenant — pemeriksaan
rate-limit terjadi pra-autentikasi (login, forgot-password, reset-password),
sebelum konteks tenant ada; key-nya per IP/email, bukan per tenant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base


class RateLimitHit(Base):
    """Satu percobaan (login/reset) yang tercatat pada `namespace`+`key`."""

    __tablename__ = "rate_limit_hits"
    __table_args__ = (Index("ix_ratelimit_ns_key_time", "namespace", "key", "hit_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    namespace: Mapped[str] = mapped_column(String(50))
    key: Mapped[str] = mapped_column(String(255))
    hit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SlidingWindowLimiter:
    """Terikat ke satu `namespace` (mis. "login", "password_reset")."""

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace

    def check(
        self, db: Session, key: str, max_attempts: int, window_seconds: int
    ) -> tuple[bool, int]:
        """True bila masih boleh lewat; selain itu (False, retry_after_detik).

        Cutoff dihitung di Python (bukan aritmetika `NOW()` sisi-DB) supaya
        portable lintas dialect (Postgres di Docker, SQLite fallback lokal &
        di test).
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=window_seconds)
        count = db.execute(
            select(func.count())
            .select_from(RateLimitHit)
            .where(
                RateLimitHit.namespace == self.namespace,
                RateLimitHit.key == key,
                RateLimitHit.hit_at >= cutoff,
            )
        ).scalar_one()
        if count >= max_attempts:
            oldest = db.execute(
                select(func.min(RateLimitHit.hit_at)).where(
                    RateLimitHit.namespace == self.namespace,
                    RateLimitHit.key == key,
                    RateLimitHit.hit_at >= cutoff,
                )
            ).scalar_one()
            if oldest is not None:
                if oldest.tzinfo is None:
                    oldest = oldest.replace(tzinfo=UTC)
                retry_after = int(window_seconds - (now - oldest).total_seconds()) + 1
            else:
                retry_after = window_seconds
            return False, max(retry_after, 1)
        return True, 0

    def hit(self, db: Session, key: str, window_seconds: int) -> None:
        cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
        # Bersihkan baris kedaluwarsa utk key ini dulu — bounding pertumbuhan
        # tabel tanpa perlu job pembersihan terjadwal terpisah.
        db.execute(
            delete(RateLimitHit).where(
                RateLimitHit.namespace == self.namespace,
                RateLimitHit.key == key,
                RateLimitHit.hit_at < cutoff,
            )
        )
        db.add(RateLimitHit(namespace=self.namespace, key=key))
        db.commit()

    def clear(self, db: Session, key: str) -> None:
        db.execute(
            delete(RateLimitHit).where(
                RateLimitHit.namespace == self.namespace,
                RateLimitHit.key == key,
            )
        )
        db.commit()


_limiters: dict[str, SlidingWindowLimiter] = {}


def get_limiter(namespace: str) -> SlidingWindowLimiter:
    if namespace not in _limiters:
        _limiters[namespace] = SlidingWindowLimiter(namespace)
    return _limiters[namespace]


def reset_all_limiters(db: Session) -> None:
    """Hapus semua baris rate-limit — dipakai test antar-run."""
    db.execute(delete(RateLimitHit))
    db.commit()
