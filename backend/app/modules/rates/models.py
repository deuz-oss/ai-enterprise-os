"""Rate/config ber-versi untuk pajak, BPJS, billing, dan bank fee.

Semua rate disimpan terpisah dari kode agar regulasi dapat diperbarui
tanpa deploy. Setiap tabel memiliki kolom effective_from yang menandai
berlakunya versi tersebut. Payroll/billing mengambil versi efektif
berdasarkan periode, dan snapshot dicatat di PayrollRun agar historis
konsisten (NFR §11).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Pph21Config(Base):
    """Versi tarif PPh21 (PTKP, Pasal 17, dan TER)."""

    __tablename__ = "pph21_configs"
    __table_args__ = (UniqueConstraint("effective_from", name="uq_pph21_effective"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ptkp_diri: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    ptkp_kawin: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    ptkp_tanggungan: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    max_tanggungan: Mapped[int] = mapped_column(default=3)
    pasal17_brackets: Mapped[Any] = mapped_column(JSON, nullable=False)
    ter_a: Mapped[Any] = mapped_column(JSON, nullable=False)
    ter_b: Mapped[Any] = mapped_column(JSON, nullable=False)
    ter_c: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BpjsConfig(Base):
    """Versi tarif BPJS Kesehatan & Ketenagakerjaan."""

    __tablename__ = "bpjs_configs"
    __table_args__ = (UniqueConstraint("effective_from", name="uq_bpjs_effective"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kesehatan_employer: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    kesehatan_employee: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    kesehatan_cap: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    jht_employer: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    jht_employee: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    jp_employer: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    jp_employee: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    jp_cap: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    jkm_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    jkk_rates: Mapped[Any] = mapped_column(JSON, nullable=False)
    default_jkk_category: Mapped[int] = mapped_column(default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingTaxConfig(Base):
    """Versi tarif billing (PPN, PPh23, jatuh tempo)."""

    __tablename__ = "billing_tax_configs"
    __table_args__ = (UniqueConstraint("effective_from", name="uq_billing_effective"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ppn_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    pph23_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    due_days: Mapped[int] = mapped_column(default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankFeeConfig(Base):
    """Biaya admin bank per nama bank (mis. non-Mandiri Rp 3.500)."""

    __tablename__ = "bank_fee_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    bank_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    fee: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=3500)
    is_mandiri_group: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )  # noqa: E501
