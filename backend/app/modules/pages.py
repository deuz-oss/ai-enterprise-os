"""Modul Halaman (page tree hierarkis untuk workspace) — pelengkap shell Fase 7.

Halaman buatan pengguna: hierarki parent/child, emoji, konten teks.
Gratis untuk seluruh staf tenant; karyawan outsourcing tidak mendapat akses.
"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import ForeignKey, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base, get_db, parse_uuid
from app.core.security import get_current_user
from app.core.tenancy import TenantMixin


class WorkspacePage(TenantMixin, Base):
    """Satu halaman workspace; hierarki via parent_id."""

    __tablename__ = "workspace_pages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspace_pages.id"), default=None, index=True
    )
    title: Mapped[str] = mapped_column(Text, default="Tanpa judul")
    icon: Mapped[str] = mapped_column(Text, default="📄")
    content: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


# TEMUAN AUDIT RBAC (belum diperbaiki, sengaja dibiarkan sampai dikonfirmasi
# Brian): docstring modul di atas bilang "karyawan outsourcing tidak
# mendapat akses", tapi router ini TIDAK punya require_roles(...) apa pun,
# cuma get_current_user per-endpoint — jadi role "karyawan" tidak benar-benar
# ditolak backend, cuma disembunyikan dari sidebar frontend
# (KARYAWAN_ALLOWED_PATHS di Layout.tsx). Kalau proteksi role memang
# dimaksud, tambahkan require_roles(...) di sini; kalau kebijakannya sudah
# berubah (semua staf boleh), update docstring di atas.
router = APIRouter(prefix="/pages", tags=["pages"])


def _assert_staff(user) -> None:
    from app.modules.chat.service import STAFF_ROLES

    if getattr(user.role, "value", user.role) not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Halaman hanya untuk staf internal")


def _staff(user) -> bool:
    from app.modules.chat.service import STAFF_ROLES

    return getattr(user.role, "value", user.role) in STAFF_ROLES


def _get_page(db: Session, page_id: str) -> WorkspacePage:
    page = db.get(WorkspacePage, parse_uuid(page_id))
    if page is None:
        raise HTTPException(status_code=404, detail="Halaman tidak ditemukan")
    return page


def _serialize(page: WorkspacePage, *, with_content: bool = True) -> dict:
    data: dict = {
        "id": str(page.id),
        "parent_id": str(page.parent_id) if page.parent_id else None,
        "title": page.title,
        "icon": page.icon,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }
    if with_content:
        data["content"] = page.content
    return data


@router.get("")
def list_pages(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Daftar halaman tenant untuk sidebar page tree."""
    rows = (
        db.execute(select(WorkspacePage).order_by(WorkspacePage.created_at.desc())).scalars().all()
    )
    return [_serialize(p, with_content=False) for p in rows]


@router.post("", status_code=201)
def create_page(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _assert_staff(user)
    parent_id = payload.get("parent_id") or None
    if parent_id is not None:
        _get_page(db, str(parent_id))  # induk wajib ada
    page = WorkspacePage(
        parent_id=parse_uuid(str(parent_id)) if parent_id else None,
        title=str(payload.get("title") or "").strip()[:255] or "Tanpa judul",
        icon=str(payload.get("icon") or "📄")[:10],
        content=str(payload.get("content") or "")[:100_000],
        created_by_id=parse_uuid(str(user.id)),
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return _serialize(page)


@router.get("/{page_id}")
def get_page(page_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _serialize(_get_page(db, page_id))


@router.patch("/{page_id}")
def update_page(
    page_id: str, payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    _assert_staff(user)
    page = _get_page(db, page_id)
    if "title" in payload:
        page.title = str(payload.get("title") or "").strip()[:255] or "Tanpa judul"
    if "icon" in payload:
        page.icon = str(payload.get("icon") or "📄")[:10]
    if "content" in payload:
        page.content = str(payload.get("content") or "")[:100_000]
    if "parent_id" in payload:
        new_parent = payload.get("parent_id") or None
        if new_parent is not None:
            if str(new_parent) == str(page.id):
                raise HTTPException(
                    status_code=422, detail="Halaman tidak bisa jadi induknya sendiri"
                )
            parent = _get_page(db, str(new_parent))
            # Cegah siklus: induk baru tidak boleh berada di sub-halaman ini.
            cursor: WorkspacePage | None = parent
            while cursor is not None:
                if cursor.id == page.id:
                    raise HTTPException(
                        status_code=422,
                        detail="Tidak bisa memindah ke dalam sub-halamannya sendiri",
                    )
                cursor = (
                    db.get(WorkspacePage, cursor.parent_id)
                    if cursor.parent_id is not None
                    else None
                )
            page.parent_id = parse_uuid(str(new_parent))
        else:
            page.parent_id = None
    db.commit()
    db.refresh(page)
    return _serialize(page)


@router.delete("/{page_id}")
def delete_page(page_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Hapus halaman beserta seluruh sub-halamannya."""
    _assert_staff(user)
    page = _get_page(db, page_id)
    to_delete: list[WorkspacePage] = [page]
    frontier = [page.id]
    while frontier:
        children = (
            db.execute(select(WorkspacePage).where(WorkspacePage.parent_id.in_(frontier)))
            .scalars()
            .all()
        )
        frontier = [c.id for c in children]
        to_delete.extend(children)
    removed = len(to_delete)
    for p in to_delete:
        db.delete(p)
    db.commit()
    return {"deleted": removed}
