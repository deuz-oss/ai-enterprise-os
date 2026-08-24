from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db, parse_uuid
from app.core.ratelimit import get_limiter
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
)
from app.core.tenancy import get_request_meta
from app.modules import audit
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ChangePasswordIn,
    LoginRequest,
    PasswordResetIn,
    PasswordResetIssueOut,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.modules.auth.service import (
    authenticate,
    change_own_password,
    consume_password_reset_token,
    create_user,
    issue_password_reset_token,
)

admin_only = require_roles()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    """Membuat akun baru. Hanya admin — akun tim dikelola lewat menu Pengguna."""
    return create_user(db, payload)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    from app.modules.auth.service import get_by_email

    settings = get_settings()
    ip, _ = get_request_meta()
    limiter = get_limiter("login")
    window_sec = settings.login_rate_limit_window_sec
    # Dua kunci sekaligus: kombinasi IP|email DAN global per-IP,
    # agar rotasi email tidak membebani percobaan brute force.
    keys = [f"{ip}|{payload.email.lower()}", f"ip:{ip}"]
    retry_after_max = 0
    for key in keys:
        allowed, retry_after = limiter.check(
            key, max_attempts=settings.login_rate_limit_max, window_seconds=window_sec
        )
        if not allowed:
            retry_after_max = max(retry_after_max, retry_after)
    if retry_after_max:
        # Sama seperti login_failed: hanya percobaan ke email yang terdaftar
        # yang dicatat pada tenant pemilik akun (event pra-auth tanpa konteks).
        known = get_by_email(db, payload.email.lower())
        if known is not None:
            audit.log_event(
                db,
                action="auth.login_ratelimited",
                entity_type="user",
                entity_id=known.id,
                actor=known.id,
                tenant_id=known.tenant_id,
                detail={"email": payload.email.lower(), "ip": ip},
            )
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan login. Coba lagi nanti.",
            headers={"Retry-After": str(retry_after_max)},
        )

    user = authenticate(db, payload.email.lower(), payload.password)
    if user is None:
        for key in keys:
            limiter.hit(key, window_seconds=window_sec)
        # Percobaan ke email yang terdaftar dicatat pada tenant pemilik akun
        # agar terlihat oleh admin tenant; email tak dikenal tetap anonim.
        known = get_by_email(db, payload.email.lower())
        audit.log_event(
            db,
            action="auth.login_failed",
            entity_type="user" if known else None,
            entity_id=known.id if known else None,
            actor=known.id if known else None,
            tenant_id=known.tenant_id if known else None,
            detail={"email": payload.email.lower()},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email atau password salah"
        )

    limiter.clear(keys[0])
    limiter.clear(keys[1])
    # Tolak akun dari tenant yang ditangguhkan (cek langsung tanpa konteks).
    if user.tenant_id is not None:
        from app.modules.platform.models import Tenant, TenantStatus

        stmt = select(Tenant).where(Tenant.id == user.tenant_id).execution_options(
            include_with_loader_criteria=False
        )
        tenant = db.execute(stmt).scalar_one_or_none()
        if tenant is None or tenant.status != TenantStatus.active:
            raise HTTPException(status_code=403, detail="Tenant sedang ditangguhkan")
    audit.log_event(
        db,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        detail={"role": user.role.value},
        actor=user.id,
        tenant_id=user.tenant_id,
    )
    return Token(
        access_token=create_access_token(str(user.id), tenant_id=user.tenant_id),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User aktif mengganti password sendiri (wajib password lama)."""
    change_own_password(db, current_user, payload.old_password, payload.new_password)
    audit.log_event(
        db,
        action="auth.password_changed",
        entity_type="user",
        entity_id=current_user.id,
        actor=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return Response(status_code=204)


@router.post("/users/{user_id}/password-reset-token", response_model=PasswordResetIssueOut)
def issue_reset_token(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    """Admin membuat token reset satu kali pakai untuk anggota tenant-nya.

    Tanpa SMTP di v1: token dikembalikan ke admin untuk diteruskan ke user
    lewat kanal lain (mis. WhatsApp).
    """
    user = db.get(User, parse_uuid(user_id))
    if user is not None and user.tenant_id != admin.tenant_id:
        user = None  # lintas tenant: perlakukan sebagai tidak ada
    if user is None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    raw = issue_password_reset_token(db, user)
    audit.log_event(
        db,
        action="auth.password_reset_requested",
        entity_type="user",
        entity_id=user.id,
        actor=admin.id,
        tenant_id=admin.tenant_id,
        detail={"target_email": user.email},
    )
    return PasswordResetIssueOut(
        reset_token=raw, expires_in_minutes=get_settings().password_reset_ttl_min
    )


@router.post("/reset-password", response_model=UserOut)
def reset_password(payload: PasswordResetIn, db: Session = Depends(get_db)):
    """Endpoint publik: tukar token reset dengan password baru."""
    settings = get_settings()
    ip, _ = get_request_meta()
    limiter = get_limiter("password_reset")
    key = f"ip:{ip}"
    allowed, retry_after = limiter.check(
        key,
        max_attempts=settings.reset_rate_limit_max,
        window_seconds=settings.login_rate_limit_window_sec,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan. Coba lagi nanti.",
            headers={"Retry-After": str(retry_after)},
        )
    limiter.hit(key, window_seconds=settings.login_rate_limit_window_sec)

    user = consume_password_reset_token(db, payload.token, payload.new_password)
    audit.log_event(
        db,
        action="auth.password_reset_completed",
        entity_type="user",
        entity_id=user.id,
        actor=user.id,
        tenant_id=user.tenant_id,
    )
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return list(db.execute(select(User).order_by(User.created_at)).scalars())


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    user = db.get(User, parse_uuid(user_id))
    if user is not None and user.tenant_id != admin.tenant_id:
        user = None  # lintas tenant: perlakukan sebagai tidak ada
    if user is None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    data = payload.model_dump(exclude_unset=True)

    if user.id == admin.id and data.get("is_active") is False:
        raise HTTPException(status_code=422, detail="Tidak bisa menonaktifkan akun sendiri")
    if user.id == admin.id and "role" in data and data["role"] != user.role:
        raise HTTPException(status_code=422, detail="Tidak bisa mengubah role akun sendiri")

    new_password = data.pop("new_password", None)
    for field, value in data.items():
        setattr(user, field, value)
    if new_password:
        if len(new_password) < 8:
            raise HTTPException(status_code=422, detail="Password minimal 8 karakter")
        user.hashed_password = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user
