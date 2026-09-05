from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.modules.billing.models  # noqa: F401  -- registrasi tabel TenantSubscription
from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()

# 600k rounds = rekomendasi OWASP saat ini utk PBKDF2-HMAC-SHA256 (sebelumnya
# default passlib ~29k, ~20x lebih murah untuk di-brute-force offline kalau
# dump DB bocor). deprecated="auto" -- hash lama otomatis di-rehash saat
# verify_password() berikutnya berhasil, tanpa migrasi data.
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"], pbkdf2_sha256__rounds=600_000, deprecated="auto"
)
bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def verify_and_update_password(plain: str, hashed: str) -> tuple[bool, str | None]:
    """Verifikasi, dan kalau hash lama pakai parameter usang (mis. rounds
    rendah sebelum diperketat ke 600k), kembalikan hash baru untuk disimpan
    ulang oleh caller. `new_hash` None berarti tidak perlu update."""
    try:
        ok, new_hash = pwd_context.verify_and_update(plain, hashed)
    except ValueError:
        return False, None
    return ok, new_hash


def create_access_token(subject: str, tenant_id: UUID | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "tid": str(tenant_id) if tenant_id else None}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def decode_token_payload(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload if isinstance(payload, dict) else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    from app.core.tenancy import set_tenant
    from app.modules.auth.models import User

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
    )
    if credentials is None:
        raise unauthorized
    subject = decode_token(credentials.credentials)
    if subject is None:
        raise unauthorized
    try:
        user_id = UUID(subject)
    except ValueError:
        raise unauthorized from None
    # Cari user tanpa filter tenant (konteks belum ada pada titik ini).
    stmt = (
        select(User).where(User.id == user_id).execution_options(include_with_loader_criteria=False)
    )
    user = db.execute(stmt).scalar_one_or_none()
    if user is None or not user.is_active:
        raise unauthorized
    # Sumber kebenaran tenant adalah DB akun, bukan klaim token.
    set_tenant(user.tenant_id)
    return user


def require_roles(*allowed_roles: str):
    """Dependency pembatas akses per role. Admin tenant selalu diizinkan.

    Catatan: bypass ini TIDAK berlaku untuk endpoint /platform/* — gunakan
    `require_platform_admin` di sana agar admin tenant tidak ikut lolos.
    """

    def dependency(user=Depends(get_current_user)):
        if user.role == "admin" or user.role.value in allowed_roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role Anda tidak memiliki akses ke fitur ini",
        )

    return dependency


def require_platform_admin():
    """Khusus pengelola SaaS; tanpa bypass apa pun."""

    def dependency(user=Depends(get_current_user)):
        if user.role == "platform_admin":
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya platform admin yang memiliki akses",
        )

    return dependency


def _is_billing_bypass(db: Session, tenant_id) -> bool:
    """PRD v3.0 per-tenant override: inherit → ikut APP_MODE global."""
    from app.core.config import get_settings as _get_settings

    mode = _get_settings().app_mode
    if tenant_id is None:
        return mode == "internal"
    try:
        from app.modules.platform.models import Tenant

        tenant = db.get(Tenant, tenant_id)
        if tenant and hasattr(tenant, "billing_mode"):
            bm = (tenant.billing_mode or "inherit").lower()
            if bm == "internal":
                return True
            if bm == "commercial":
                return False
    except Exception:
        pass
    return mode == "internal"


def require_active_subscription():
    """Guard Opsi G (Fase 28): satu status langganan per tenant, menggantikan
    lisensi per-SKU (`require_licensed_app`/`require_any_licensed_app`,
    dihapus sekaligus dalam cutover yang sama -- ADR-0007, tanpa masa
    transisi/grandfathering per keputusan PRD Fase 28).
    """

    def dependency(user=Depends(get_current_user), db: Session = Depends(get_db)):
        if _is_billing_bypass(db, user.tenant_id):
            return user
        if user.role == "platform_admin" or user.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun platform tidak memiliki akses ke data tenant",
            )
        from app.modules.billing.service import has_active_subscription

        if not has_active_subscription(db, user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant belum berlangganan. Pilih paket di halaman Pembayaran.",
            )

        # Safety-net: tutup cycle yang sudah lewat waktunya kalau scheduler
        # eksternal (POST /platform/internal/run-cycle-charge) terlewat --
        # korektnes penagihan periodik tidak boleh bergantung penuh pada
        # trigger di luar proses ini. No-op murah bila cycle masih berlaku.
        from app.modules.billing.cycle_close import close_cycle_for_tenant

        close_cycle_for_tenant(db, user.tenant_id)
        return user

    return dependency


def require_tenant_user():
    """Wajib akun bertenanta — memblokir platform_admin dari data bisnis."""

    def dependency(user=Depends(get_current_user)):
        if user.role == "platform_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun platform tidak memiliki akses ke data tenant",
            )
        return user

    return dependency
