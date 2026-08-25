"""Fase 8 — Absensi harian: CRUD, agregasi, impor CSV, validasi dua jalur."""

import csv
import io
import logging
from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import parse_uuid
from app.modules import audit
from app.modules.attendance.models import (
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
)
from app.modules.attendance.schemas import (
    AttendanceRecordIn,
    ImportResultOut,
    ImportRowFailure,
)

logger = logging.getLogger(__name__)

# Status yang dihitung sebagai hari hadir dalam agregasi bulanan.
PRESENT_STATUSES = {
    AttendanceStatus.hadir,
    AttendanceStatus.terlambat,
    AttendanceStatus.dinas_luar,
}

TEMPLATE_HEADER = ["employee_no", "date", "clock_in", "clock_out", "overtime_hours", "status"]


# ---------- Agregasi otomatis ----------


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def recompute_month_summary(db: Session, employee_id, year: int, month: int):
    """Bangun ulang `AttendanceSummary` dari record harian (artefak agregasi).

    Angka berubah → approval (klien untuk eksternal / HR untuk internal)
    di-reset agar diverifikasi ulang, konsisten dengan perilaku payrol.
    """
    from app.modules.payroll.models import AttendanceSummary

    start, end = _month_bounds(year, month)
    rows = db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.employee_id == parse_uuid(str(employee_id)))
        .where(AttendanceRecord.date >= start)
        .where(AttendanceRecord.date <= end)
        .order_by(AttendanceRecord.date)
    ).scalars().all()

    present = sum(1 for r in rows if r.status in PRESENT_STATUSES)
    overtime = sum(r.overtime_hours for r in rows)

    summary = db.execute(
        select(AttendanceSummary)
        .where(AttendanceSummary.employee_id == parse_uuid(str(employee_id)))
        .where(AttendanceSummary.year == year)
        .where(AttendanceSummary.month == month)
    ).scalar_one_or_none()
    if summary is None:
        if not rows:
            return None
        summary = AttendanceSummary(
            employee_id=parse_uuid(str(employee_id)),
            year=year,
            month=month,
            notes="Agregasi otomatis absensi harian",
        )
        db.add(summary)
    if summary.present_days != present or summary.overtime_hours != overtime:
        summary.present_days = present
        summary.overtime_hours = overtime
        # Angka berubah → validasi ulang (dua jalur: HR/klien).
        summary.client_approved = False
        summary.approved_at = None
    db.commit()
    db.refresh(summary)
    return summary


def _affected_months(db: Session, employee_id) -> list[tuple[int, int]]:
    rows = db.execute(
        select(func.distinct(AttendanceRecord.date)).where(
            AttendanceRecord.employee_id == parse_uuid(str(employee_id))
        )
    ).all()
    months: set[tuple[int, int]] = set()
    for (d,) in rows:
        if isinstance(d, str):
            d = date.fromisoformat(d)
        months.add((d.year, d.month))
    return sorted(months)


# ---------- Input manual (HR/Ops) ----------


def upsert_record(db: Session, payload: AttendanceRecordIn) -> tuple[AttendanceRecord, bool]:
    from app.modules.hrd.models import Employee

    employee = db.get(Employee, parse_uuid(str(payload.employee_id)))
    if employee is None:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")

    existing = db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.employee_id == employee.id)
        .where(AttendanceRecord.date == payload.date)
    ).scalar_one_or_none()
    inserted = existing is None
    record = existing or AttendanceRecord(employee_id=employee.id, date=payload.date)
    record.status = payload.status
    record.clock_in = payload.clock_in
    record.clock_out = payload.clock_out
    record.overtime_hours = payload.overtime_hours
    record.source = AttendanceSource.manual
    record.notes = (payload.notes or "").strip() or None
    db.add(record)
    db.commit()
    db.refresh(record)
    audit.log_event(
        db,
        action="attendance.record_upserted",
        entity_type="attendance_record",
        entity_id=record.id,
        detail={
            "employee_id": str(employee.id),
            "date": record.date.isoformat(),
            "status": record.status.value,
            "inserted": inserted,
        },
    )
    recompute_month_summary(db, employee.id, record.date.year, record.date.month)
    return record, inserted


def list_records(
    db: Session, year: int, month: int, employee_id: str | None = None
) -> list[AttendanceRecord]:
    from app.modules.hrd.models import Employee

    start, end = _month_bounds(year, month)
    stmt = (
        select(AttendanceRecord)
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
        .where(AttendanceRecord.date >= start)
        .where(AttendanceRecord.date <= end)
        .order_by(AttendanceRecord.date, Employee.full_name)
    )
    if employee_id is not None:
        stmt = stmt.where(AttendanceRecord.employee_id == parse_uuid(employee_id))
    return list(db.execute(stmt).scalars())


# ---------- Impor CSV mesin fingerprint ----------


def template_csv() -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(TEMPLATE_HEADER)
    writer.writerow(["EMP-0001", "2026-08-03", "2026-08-03 07:55", "2026-08-03 17:05", 2, "hadir"])
    return buffer.getvalue()


def _parse_datetime(value: str, base_date: date | None) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    if base_date is not None:
        try:
            t = datetime.strptime(value, "%H:%M")
            return datetime.combine(base_date, t.time())
        except ValueError:
            pass
    raise ValueError(f"Waktu tidak valid: '{value}'")


def _parse_status(value: str) -> AttendanceStatus:
    normalized = value.strip().lower().replace(" ", "_") or "hadir"
    try:
        return AttendanceStatus(normalized)
    except ValueError:
        raise ValueError(
            f"Status tidak valid: '{value}' (pilihan: "
            f"{', '.join(s.value for s in AttendanceStatus)})"
        ) from None


async def import_csv(db: Session, file: UploadFile) -> ImportResultOut:
    """Impor CSV fingerprint; baris gagal dilaporkan tanpa menghentikan lainnya."""
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    sample = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    result = ImportResultOut(inserted=0, updated=0, failed=[])
    employees_cache: dict[str, Any] = {}
    touched: dict[tuple, set] = {}

    for idx, row in enumerate(reader, start=2):  # baris 1 = header
        employee_no = (row.get("employee_no") or "").strip()
        try:
            if not employee_no:
                raise ValueError("employee_no kosong")
            if employee_no not in employees_cache:
                from app.modules.hrd.models import Employee

                employees_cache[employee_no] = db.execute(
                    select(Employee).where(Employee.employee_no == employee_no)
                ).scalar_one_or_none()
            employee = employees_cache[employee_no]
            if employee is None:
                raise ValueError(f"Nomor induk '{employee_no}' tidak ditemukan")

            raw_date = (row.get("date") or "").strip()
            try:
                record_date = date.fromisoformat(raw_date)
            except ValueError:
                msg = f"Tanggal tidak valid: '{raw_date}' (format YYYY-MM-DD)"
                raise ValueError(msg) from None
            clock_in = _parse_datetime((row.get("clock_in") or "").strip(), record_date)
            clock_out = _parse_datetime((row.get("clock_out") or "").strip(), record_date)
            status = _parse_status((row.get("status") or "").strip())
            overtime_raw = (row.get("overtime_hours") or "").strip() or "0"
            overtime = int(float(overtime_raw))
            if overtime < 0:
                raise ValueError("Jam lembur negatif")

            existing = db.execute(
                select(AttendanceRecord)
                .where(AttendanceRecord.employee_id == employee.id)
                .where(AttendanceRecord.date == record_date)
            ).scalar_one_or_none()
            record = existing or AttendanceRecord(
                employee_id=employee.id, date=record_date
            )
            record.status = status
            record.clock_in = clock_in
            record.clock_out = clock_out
            record.overtime_hours = overtime
            record.source = AttendanceSource.impor
            db.add(record)
            if existing is None:
                result.inserted += 1
            else:
                result.updated += 1
            touched.setdefault((employee.id, record_date.year, record_date.month), set()).add(
                record_date
            )
        except (ValueError, TypeError) as exc:
            result.failed.append(
                ImportRowFailure(row=idx, employee_no=employee_no or "-", error=str(exc))
            )

    db.commit()
    for (employee_id, year, month), _dates in touched.items():
        recompute_month_summary(db, employee_id, year, month)
    if result.failed:
        logger.warning("Impor absensi: %d baris gagal", len(result.failed))
    audit.log_event(
        db,
        action="attendance.imported",
        entity_type="attendance_record",
        detail={
            "inserted": result.inserted,
            "updated": result.updated,
            "failed_rows": len(result.failed),
        },
    )
    return result


# ---------- Validasi dua jalur ----------


def validate_summary(db: Session, user, summary_id: str, lane: str):
    """Validasi rekap bulanan: internal → HR, eksternal → Ops (approval klien)."""

    from app.modules.payroll.models import AttendanceSummary

    allowed_roles = {
        "hr": ("hr", "management"),
        "klien": ("operations", "management"),
    }.get(lane)
    if allowed_roles is None:
        raise HTTPException(status_code=422, detail="Jalur harus 'hr' atau 'klien'")
    if user.role != "admin" and user.role.value not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Jalur '{lane}' hanya untuk role {', '.join(allowed_roles)}",
        )

    summary = db.get(AttendanceSummary, parse_uuid(summary_id))
    if summary is None:
        raise HTTPException(status_code=404, detail="Rekap absensi tidak ditemukan")
    employee_type = summary.employee.employment_type.value

    if lane == "hr":
        if employee_type != "internal":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Karyawan ini {employee_type} — validasi melalui jalur "
                    "Operations/approval klien"
                ),
            )
    elif lane == "klien":
        if employee_type != "eksternal":
            raise HTTPException(
                status_code=422,
                detail=f"Karyawan ini {employee_type} — validasi melalui jalur HR",
            )
    else:
        raise HTTPException(status_code=422, detail="Jalur harus 'hr' atau 'klien'")

    summary.client_approved = True
    summary.approved_at = datetime.now(UTC)
    db.commit()
    db.refresh(summary)
    audit.log_event(
        db,
        action="attendance.summary_validated",
        entity_type="attendance_summary",
        entity_id=summary.id,
        detail={"lane": lane, "employment_type": employee_type},
    )
    return summary


# ---------- Integrasi ESS: cuti disetujui → record otomatis ----------

LEAVE_STATUS_MAP = {
    "cuti_tahunan": AttendanceStatus.cuti,
    "cuti_tak_berbayar": AttendanceStatus.cuti,
    "izin": AttendanceStatus.izin,
    "sakit": AttendanceStatus.sakit,
}


def sync_leave_records(db, leave) -> int:
    """Panggil saat cuti/izin ESS disetujui.

    Membuat record ber-status cuti/izin/sakit untuk tiap tanggal rentang;
    tanggal yang sudah punya record (manual/impor) TIDAK ditimpa.
    Kembalikan jumlah record dibuat.
    """
    created = 0
    current = leave.start_date
    while current <= leave.end_date:
        existing = db.execute(
            select(AttendanceRecord)
            .where(AttendanceRecord.employee_id == leave.employee_id)
            .where(AttendanceRecord.date == current)
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                AttendanceRecord(
                    employee_id=leave.employee_id,
                    date=current,
                    status=LEAVE_STATUS_MAP.get(
                        leave.leave_type.value, AttendanceStatus.cuti
                    ),
                    source=AttendanceSource.ess,
                    notes=f"Dari pengajuan cuti/izin ESS ({leave.leave_type.value})",
                )
            )
            created += 1
        current = date.fromordinal(current.toordinal() + 1)
    if created:
        db.commit()
        # Hitung bulan terdampak langsung dari rentang cuti (hindari DISTINCT Date di SQLite).
        months: set[tuple[int, int]] = set()
        cur = date(leave.start_date.year, leave.start_date.month, 1)
        end_month = date(leave.end_date.year, leave.end_date.month, 1)
        while cur <= end_month:
            months.add((cur.year, cur.month))
            if cur.month == 12:
                cur = date(cur.year + 1, 1, 1)
            else:
                cur = date(cur.year, cur.month + 1, 1)
        for year, month in months:
            recompute_month_summary(db, leave.employee_id, year, month)
    audit.log_event(
        db,
        action="attendance.synced_from_leave",
        entity_type="leave_request",
        entity_id=leave.id,
        detail={"created": created},
    )
    return created
