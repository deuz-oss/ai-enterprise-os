from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.schemas import UserCreate


def _find_users_by_email_unfiltered(db: Session, email: str) -> list[User]:
    """Cari user by email TANPA filter tenant (opsi eksekusi eksplisit)."""
    stmt = select(User).where(User.email == email).execution_options(
        include_with_loader_criteria=False
    )
    return list(db.scalars(stmt).all())


def get_by_email(db: Session, email: str) -> User | None:
    """Cek keunikan email secara global — abaikan konteks tenant."""
    users = _find_users_by_email_unfiltered(db, email)
    return users[0] if users else None


def create_user(db: Session, payload: UserCreate, tenant_id=None) -> User:
    """Buat akun baru.

    - Dari admin tenant (konteks tenant aktif): tenant_id otomatis diinjeksi.
    - Dari provisioning platform: tenant_id wajib eksplisit.
    - Email dicek unik secara global agar alur login tanpa subdomain tetap
      sederhana (batasan v1 multi-tenant).
    """
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password minimal 8 karakter")
    if get_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email sudah terdaftar"
        )
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password(payload.password),
        tenant_id=tenant_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    users = _find_users_by_email_unfiltered(db, email)
    # Email unik global dijaga oleh create_user, tapi antisipasi bila data
    # lama/seed menghasilkan lebih dari satu akun dengan email sama.
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email dipakai di lebih dari satu tenant; gunakan portal tenant masing-masing",
        )
    user = users[0] if users else None
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
