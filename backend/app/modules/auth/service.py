from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.modules.auth.models import PasswordResetToken, User
from app.modules.auth.schemas import UserCreate


def _find_users_by_email_unfiltered(db: Session, email: str) -> list[User]:
    """Cari user by email TANPA filter tenant (opsi eksekusi eksplisit)."""
    stmt = (
        select(User)
        .where(User.email == email)
        .execution_options(include_with_loader_criteria=False)
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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email sudah terdaftar")
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


def issue_password_reset_token(db: Session, user: User) -> str:
    """Buat token reset satu kali pakai untuk user; kembalikan token mentah.

    Token mentah hanya tampil sekali (diteruskan admin ke user via kanal
    out-of-band); database menyimpan hash SHA-256-nya.
    """
    import hashlib
    from uuid import uuid4

    settings = get_settings()
    raw = f"{user.id}-{uuid4().hex}"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_ttl_min),
        )
    )
    # Batasi riwayat: token lama/terpakai milik user yang sama dibuang.
    for stale in db.scalars(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    ).all():
        if stale.token_hash != token_hash:
            db.delete(stale)
    db.commit()
    return raw


def consume_password_reset_token(db: Session, raw_token: str, new_password: str) -> User:
    """Validasi & pakai token reset, lalu ganti password pemiliknya."""
    import hashlib

    if len(new_password) < 8:
        raise HTTPException(status_code=422, detail="Password minimal 8 karakter")
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    row = db.scalars(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()
    # SQLite menyimpan tz-aware sebagai naive — samakan basis perbandingan.
    now = (
        datetime.now(UTC).replace(tzinfo=None)
        if row and row.expires_at.tzinfo is None
        else datetime.now(UTC)
    )
    if row is None or row.used_at is not None or row.expires_at < now:
        raise HTTPException(status_code=422, detail="Token tidak valid atau kedaluwarsa")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    user.hashed_password = hash_password(new_password)
    row.used_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


def change_own_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    """User aktif mengganti password sendiri; wajib tahu password lama."""
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=422, detail="Password lama salah")
    if len(new_password) < 8:
        raise HTTPException(status_code=422, detail="Password minimal 8 karakter")
    user.hashed_password = hash_password(new_password)
    db.commit()
