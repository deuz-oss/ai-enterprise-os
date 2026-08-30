"""Router modul transaksi Fase 10 lanjutan: Kas & Bank, Pembelian, Aset Tetap."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import ACCOUNTING_TRANSACTIONS_ROLES
from app.core.security import get_current_user, require_roles
from app.modules.accounting import transactions_service as tx_service
from app.modules.accounting.transactions_schemas import (
    BankTxCreate,
    FixedAssetCreate,
    FixedAssetOut,
    PurchaseBillCreate,
    PurchaseBillOut,
)

router = APIRouter(
    prefix="/accounting",
    tags=["accounting"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles(*ACCOUNTING_TRANSACTIONS_ROLES)),
    ],
)


def _serialize_asset(db, asset) -> dict:
    book = float(asset.cost) - float(asset.accumulated_depreciation)
    return {
        "id": str(asset.id),
        "name": asset.name,
        "acquisition_date": asset.acquisition_date,
        "cost": float(asset.cost),
        "useful_life_months": asset.useful_life_months,
        "accumulated_depreciation": float(asset.accumulated_depreciation),
        "monthly_depreciation": float(asset.monthly_depreciation),
        "book_value": round(book, 2),
        "last_depreciated_ym": asset.last_depreciated_ym,
        "disposed_at": asset.disposed_at,
    }


# ---------- Kas & Bank ----------


@router.get("/cashbank/transactions")
def list_bank_transactions(
    year: int = Query(...),
    month: int | None = Query(None, ge=1, le=12),
    reconciled: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    rows = tx_service.list_bank_transactions(db, year=year, month=month, reconciled=reconciled)
    return [
        {
            "id": str(t.id),
            "tx_date": t.tx_date.isoformat(),
            "tx_type": t.tx_type.value,
            "amount": float(t.amount),
            "description": t.description,
            "reconciled": t.reconciled_at is not None,
        }
        for t in rows
    ]


@router.post("/cashbank/transactions", status_code=201)
def create_bank_transaction(payload: BankTxCreate, db: Session = Depends(get_db)):
    tx = tx_service.create_bank_transaction(
        db,
        tx_type=payload.tx_type,
        bank_account_id=payload.bank_account_id,
        amount=payload.amount,
        tx_date=payload.tx_date,
        counter_account_id=payload.counter_account_id,
        description=payload.description,
    )
    return {"id": str(tx.id), "status": "created"}


@router.post("/cashbank/transactions/{tx_id}/reconcile")
def reconcile_bank_transaction(
    tx_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    tx = tx_service.reconcile_bank_transaction(db, user, tx_id)
    return {"id": str(tx.id), "reconciled": tx.reconciled_at is not None}


# ---------- Rekening koran & rekonsiliasi cerdas (PRD §8.8 #2) ----------

from fastapi import UploadFile  # noqa: E402

from app.modules.accounting import bank_statement  # noqa: E402
from app.modules.accounting.models import StatementLineStatus  # noqa: E402


@router.get("/cashbank/statement/template")
def statement_template():
    """Template CSV rekening koran (tanggal;keterangan;mutasi_masuk;mutasi_keluar)."""
    from fastapi import Response

    return Response(
        content=bank_statement.template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="template-rekening-koran.csv"'},
    )


@router.post("/cashbank/statement/import")
async def import_statement(file: UploadFile, db: Session = Depends(get_db)):
    """Impor mutasi rekening koran; matching fuzzy dihitung per baris."""
    return await bank_statement.import_statement(db, file)


@router.get("/cashbank/statement")
def list_statement(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    st = StatementLineStatus(status_filter) if status_filter else None
    return bank_statement.list_statement_lines(db, status=st)


@router.post("/cashbank/statement/{line_id}/match")
def confirm_statement_match(
    line_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    tx_id = str((payload or {}).get("bank_transaction_id") or "")
    return bank_statement.confirm_match(db, user=user, line_id=line_id, bank_transaction_id=tx_id)


@router.post("/cashbank/statement/{line_id}/ignore")
def ignore_statement_line(
    line_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return bank_statement.ignore_line(db, user=user, line_id=line_id)


# ---------- Pembelian ----------


@router.get("/purchases", response_model=list[PurchaseBillOut])
def list_purchases(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    from app.modules.accounting.models import BillStatus

    st = BillStatus(status_filter) if status_filter else None
    return tx_service.list_purchase_bills(db, status=st)
    return service_list_bills(db, st)


def service_list_bills(db, st):
    return tx_service.list_purchase_bills(db, status=st)


@router.post("/purchases", response_model=PurchaseBillOut, status_code=201)
def create_purchase(payload: PurchaseBillCreate, db: Session = Depends(get_db)):
    return tx_service.create_purchase_bill(db, payload)


@router.post("/purchases/{bill_id}/pay", response_model=PurchaseBillOut)
def pay_purchase(bill_id: str, payload: dict, db: Session = Depends(get_db)):
    return tx_service.pay_purchase_bill(
        db, bill_id=bill_id, bank_account_id=(payload or {}).get("bank_account_id")
    )


# ---------- Aset tetap ----------


@router.get("/assets", response_model=list[FixedAssetOut])
def list_assets(include_disposed: bool = Query(False), db: Session = Depends(get_db)):
    rows = tx_service.list_fixed_assets(db, include_disposed=include_disposed)
    return [_serialize_asset(db, a) for a in rows]


@router.post("/assets", response_model=FixedAssetOut, status_code=201)
def acquire_asset(payload: FixedAssetCreate, db: Session = Depends(get_db)):
    asset = tx_service.acquire_fixed_asset(db, payload)
    return _serialize_asset(db, asset)


@router.post("/assets/{asset_id}/depreciate")
def depreciate_asset(
    asset_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Catat penyusutan bulan tertentu (idempoten per bulan)."""
    year = int((payload or {}).get("year") or 0)
    month = int((payload or {}).get("month") or 0)
    if not year or not (1 <= month <= 12):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="year/month tidak valid")
    asset, dep, journal_id = tx_service.depreciate_asset_monthly(
        db, asset_id=asset_id, year=year, month=month
    )
    return {
        "id": str(asset.id),
        "ym": ym_label(year, month),
        "depreciation": dep,
        "accumulated": float(asset.accumulated_depreciation),
        "journal_entry_id": journal_id,
    }


def ym_label(year: int, month: int) -> str:
    return f"{year}-{str(month).zfill(2)}"


@router.post("/assets/{asset_id}/dispose")
def dispose_asset(asset_id: str, payload: dict, db: Session = Depends(get_db)):
    asset = tx_service.dispose_fixed_asset(
        db,
        asset_id=asset_id,
        proceeds=float((payload or {}).get("proceeds") or 0),
    )
    return {
        "id": str(asset.id),
        "disposed_at": asset.disposed_at,
        "disposal_proceeds": float(asset.disposal_proceeds),
    }


# ---------- Arus kas tidak langsung ----------


@router.get("/reports/cash-flow-indirect")
def cash_flow_indirect(year: int = Query(...), db: Session = Depends(get_db)):
    """Arus kas metode tidak langsung dari perubahan saldo grup akun."""
    return tx_service.cash_flow_indirect(db, year=year)
