from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.modules.accounting import service
from app.modules.accounting.models import JournalEntryStatus
from app.modules.accounting.schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    BalanceSheet,
    IncomeStatement,
    JournalEntryIn,
    JournalEntryOut,
    PeriodOut,
    TrialBalanceRow,
)

router = APIRouter(
    prefix="/accounting",
    tags=["accounting"],
    dependencies=[Depends(get_current_user), Depends(require_roles("finance", "management"))],
)


# ---------- Bagan akun dinamis (PRD §8.1) ----------


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(include_inactive: bool = Query(False), db: Session = Depends(get_db)):
    return service.list_accounts(db, include_inactive=include_inactive)


@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    return service.create_account(db, payload)


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: str, payload: AccountUpdate, db: Session = Depends(get_db)):
    return service.update_account(db, account_id, payload)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: str, db: Session = Depends(get_db)):
    service.delete_account(db, account_id)


# ---------- Periode & tutup buku (PRD §8.5) ----------


@router.get("/periods", response_model=list[PeriodOut])
def list_periods(db: Session = Depends(get_db)):
    return service.list_periods(db)


@router.post("/periods/{year}/{month}/close", response_model=PeriodOut)
def close_period(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.close_period(db, user, year, month)


@router.post("/periods/{year}/{month}/reopen")
def reopen_period(
    year: int, month: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    service.reopen_period(db, user, year, month)
    return {"status": "open", "period": f"{month}/{year}"}


# ---------- Jurnal umum & memorial ----------


@router.get("/journal", response_model=list[JournalEntryOut])
def list_entries(
    year: int | None = Query(None),
    month: int | None = Query(None),
    status_filter: JournalEntryStatus | None = Query(None, alias="status"),
    event_code: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return service.list_entries(
        db, year=year, month=month, status=status_filter, event_code=event_code
    )


@router.post("/journal", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(payload: JournalEntryIn, db: Session = Depends(get_db)):
    """Catat jurnal; default langsung posted. status=memorial untuk alur dua langkah."""
    return service.create_entry(db, payload)


@router.post("/journal/{entry_id}/post", response_model=JournalEntryOut)
def post_entry(entry_id: str, db: Session = Depends(get_db)):
    """Posting jurnal memorial: validasi seimbang, periode open, akun aktif."""
    return service.post_entry(db, entry_id)


# ---------- Laporan ----------


@router.get("/ledger/{account_code}")
def ledger(account_code: str, year: int = Query(...), db: Session = Depends(get_db)):
    """Buku besar satu akun dengan saldo berjalan (hanya jurnal posted)."""
    return service.ledger(db, account_code, year=year)


@router.get("/trial-balance", response_model=list[TrialBalanceRow])
def trial_balance(year: int = Query(...), db: Session = Depends(get_db)):
    return service.trial_balance(db, year=year)


@router.get("/reports/income-statement", response_model=IncomeStatement)
def income_statement(
    year: int = Query(...),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    return service.income_statement(db, year=year, month=month)


@router.get("/reports/balance-sheet", response_model=BalanceSheet)
def balance_sheet(
    as_of: str = Query(..., description="Format YYYY-MM-DD"), db: Session = Depends(get_db)
):
    return service.balance_sheet(db, as_of=as_of)


@router.get("/reports/profit-by-client")
def profit_by_client(
    year: int = Query(...),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Laba rugi per kontrak klien dari dimensi baris jurnal (PRD §8.6)."""
    return service.profit_by_client(db, year=year, month=month)
