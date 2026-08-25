"""Bootstrap data awal: tenant default, admin tenant, dan platform admin.

Semua operasi berjalan tanpa konteks tenant (sistem), sehingga tenant_id
disetel eksplisit pada baris yang membutuhkannya.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password

logger = logging.getLogger(__name__)

DEFAULT_TENANT_SLUG = "default"

# Kunci advisory PostgreSQL: mencegah balapan antar worker uvicorn yang
# menjalankan bootstrap bersamaan saat start.
_BOOTSTRAP_LOCK_KEY = 918_273_645


@contextmanager
def _bootstrap_lock(db: Session):
    is_pg = db.bind.dialect.name == "postgresql"  # type: ignore[union-attr]
    if is_pg:
        db.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _BOOTSTRAP_LOCK_KEY})
    try:
        yield
    finally:
        if is_pg:
            db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _BOOTSTRAP_LOCK_KEY})


def ensure_default_tenant(db: Session):
    """Pastikan ada tenant 'default' untuk mode single-tenant/dev."""
    from app.modules.platform.service import get_or_create_default_tenant

    return get_or_create_default_tenant(db, slug=DEFAULT_TENANT_SLUG)


def _find_user_unfiltered(db: Session, email: str):
    from app.modules.auth.models import User

    stmt = (
        select(User)
        .where(User.email == email)
        .execution_options(include_with_loader_criteria=False)
    )
    return db.execute(stmt).scalar_one_or_none()


def run_bootstrap(db: Session) -> None:
    from app.modules.auth.models import User, UserRole

    settings = get_settings()
    with _bootstrap_lock(db):
        default_tenant = ensure_default_tenant(db)

        # 1) Admin tenant default
        if _find_user_unfiltered(db, settings.admin_email) is None:
            admin = User(
                email=settings.admin_email,
                full_name="Administrator",
                role=UserRole.admin,
                hashed_password=hash_password(settings.admin_password),
                tenant_id=default_tenant.id,
            )
            db.add(admin)
            logger.info("Bootstrap admin tenant '%s' dibuat: %s", DEFAULT_TENANT_SLUG, admin.email)

        # 2) Platform admin (opsional; aktif jika password diset di env)
        if settings.platform_admin_password:
            if _find_user_unfiltered(db, settings.platform_admin_email) is None:
                platform_admin = User(
                    email=settings.platform_admin_email,
                    full_name="Platform Admin",
                    role=UserRole.platform_admin,
                    hashed_password=hash_password(settings.platform_admin_password),
                    tenant_id=None,
                )
                db.add(platform_admin)
                logger.info("Bootstrap platform admin dibuat: %s", platform_admin.email)

        db.commit()
