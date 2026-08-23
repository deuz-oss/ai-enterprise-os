from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db, parse_uuid
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.modules.auth.service import authenticate, create_user

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
    user = authenticate(db, payload.email.lower(), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email atau password salah"
        )
    return Token(access_token=create_access_token(str(user.id)), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


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
