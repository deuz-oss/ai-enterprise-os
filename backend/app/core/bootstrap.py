from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password

logger = logging.getLogger(__name__)


def ensure_admin_user(db: Session) -> None:
    from app.modules.auth.models import User

    settings = get_settings()
    existing = db.execute(
        select(User).where(User.email == settings.admin_email)
    ).scalar_one_or_none()
    if existing is not None:
        return
    admin = User(
        email=settings.admin_email,
        full_name="Administrator",
        role="admin",
        hashed_password=hash_password(settings.admin_password),
    )
    db.add(admin)
    db.commit()
    logger.info("Bootstrap admin created: %s", settings.admin_email)
