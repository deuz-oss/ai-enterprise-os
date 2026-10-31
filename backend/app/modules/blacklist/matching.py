"""Pencocokan Blacklist sebagai blocking check (lanjutan Fase 29).

Dipisah dari `service.py` supaya modul lain (recruitment, talentpool, ai,
job_portal) bisa memakainya tanpa ikut menarik dependensi router/audit
modul blacklist -- modul ini HANYA bergantung pada model.

Aturan:
- Yang dihitung hanya entri berstatus `approved`. `pending`/`rejected`
  tidak berpengaruh (penanda reputasi tidak pernah final tanpa review).
  Model tidak punya kolom kedaluwarsa, jadi blacklist berlaku sampai ada
  mekanisme cabut (belum ada).
- Kandidat dianggap ter-blacklist bila `candidate_id`-nya punya entri
  approved, ATAU identitasnya (email/telepon/NIK, setelah dinormalisasi)
  sama dengan identitas kandidat yang ter-blacklist. Ini menutup celah
  pelamar portal yang membuat profil `Candidate` baru dengan email lain.
- Scoping tenant lewat filter otomatis `TenantMixin` -- query di sini
  sengaja TIDAK memakai opsi bypass apa pun. Pemanggil publik (job portal)
  wajib sudah `set_tenant(...)` sebelum memanggil `load_index`.

Daftar blacklist per tenant kecil, jadi pencocokan identitas dilakukan di
Python (satu query JOIN per request) dan tidak butuh kolom/index baru.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from app.modules.blacklist.models import BlacklistEntry, BlacklistStatus
from app.modules.recruitment.models import Candidate
from sqlalchemy import select
from sqlalchemy.orm import Session

BLACKLIST_BLOCK_DETAIL = (
    "Kandidat ini masuk daftar Blacklist (disetujui) dan tidak bisa diusulkan ke job order."
)

_NON_DIGIT = re.compile(r"\D")
# Nomor Indonesia terpendek yang masuk akal (mis. 0812345678 = 10 digit);
# di bawah 9 digit terlalu rawan bentrok antar-kandidat.
_MIN_PHONE_DIGITS = 9
_NIK_DIGITS = 16


def normalize_email(value: str | None) -> str | None:
    email = (value or "").strip().lower()
    return email or None


def normalize_phone(value: str | None) -> str | None:
    """`+62 812-3456-7890`, `62812...`, `0812...`, `812...` -> `0812...`."""
    digits = _NON_DIGIT.sub("", value or "")
    if digits.startswith("62"):
        digits = "0" + digits[2:]
    elif digits.startswith("8"):
        digits = "0" + digits
    return digits if len(digits) >= _MIN_PHONE_DIGITS else None


def normalize_nik(value: str | None) -> str | None:
    """NIK hanya dipakai bila tepat 16 digit; selain itu diabaikan."""
    digits = _NON_DIGIT.sub("", value or "")
    return digits if len(digits) == _NIK_DIGITS else None


@dataclass(frozen=True)
class BlacklistIndex:
    candidate_ids: frozenset[UUID] = field(default_factory=frozenset)
    emails: frozenset[str] = field(default_factory=frozenset)
    phones: frozenset[str] = field(default_factory=frozenset)
    niks: frozenset[str] = field(default_factory=frozenset)

    def match_reasons(self, candidate: Candidate) -> list[str]:
        """Dasar kecocokan (`candidate_id`/`email`/`phone`/`nik`) -- untuk
        audit internal. List kosong = tidak ter-blacklist."""
        reasons: list[str] = []
        if candidate.id in self.candidate_ids:
            reasons.append("candidate_id")
        email = normalize_email(candidate.email)
        if email and email in self.emails:
            reasons.append("email")
        phone = normalize_phone(candidate.phone)
        if phone and phone in self.phones:
            reasons.append("phone")
        nik = normalize_nik(candidate.ktp_no)
        if nik and nik in self.niks:
            reasons.append("nik")
        return reasons

    def matches(self, candidate: Candidate) -> bool:
        return bool(self.match_reasons(candidate))


def load_index(db: Session) -> BlacklistIndex:
    """Satu query: kandidat yang punya entri approved di tenant aktif."""
    rows = db.execute(
        select(Candidate)
        .join(BlacklistEntry, BlacklistEntry.candidate_id == Candidate.id)
        .where(BlacklistEntry.status == BlacklistStatus.approved)
    ).scalars()
    ids: set[UUID] = set()
    emails: set[str] = set()
    phones: set[str] = set()
    niks: set[str] = set()
    for cand in rows:
        ids.add(cand.id)
        if email := normalize_email(cand.email):
            emails.add(email)
        if phone := normalize_phone(cand.phone):
            phones.add(phone)
        if nik := normalize_nik(cand.ktp_no):
            niks.add(nik)
    return BlacklistIndex(
        candidate_ids=frozenset(ids),
        emails=frozenset(emails),
        phones=frozenset(phones),
        niks=frozenset(niks),
    )


def is_blacklisted(db: Session, candidate: Candidate) -> bool:
    return load_index(db).matches(candidate)


def blacklisted_ids(db: Session, candidates: list[Candidate]) -> set[UUID]:
    """ID kandidat (dari `candidates`) yang ter-blacklist -- untuk anotasi
    flag `is_blacklisted` di response daftar tanpa query per baris."""
    if not candidates:
        return set()
    index = load_index(db)
    return {c.id for c in candidates if index.matches(c)}
