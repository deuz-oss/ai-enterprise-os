from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounting.accounts import ACCOUNTS, INCOME_CATEGORIES, get_account
from app.modules.accounting.models import JournalEntry, JournalLine
from app.modules.accounting.schemas import (
    BalanceSheet,
    BalanceSheetSection,
    IncomeStatement,
    IncomeStatementRow,
    JournalEntryIn,
    TrialBalanceRow,
)


def create_entry(db: Session, payload: JournalEntryIn) -> JournalEntry:
    for line in payload.lines:
        if get_account(line.account_code) is None:
            raise HTTPException(
                status_code=422,
                detail=f"Kode akun tidak dikenal: {line.account_code}",
            )
    entry = JournalEntry(
        entry_date=payload.entry_date or date.today(),
        description=payload.description,
        reference=payload.reference,
    )
    entry.lines = [
        JournalLine(account_code=line.account_code, debit=line.debit, credit=line.credit)
        for line in payload.lines
    ]
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_entries(
    db: Session, year: int | None = None, month: int | None = None
) -> list[JournalEntry]:
    stmt = select(JournalEntry).order_by(JournalEntry.entry_date.desc())
    if year is not None:
        stmt = stmt.where(func.extract("year", JournalEntry.entry_date) == year)
    if month is not None:
        stmt = stmt.where(func.extract("month", JournalEntry.entry_date) == month)
    return list(db.execute(stmt).unique().scalars())


def _account_totals(db: Session, until: str) -> dict[str, tuple[float, float]]:
    """Total debit & kredit per akun sampai akhir periode (YYYY-MM-DD)."""
    stmt = (
        select(
            JournalLine.account_code,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalEntry.entry_date <= until)
        .group_by(JournalLine.account_code)
    )
    totals: dict[str, tuple[float, float]] = {}
    for code, debit, credit in db.execute(stmt).all():
        totals[code] = (float(debit), float(credit))
    # Sertakan semua akun di chart of accounts meski belum ada mutasi.
    for code in ACCOUNTS:
        totals.setdefault(code, (0.0, 0.0))
    return totals


def trial_balance(db: Session, year: int) -> list[TrialBalanceRow]:
    end = f"{year}-12-31"
    totals = _account_totals(db, end)
    rows = []
    for code in sorted(ACCOUNTS):
        account = ACCOUNTS[code]
        debit, credit = totals[code]
        rows.append(
            TrialBalanceRow(
                account_code=code,
                account_name=account.name,
                category=account.category,
                total_debit=debit,
                total_credit=credit,
            )
        )
    return rows


def ledger(db: Session, account_code: str, year: int):
    account = get_account(account_code)
    if account is None:
        raise HTTPException(status_code=404, detail="Kode akun tidak dikenal")
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_code == account_code)
        .where(JournalEntry.entry_date >= start)
        .where(JournalEntry.entry_date <= end)
        .order_by(JournalEntry.entry_date, JournalEntry.created_at)
    )
    lines = []
    balance = 0.0
    normal_debit = account.category in ("aset", "beban")
    for line, entry in db.execute(stmt).unique().all():
        delta = (
            float(line.debit) - float(line.credit)
            if normal_debit
            else float(line.credit) - float(line.debit)
        )
        balance += delta
        lines.append(
            {
                "entry_id": str(entry.id),
                "entry_date": entry.entry_date.isoformat(),
                "description": entry.description,
                "reference": entry.reference,
                "debit": float(line.debit),
                "credit": float(line.credit),
                "balance": round(balance, 2),
            }
        )
    return {"account": account.code, "account_name": account.name, "year": year, "lines": lines}


def income_statement(db: Session, year: int) -> IncomeStatement:
    end = f"{year}-12-31"
    totals = _account_totals(db, end)
    revenues: list[IncomeStatementRow] = []
    expenses: list[IncomeStatementRow] = []
    for code in sorted(ACCOUNTS):
        account = ACCOUNTS[code]
        debit, credit = totals[code]
        if account.category not in INCOME_CATEGORIES:
            continue
        amount = credit - debit if account.category == "pendapatan" else debit - credit
        row = IncomeStatementRow(
            account_code=code, account_name=account.name, amount=round(amount, 2)
        )
        if account.category == "pendapatan":
            revenues.append(row)
        else:
            expenses.append(row)
    total_revenue = round(sum(r.amount for r in revenues), 2)
    total_expense = round(sum(r.amount for r in expenses), 2)
    return IncomeStatement(
        year=year,
        revenues=revenues,
        expenses=expenses,
        total_revenue=total_revenue,
        total_expense=total_expense,
        net_income=round(total_revenue - total_expense, 2),
    )


def balance_sheet(db: Session, as_of: str) -> BalanceSheet:
    totals = _account_totals(db, as_of)

    def section(category: str) -> BalanceSheetSection:
        rows = []
        total = 0.0
        for code in sorted(ACCOUNTS):
            account = ACCOUNTS[code]
            if account.category != category:
                continue
            debit, credit = totals[code]
            amount = round(debit - credit, 2) if category == "aset" else round(credit - debit, 2)
            rows.append(
                IncomeStatementRow(
                    account_code=code, account_name=account.name, amount=amount
                )
            )
            total += amount
        return BalanceSheetSection(rows=rows, total=round(total, 2))

    assets = section("aset")
    liabilities = section("kewajiban")
    equity = section("ekuitas")

    # Laba berjalan (pendapatan - beban) menambah ekuitas.
    net = 0.0
    for code in ACCOUNTS:
        account = ACCOUNTS[code]
        if account.category not in INCOME_CATEGORIES:
            continue
        debit, credit = totals[code]
        net += credit - debit if account.category == "pendapatan" else debit - credit
    net_income = round(net, 2)
    equity.total = round(equity.total + net_income, 2)

    return BalanceSheet(
        as_of=date.fromisoformat(as_of),
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        net_income=net_income,
    )
