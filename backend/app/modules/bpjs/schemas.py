from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContributionRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: UUID
    full_name: str
    ktp_no: str | None
    bpjs_kesehatan_no: str | None
    bpjs_ketenagakerjaan_no: str | None
    salary_kesehatan: int
    salary_jp: int
    # Rincian per program (rupiah): kes/jkk/jkm/jht/jp × employer/employee.
    breakdown: dict[str, int]
    employer_total: int
    employee_total: int
    grand_total: int


class RecapSummaryOut(BaseModel):
    employer_total: int
    employee_total: int
    grand_total: int


class BpjsRecapOut(BaseModel):
    year: int
    month: int
    rows: list[ContributionRowOut]
    summary: RecapSummaryOut
