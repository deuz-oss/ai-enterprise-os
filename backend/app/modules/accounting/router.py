from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import ACCOUNTING_ROLES
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
    dependencies=[Depends(get_current_user), Depends(require_roles(*ACCOUNTING_ROLES))],
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


# ---------- Fase 10: AI Layer Akuntansi (PRD §8.8) ----------

from app.modules.accounting import ai_accounting  # noqa: E402


@router.get("/ai/close-checklist")
def close_checklist(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Asisten tutup buku — checklist deterministik tanpa LLM."""
    return ai_accounting.close_checklist(db, year=year, month=month)


@router.get("/ai/anomalies")
def detect_anomalies(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Deteksi anomali & kepatuhan: duplikasi bill, transaksi besar, sanity PPN."""
    return ai_accounting.detect_anomalies(db, year=year, month=month)


@router.get("/ai/executive-summary")
def executive_summary(
    year: int = Query(...),
    month: int | None = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Narasi eksekutif otomatis dari data terverifikasi (LLM opsional)."""
    return ai_accounting.executive_summary(db, year=year, month=month)


@router.post("/ai/categorize-bill")
def categorize_bill(payload: dict, db: Session = Depends(get_db)):
    """Saran COA untuk bill baru berdasarkan riwayat & keyword."""
    vendor = str((payload or {}).get("vendor_name") or "")
    if not vendor.strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="vendor_name wajib diisi")
    return ai_accounting.suggest_bill_category(
        db, vendor_name=vendor, description=(payload or {}).get("description")
    )


@router.post("/ai/ask")
def ask_report(payload: dict, db: Session = Depends(get_db)):
    """Tanya laporan — jawaban berbasis pre-computed data terverifikasi."""
    question = str((payload or {}).get("question") or "").strip()
    if not question:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Pertanyaan wajib diisi")
    year = (payload or {}).get("year")
    return ai_accounting.ask_report(db, question=question, year=int(year) if year else None)


@router.post("/ai/ocr-bill")
async def ocr_bill(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Foto faktur/nota → draft pembelian + saran COA (satu panggilan vision LLM)."""
    import base64

    mime = (file.content_type or "").lower()
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Ukuran file maksimal 8 MB")
    return ai_accounting.ocr_extract_bill(
        db, image_b64=base64.b64encode(raw).decode(), mime_type=mime
    )


@router.get("/ai/payment-prediction")
def payment_prediction(db: Session = Depends(get_db)):
    """Skor risiko telat bayar per klien + prioritas collection (deterministik)."""
    return ai_accounting.predict_client_payments(db)
