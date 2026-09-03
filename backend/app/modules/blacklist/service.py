from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.audit import service as audit
from app.modules.auth.models import User
from app.modules.blacklist.models import BlacklistEntry, BlacklistStatus
from app.modules.blacklist.schemas import BlacklistEntryOut
from app.modules.recruitment.models import Candidate
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

# Status yang masih dianggap "aktif" -- kandidat dengan entri di salah satu
# status ini tidak boleh diajukan blacklist lagi (cegah duplikat menumpuk di
# antrean review). Kandidat yang permintaannya `rejected` BOLEH diajukan
# ulang -- itu bukan status aktif.
_ACTIVE_STATUSES = (BlacklistStatus.pending, BlacklistStatus.approved)


def _to_out(
    entry: BlacklistEntry,
    candidates: dict[UUID, Candidate],
    users: dict[UUID, User],
) -> BlacklistEntryOut:
    candidate = candidates.get(entry.candidate_id)
    requester = users.get(entry.requested_by) if entry.requested_by else None
    reviewer = users.get(entry.reviewed_by) if entry.reviewed_by else None
    return BlacklistEntryOut(
        id=entry.id,
        candidate_id=entry.candidate_id,
        candidate_name=candidate.full_name if candidate else "(kandidat terhapus)",
        reason=entry.reason,
        status=entry.status,
        requested_by=entry.requested_by,
        requested_by_name=requester.full_name if requester else None,
        requested_at=entry.requested_at,
        reviewed_by=entry.reviewed_by,
        reviewed_by_name=reviewer.full_name if reviewer else None,
        reviewed_at=entry.reviewed_at,
        review_notes=entry.review_notes,
    )


def _to_out_many(db: Session, entries: list[BlacklistEntry]) -> list[BlacklistEntryOut]:
    """Batch-fetch candidate/user sekali per kelompok, bukan 3 query per
    baris (N+1 -- temuan audit 2026-09-02, terasa begitu daftar blacklist
    membesar). `1 + 2` query total untuk berapa pun banyak `entries`."""
    candidate_ids = {e.candidate_id for e in entries}
    user_ids = {e.requested_by for e in entries if e.requested_by} | {
        e.reviewed_by for e in entries if e.reviewed_by
    }
    candidates = (
        {
            c.id: c
            for c in db.execute(select(Candidate).where(Candidate.id.in_(candidate_ids))).scalars()
        }
        if candidate_ids
        else {}
    )
    users = (
        {u.id: u for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars()}
        if user_ids
        else {}
    )
    return [_to_out(e, candidates, users) for e in entries]


def request_blacklist(
    db: Session, user: User, candidate_id: UUID, reason: str
) -> BlacklistEntryOut:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Kandidat tidak ditemukan")

    existing = db.execute(
        select(BlacklistEntry).where(
            BlacklistEntry.candidate_id == candidate_id,
            BlacklistEntry.status.in_(_ACTIVE_STATUSES),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Kandidat ini sudah punya permintaan blacklist yang aktif "
                "(menunggu review atau sudah disetujui)"
            ),
        )

    entry = BlacklistEntry(candidate_id=candidate_id, reason=reason, requested_by=user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    audit.log_event(
        db,
        action="blacklist.requested",
        entity_type="candidate",
        entity_id=candidate_id,
        detail={"blacklist_entry_id": str(entry.id), "reason": reason},
    )
    return _to_out_many(db, [entry])[0]


def list_entries(db: Session, status: BlacklistStatus | None = None) -> list[BlacklistEntryOut]:
    stmt = select(BlacklistEntry).order_by(BlacklistEntry.requested_at.desc())
    if status is not None:
        stmt = stmt.where(BlacklistEntry.status == status)
    entries = list(db.execute(stmt).scalars().all())
    return _to_out_many(db, entries)


def review_entry(
    db: Session,
    user: User,
    entry_id: UUID,
    decision: BlacklistStatus,
    notes: str | None,
) -> BlacklistEntryOut:
    if decision not in (BlacklistStatus.approved, BlacklistStatus.rejected):
        raise HTTPException(
            status_code=422, detail="Keputusan review harus 'disetujui' atau 'ditolak'"
        )

    entry = db.get(BlacklistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Permintaan blacklist tidak ditemukan")
    if entry.status != BlacklistStatus.pending:
        raise HTTPException(
            status_code=422, detail="Permintaan ini sudah pernah direview, tidak bisa diubah lagi"
        )

    entry.status = decision
    entry.reviewed_by = user.id
    entry.reviewed_at = datetime.now(UTC)
    entry.review_notes = notes
    db.commit()
    db.refresh(entry)

    audit.log_event(
        db,
        action=f"blacklist.{decision.name}",
        entity_type="candidate",
        entity_id=entry.candidate_id,
        detail={"blacklist_entry_id": str(entry.id), "notes": notes},
    )
    return _to_out_many(db, [entry])[0]
