"""`allowed_areas` di `GET /auth/me` harus SAMA dengan yang benar-benar
ditegakkan backend (audit 2026-11-11 Top-20 #4).

Sidebar & guard halaman frontend disaring dari `allowed_areas`. Kalau daftar
itu melenceng dari guard router, menu kembali menyesatkan: tampil tapi 403,
atau tersembunyi padahal boleh. Test ini memanggil endpoint data utama tiap
area sebagai tiap role dan mencocokkannya -- jadi mengubah role di satu sisi
tanpa sisi lain langsung ketahuan.
"""

import pytest
from app.core.permissions import NAV_AREAS, allowed_areas

from tests.conftest import _auth_header, _login_header

PASSWORD = "rahasia-123"

# Endpoint data utama yang dimuat halaman area tsb.
PRIMARY_ENDPOINT = {
    "leads": "/leads",
    "clients": "/clients",
    "quotations": "/quotations",
    "agreements": "/agreements",
    "suppressed-contacts": "/suppressed-contacts",
    "job-orders": "/recruitment/job-orders",
    "referral": "/recruitment/referral-rewards",
    "talent-pool": "/talentpool",
    "ai-interview": "/ai-interview/templates",
    "blacklist": "/blacklist/entries",
    "employees": "/employees",
    "attendance": "/attendance/records?year=2026&month=11",
    "payroll": "/payroll/runs",
    "payment-requests": "/payment-requests",
    "finance": "/finance/invoices",
    "accounting": "/accounting/journal",
    "rates": "/rates/pph21",
    "billing": "/billing/payment-methods",
    "audit": "/audit/logs",
    "users": "/auth/users",
}

# GET tarif terbuka untuk semua user tenant (payroll/finance membacanya);
# hanya PENULISAN yang dibatasi RATES_ROLES. Halaman Rate Configuration tetap
# disembunyikan dari role lain, tapi endpoint bacanya memang tidak 403.
READ_OPEN_AREAS = {"rates"}

TENANT_ROLES = [
    "admin",
    "management",
    "business_dev",
    "recruiter",
    "hr",
    "operations",
    "finance",
    "karyawan",
]


def _role_header(client, admin, role: str) -> dict[str, str]:
    if role == "admin":
        return admin
    email = f"nav-{role}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={"email": email, "full_name": f"Nav {role}", "password": PASSWORD, "role": role},
    )
    assert resp.status_code in (201, 409), resp.text
    return _login_header(client, email, PASSWORD)


def test_setiap_area_punya_endpoint_uji():
    assert set(PRIMARY_ENDPOINT) == set(NAV_AREAS)


@pytest.mark.parametrize("role", TENANT_ROLES)
def test_allowed_areas_cocok_dengan_guard_backend(client, role):
    headers = _role_header(client, _auth_header(client), role)

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    areas = me.json()["allowed_areas"]
    assert areas == allowed_areas(role)

    for area, path in PRIMARY_ENDPOINT.items():
        status = client.get(f"/api/v1{path}", headers=headers).status_code
        if area in areas:
            assert status == 200, f"{role}: area '{area}' diiklankan boleh tapi {path} -> {status}"
        elif area not in READ_OPEN_AREAS:
            assert status == 403, f"{role}: area '{area}' disembunyikan tapi {path} -> {status}"


def test_daftar_area_frontend_sama_dengan_backend():
    """`GUARDED_AREAS` di frontend adalah salinan kunci NAV_AREAS -- area yang
    ada di satu sisi saja berarti menu tampil tanpa guard, atau guard tanpa menu."""
    import re
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "navAccess.ts"
    block = re.search(r"GUARDED_AREAS = \[(.*?)\] as const", source.read_text("utf-8"), re.S)
    assert block, "GUARDED_AREAS tidak ditemukan di navAccess.ts"
    frontend_areas = re.findall(r'"([^"]+)"', block.group(1))

    assert frontend_areas == list(NAV_AREAS)


def test_admin_semua_area_karyawan_tidak_ada():
    assert allowed_areas("admin") == list(NAV_AREAS)
    assert allowed_areas("karyawan") == []
    assert allowed_areas("platform_admin") == []
    assert allowed_areas("finance") == [
        "payment-requests",
        "finance",
        "accounting",
        "rates",
        "billing",
    ]
