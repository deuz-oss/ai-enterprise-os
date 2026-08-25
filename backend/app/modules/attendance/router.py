from fastapi import APIRouter, Depends, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.modules.attendance import service
from app.modules.attendance.schemas import AttendanceRecordIn, AttendanceRecordOut

router = APIRouter(
    prefix="/attendance",
    tags=["attendance"],
)


@router.get("/template")
def download_template():
    """Template CSV impor mesin fingerprint (delimiter ;)."""
    return Response(
        content=service.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="template-absensi.csv"'},
    )


@router.get("/records", response_model=list[AttendanceRecordOut])
def list_records(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    employee_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return service.list_records(db, year=year, month=month, employee_id=employee_id)


@router.post("/records", response_model=AttendanceRecordOut, status_code=201)
def upsert_record(
    payload: AttendanceRecordIn,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Input/update manual satu hari; agregasi bulanan dihitung ulang otomatis."""
    record, _inserted = service.upsert_record(db, payload)
    return record


@router.post("/import", response_model=dict)
async def import_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Impor CSV fingerprint; kembalikan jumlah sukses + daftar baris gagal."""
    result = await service.import_csv(db, file)
    return {
        "inserted": result.inserted,
        "updated": result.updated,
        "failed": [f.model_dump() for f in result.failed],
    }


@router.post("/summaries/{summary_id}/validate")
def validate_summary(
    summary_id: str,
    lane: str = Query(..., pattern="^(hr|klien)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Validasi dua jalur rekap bulanan: `hr` (internal) atau `klien` (eksternal)."""
    summary = service.validate_summary(db, user, summary_id, lane)
    return {
        "id": str(summary.id),
        "client_approved": summary.client_approved,
        "approved_at": summary.approved_at,
    }
