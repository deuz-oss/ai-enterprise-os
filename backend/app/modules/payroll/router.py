from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import PAYROLL_ROLES
from app.core.ratelimit import get_limiter
from app.core.security import get_current_user, require_any_licensed_app, require_roles
from app.core.tenancy import get_request_meta
from app.modules.payroll import service
from app.modules.payroll.schemas import (
    AttendanceOut,
    AttendanceUpsert,
    ClientDecisionIn,
    ClientLinkCreate,
    GenerateSlipsRequest,
    PayslipOut,
    RunCreate,
    RunOut,
    TaxPreviewIn,
)

# Shell OR (ADR-0006): cukup salah satu lisensi untuk masuk modul;
# mutasi run divalidasi per run_type di service (assert lisensi per objek).
router = APIRouter(
    prefix="/payroll",
    tags=["payroll"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_any_licensed_app("hr_payroll", "operations_billing")),
        Depends(require_roles(*PAYROLL_ROLES)),
    ],
)


# ---------- Absensi & approval klien ----------


@router.get("/attendance", response_model=list[AttendanceOut])
def list_attendance(year: int = Query(...), month: int = Query(...), db: Session = Depends(get_db)):
    return service.list_attendance(db, year=year, month=month)


@router.post("/attendance", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def upsert_attendance(payload: AttendanceUpsert, db: Session = Depends(get_db)):
    return service.upsert_attendance(db, payload)


@router.patch("/attendance/{attendance_id}/client-approval", response_model=AttendanceOut)
def set_client_approval(
    attendance_id: str, approved: bool = Query(True), db: Session = Depends(get_db)
):
    """Approval kehadiran/lembur oleh klien sebelum masuk payrol."""
    return service.set_client_approval(db, attendance_id, approved)


# ---------- Payroll runs & slip gaji ----------


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)):
    return service.list_runs(db)


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.create_run(db, payload, tenant_id=user.tenant_id)


@router.post("/runs/{run_id}/generate", response_model=list[PayslipOut], status_code=201)
def generate_slips(
    run_id: str,
    payload: GenerateSlipsRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return service.generate_slips(db, run_id, payload, tenant_id=user.tenant_id)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return service.get_run(db, run_id)


@router.get("/runs/{run_id}/slips", response_model=list[PayslipOut])
def list_slips(run_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.list_slips(db, run_id)


# ---------- Saltab grid (Fase 9b) ----------


@router.get("/runs/{run_id}/saltab")
def saltab_view(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Grid line-item Saltab per karyawan (PRD §6)."""
    return service.saltab_view(db, run_id, tenant_id=user.tenant_id)


@router.patch("/saltab/components/{component_id}", response_model=dict)
def override_saltab_component(
    component_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Override manual nominal komponen; agregat slip dihitung ulang + audit."""
    from app.modules.payroll.schemas import SaltabComponentUpdate

    data = SaltabComponentUpdate(**payload)
    comp, slip = service.update_saltab_component(db, user, component_id, data.amount)
    return {
        "id": str(comp.id),
        "amount": float(comp.amount),
        "source": comp.source,
        "gross": float(slip.gross),
        "net_pay": float(slip.net_pay),
    }


@router.get("/runs/{run_id}/saltab/export")
def export_saltab(run_id: str, db: Session = Depends(get_db)):
    from fastapi import Response

    content, filename = service.saltab_export_csv(db, run_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/saltab/export-excel")
def export_saltab_excel(run_id: str, db: Session = Depends(get_db)):
    from fastapi import Response

    content, filename = service.saltab_export_excel(db, run_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/saltab/export-pdf")
def export_saltab_pdf(run_id: str, db: Session = Depends(get_db)):
    from fastapi import Response

    content, filename = service.saltab_export_pdf(db, run_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/runs/{run_id}/send-to-client", status_code=204)
def send_saltab_to_client(run_id: str, payload: dict, db: Session = Depends(get_db)):
    """Kirim manual Saltab ke email klien -- Fase 23 butir 4. Email penerima
    diisi manual di body (`recipient_email`), bukan diambil otomatis."""
    recipient_email = (payload.get("recipient_email") or "").strip()
    if not recipient_email:
        raise HTTPException(status_code=422, detail="recipient_email wajib diisi")
    service.send_saltab_to_client(db, run_id, recipient_email)


@router.get("/runs/{run_id}/bukti-potong/{employee_id}/pdf")
def export_bukti_potong_pdf(
    run_id: str,
    employee_id: str,
    db: Session = Depends(get_db),
):
    """PRD v3.0 §6 — Bukti Pemotongan PPh 21 per karyawan (dokumen compliance)."""
    from fastapi import Response

    content, filename = service.bukti_potong_pdf(db, run_id, employee_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}/employees/{employee_id}/payslip/pdf")
def export_employee_payslip_pdf(run_id: str, employee_id: str, db: Session = Depends(get_db)):
    """Fase 26 butir 5 -- payslip lengkap per karyawan (beda dari bukti potong)."""
    from fastapi import Response

    content, filename = service.employee_payslip_pdf(db, run_id, employee_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/runs/{run_id}/employees/{employee_id}/send-payslip-email", status_code=204)
def send_payslip_email(run_id: str, employee_id: str, db: Session = Depends(get_db)):
    """Fase 26 butir 5 -- kirim payslip ke email karyawan sendiri."""
    service.send_payslip_email(db, run_id, employee_id)


@router.post("/runs/{run_id}/finalize", response_model=RunOut)
def finalize_run(run_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return service.finalize_run(db, run_id, tenant_id=user.tenant_id)


# ---------- Fase 9a: dua jalur & approval klien ber-token ----------


@router.post("/runs/{run_id}/submit-to-client", response_model=dict)
def submit_to_client(
    run_id: str,
    payload: ClientLinkCreate | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Kirim payrol proyek ke klien; hasilkan link approval ber-token."""
    days = payload.days if payload else 14
    run, raw, expires = service.submit_to_client(db, user.tenant_id, run_id, days=days)
    return {
        "status": run.status.value,
        "expires_at": expires,
        "link": f"/payroll/client/{raw}",
        "raw_token": raw,
    }


@router.post("/runs/{run_id}/start-processing", response_model=RunOut)
def start_processing(run_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """internal draft → finance_processing · proyek client_approved → finance_processing."""
    return service.start_finance_processing(db, run_id, tenant_id=user.tenant_id)


# ---------- Preview PPh 21 ----------


@router.post("/tax-preview")
def tax_preview(payload: TaxPreviewIn, db: Session = Depends(get_db)):
    return service.preview_tax(payload, db)


# ---------- Publik (tanpa akun): approval klien via link ber-token ----------
# Guard lisensi TIDAK berlaku di sini — akses dikontrol token + kedaluwarsa,
# payload read-only, dan setiap keputusan tercatat di audit.

public_router = APIRouter(prefix="/payroll/client", tags=["payroll-client"])

# Entropi token (secrets.token_urlsafe(24)) sudah membuat brute-force tidak
# praktis, tapi endpoint publik & mutating tetap wajib rate-limited -- pola
# sama seperti ai_interview/router.py::_check_rate_limit.
_CLIENT_RATE_MAX = 30
_CLIENT_RATE_WINDOW_SEC = 3600


def _check_rate_limit(db: Session) -> None:
    ip, _ = get_request_meta()
    limiter = get_limiter("payroll_client_token")
    key = ip or "unknown"
    allowed, retry_after = limiter.check(
        db, key, max_attempts=_CLIENT_RATE_MAX, window_seconds=_CLIENT_RATE_WINDOW_SEC
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan dari lokasi ini. Coba lagi nanti.",
            headers={"Retry-After": str(retry_after)},
        )
    limiter.hit(db, key, window_seconds=_CLIENT_RATE_WINDOW_SEC)


@public_router.get("/{token}")
def client_view(token: str, db: Session = Depends(get_db)):
    """Ringkasan payrol proyek untuk klien (read-only)."""
    _check_rate_limit(db)
    return service.client_view(db, token)


@public_router.post("/{token}/decision")
def client_decision(
    token: str,
    payload: ClientDecisionIn,
    db: Session = Depends(get_db),
):
    """Rekam keputusan klien: setujui / tolak dengan nama & catatan."""
    _check_rate_limit(db)
    return service.decide_by_token(db, token, payload.approved, payload.name, payload.note)
