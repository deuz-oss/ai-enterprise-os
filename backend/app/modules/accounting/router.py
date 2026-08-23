from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.modules.accounting import service
from app.modules.accounting.schemas import (
    BalanceSheet,
    IncomeStatement,
    JournalEntryIn,
    JournalEntryOut,
    TrialBalanceRow,
)

router = APIRouter(
    prefix="/accounting",
    tags=["accounting"],
    dependencies=[Depends(get_current_user), Depends(require_roles("finance", "management"))],
)


@router.get("/accounts")
def list_accounts():
    """Chart of accounts (bagian akun) aktif."""
    from app.modules.accounting.accounts import ACCOUNTS

    return [
        {"code": a.code, "name": a.name, "category": a.category}
        for a in sorted(ACCOUNTS.values(), key=lambda x: x.code)
    ]


@router.get("/journal", response_model=list[JournalEntryOut])
def list_entries(
    year: int | None = Query(None), month: int | None = Query(None), db: Session = Depends(get_db)
):
    return service.list_entries(db, year=year, month=month)


@router.post("/journal", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(payload: JournalEntryIn, db: Session = Depends(get_db)):
    """Catat jurnal umum; total debit wajib = total kredit."""
    return service.create_entry(db, payload)


@router.get("/ledger/{account_code}")
def ledger(
    account_code: str, year: int = Query(...), db: Session = Depends(get_db)
):
    """Buku besar satu akun dengan saldo berjalan."""
    return service.ledger(db, account_code, year=year)


@router.get("/trial-balance", response_model=list[TrialBalanceRow])
def trial_balance(year: int = Query(...), db: Session = Depends(get_db)):
    return service.trial_balance(db, year=year)


@router.get("/reports/income-statement", response_model=IncomeStatement)
def income_statement(year: int = Query(...), db: Session = Depends(get_db)):
    return service.income_statement(db, year=year)


@router.get("/reports/balance-sheet", response_model=BalanceSheet)
def balance_sheet(
    as_of: str = Query(..., description="Format YYYY-MM-DD"), db: Session = Depends(get_db)
):
    return service.balance_sheet(db, as_of=as_of)
