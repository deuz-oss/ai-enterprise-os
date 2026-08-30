from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import RATES_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.rates import service
from app.modules.rates.schemas import (
    BankFeeCreate,
    BankFeeOut,
    BillingTaxConfigCreate,
    BillingTaxConfigOut,
    BpjsConfigCreate,
    BpjsConfigOut,
    Pph21ConfigCreate,
    Pph21ConfigOut,
)

router = APIRouter(prefix="/rates", tags=["rates"], dependencies=[Depends(get_current_user)])


# PPh21
@router.get("/pph21", response_model=list[Pph21ConfigOut])
def list_pph21(db: Session = Depends(get_db)):
    return service.list_pph21_configs(db)


@router.post(
    "/pph21",
    response_model=Pph21ConfigOut,
    status_code=201,
    dependencies=[Depends(require_roles(*RATES_ROLES))],
)  # noqa: E501
def create_pph21(payload: Pph21ConfigCreate, db: Session = Depends(get_db)):
    return service.create_pph21_config(db, payload)


# BPJS
@router.get("/bpjs", response_model=list[BpjsConfigOut])
def list_bpjs(db: Session = Depends(get_db)):
    return service.list_bpjs_configs(db)


@router.post(
    "/bpjs",
    response_model=BpjsConfigOut,
    status_code=201,
    dependencies=[Depends(require_roles(*RATES_ROLES))],
)  # noqa: E501
def create_bpjs(payload: BpjsConfigCreate, db: Session = Depends(get_db)):
    return service.create_bpjs_config(db, payload)


# Billing
@router.get("/billing", response_model=list[BillingTaxConfigOut])
def list_billing(db: Session = Depends(get_db)):
    return service.list_billing_configs(db)


@router.post(
    "/billing",
    response_model=BillingTaxConfigOut,
    status_code=201,
    dependencies=[Depends(require_roles(*RATES_ROLES))],
)  # noqa: E501
def create_billing(payload: BillingTaxConfigCreate, db: Session = Depends(get_db)):
    return service.create_billing_config(db, payload)


# Bank fees
@router.get("/bank-fees", response_model=list[BankFeeOut])
def list_bank_fees(db: Session = Depends(get_db)):
    return service.list_bank_fees(db)


@router.post(
    "/bank-fees",
    response_model=BankFeeOut,
    dependencies=[Depends(require_roles(*RATES_ROLES))],
)  # noqa: E501
def upsert_bank_fee(payload: BankFeeCreate, db: Session = Depends(get_db)):
    return service.upsert_bank_fee(db, payload)
