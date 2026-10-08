"""Jurnal otomatis finalisasi payroll harus selalu terposting & seimbang.

Audit 2026-10-08 Phase 5: baris jurnal dulu dihitung dengan float dan
dibulatkan per baris, sementara sisi kredit hanya memuat net + PPh21 + BPJS
karyawan. Potongan lain (admin bank non-Mandiri, potongan manual) membuat
debit != kredit sehingga `post_auto_event` menolak jurnal secara diam-diam --
run tetap final tanpa jurnal di buku besar.
"""

from decimal import Decimal

from tests.conftest import _auth_header


def _finalized_run_with_bank_fee(client, headers, month: int) -> dict:
    fee = client.post(
        "/api/v1/rates/bank-fees",
        headers=headers,
        json={"bank_name": "Bank Jurnal Fee", "fee": 6500},
    )
    assert fee.status_code in (200, 201), fee.text
    emp = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "full_name": "Jurnal Fee Emp",
            "base_salary": 5_123_457,
            "bank_name": "Bank Jurnal Fee",
        },
    )
    assert emp.status_code == 201, emp.text
    run = client.post(
        "/api/v1/payroll/runs", headers=headers, json={"year": 2026, "month": month}
    ).json()
    slips = client.post(
        f"/api/v1/payroll/runs/{run['id']}/generate", headers=headers, json={}
    ).json()
    slip = next(s for s in slips if s["employee_id"] == emp.json()["id"])
    # Prasyarat skenario: memang ada potongan selain PPh21/BPJS.
    assert float(slip["deductions"]) > float(slip["tax_pph21"])
    finalized = client.post(f"/api/v1/payroll/runs/{run['id']}/finalize", headers=headers)
    assert finalized.status_code == 200, finalized.text
    return run


def test_jurnal_payroll_terposting_meski_ada_potongan_admin_bank(client):
    headers = _auth_header(client)
    run = _finalized_run_with_bank_fee(client, headers, month=5)

    entries = client.get(
        "/api/v1/accounting/journal",
        headers=headers,
        params={"event_code": "payroll_finalized_internal"},
    ).json()
    mine = [e for e in entries if e.get("source_ref_id") == run["id"]]
    assert len(mine) == 1, "jurnal finalisasi payroll tidak terposting"

    lines = mine[0]["lines"]
    debit = sum(Decimal(str(line["debit"])) for line in lines)
    credit = sum(Decimal(str(line["credit"])) for line in lines)
    assert debit == credit
    assert debit > 0
    kliring = [line for line in lines if line["account_code"] == "2-1400"]
    assert len(kliring) == 1
    assert Decimal(str(kliring[0]["credit"])) == Decimal("6500")


def test_post_auto_event_tidak_menolak_karena_sisa_float(client):
    """0.1 + 0.2 != 0.3 di float; jurnal yang seimbang secara rupiah tetap
    harus terposting setelah dinormalisasi ke Decimal sen."""
    from datetime import date
    from uuid import uuid4

    from app.core.tenancy import get_tenant, set_tenant
    from app.modules.accounting.service import ensure_coa, post_auto_event

    _auth_header(client)  # memastikan tenant default + admin ada
    db = client.testing_session()
    prev_tenant = get_tenant()
    try:
        from app.modules.platform.models import Tenant

        tenant = db.query(Tenant).first()
        set_tenant(tenant.id)
        ensure_coa(db, tenant.id)
        entry = post_auto_event(
            db,
            tenant_id=tenant.id,
            event_code="uji_sisa_float",
            source_ref_type="uji",
            source_ref_id=uuid4(),
            entry_date=date.today(),
            description="uji",
            lines=[("5-9000", 0.1 + 0.2, 0.0), ("1-1100", 0.0, 0.3)],
        )
        assert entry is not None
    finally:
        # Konteks tenant global -- jangan bocor ke test berikutnya.
        set_tenant(prev_tenant)
        db.close()
