"""Service untuk mengelola rate ber-versi."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.rates.models import BankFeeConfig, BillingTaxConfig, BpjsConfig, Pph21Config

# ---------- Generic helpers ----------

def _get_effective(db: Session, model, effective_date: date):
    """Ambil versi efektif terbaru <= effective_date, atau None."""
    return db.execute(
        select(model).where(model.effective_from <= effective_date).order_by(model.effective_from.desc())  # noqa: E501
    ).scalars().first()


def _check_duplicate(db: Session, model, effective_from: date):
    exists = db.execute(select(model).where(model.effective_from == effective_from)).scalars().first()  # noqa: E501
    if exists:
        raise HTTPException(status_code=409, detail=f"Versi untuk tanggal {effective_from} sudah ada")  # noqa: E501


# ---------- PPh21 ----------

def list_pph21_configs(db: Session) -> list[Pph21Config]:
    return list(db.execute(select(Pph21Config).order_by(Pph21Config.effective_from.desc())).scalars().all())  # noqa: E501


def get_effective_pph21(db: Session, effective_date: date) -> Pph21Config | None:
    return _get_effective(db, Pph21Config, effective_date)


def create_pph21_config(db: Session, payload) -> Pph21Config:
    _check_duplicate(db, Pph21Config, payload.effective_from)
    obj = Pph21Config(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ---------- BPJS ----------

def list_bpjs_configs(db: Session) -> list[BpjsConfig]:
    return list(db.execute(select(BpjsConfig).order_by(BpjsConfig.effective_from.desc())).scalars().all())  # noqa: E501


def get_effective_bpjs(db: Session, effective_date: date) -> BpjsConfig | None:
    return _get_effective(db, BpjsConfig, effective_date)


def create_bpjs_config(db: Session, payload) -> BpjsConfig:
    _check_duplicate(db, BpjsConfig, payload.effective_from)
    obj = BpjsConfig(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ---------- Billing ----------

def list_billing_configs(db: Session) -> list[BillingTaxConfig]:
    return list(db.execute(select(BillingTaxConfig).order_by(BillingTaxConfig.effective_from.desc())).scalars().all())  # noqa: E501


def get_effective_billing(db: Session, effective_date: date) -> BillingTaxConfig | None:
    return _get_effective(db, BillingTaxConfig, effective_date)


def create_billing_config(db: Session, payload) -> BillingTaxConfig:
    _check_duplicate(db, BillingTaxConfig, payload.effective_from)
    obj = BillingTaxConfig(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ---------- Bank fees ----------

def list_bank_fees(db: Session) -> list[BankFeeConfig]:
    return list(db.execute(select(BankFeeConfig).order_by(BankFeeConfig.bank_name)).scalars().all())


def upsert_bank_fee(db: Session, payload) -> BankFeeConfig:
    existing = db.execute(select(BankFeeConfig).where(BankFeeConfig.bank_name == payload.bank_name)).scalars().first()  # noqa: E501
    if existing:
        existing.fee = payload.fee
        existing.is_mandiri_group = payload.is_mandiri_group
        db.commit()
        db.refresh(existing)
        return existing
    obj = BankFeeConfig(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_bank_fee(db: Session, bank_name: str) -> float:
    """Return fee for bank, fallback 3500 for non-mandiri, 0 for mandiri group."""
    if not bank_name:
        return 0
    row = db.execute(select(BankFeeConfig).where(BankFeeConfig.bank_name == bank_name)).scalars().first()  # noqa: E501
    if row:
        return float(row.fee)
    # fallback: check if mandiri group
    normalized = bank_name.strip().lower()
    if "mandiri" in normalized:
        return 0
    # check generic non-mandiri config
    return 3500
