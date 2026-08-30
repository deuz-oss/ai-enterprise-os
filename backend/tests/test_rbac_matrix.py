"""Test matrix RBAC — bukti tiap area di `core/permissions.py` benar-benar
menahan/meloloskan role sesuai yang dideklarasikan, plus semantik bypass yang
harus tetap konsisten (lihat komentar di puncak `core/permissions.py`).

Level unit, BUKAN lewat TestClient/HTTP: memanggil langsung closure
`dependency(user=...)` yang dikembalikan `require_roles(...)`/
`require_platform_admin()` — persis fungsi yang sama yang dipasang di 24
titik router asli, tanpa perlu DB/HTTP/fixture bisnis (cepat & deterministik,
tidak rentan flaky krn setup lisensi/data per modul).
"""

from types import SimpleNamespace

import pytest
from app.core import permissions
from app.core.security import require_platform_admin, require_roles
from app.modules.auth.models import UserRole
from fastapi import HTTPException


def _user(role: UserRole):
    return SimpleNamespace(role=role)


ALL_ROLES = list(UserRole)

# Cermin 1:1 ke-24 titik require_roles(...) di 17 router — lihat
# core/permissions.py utk pemetaan area -> file:line.
REGISTRY_AREAS = {
    "CLIENTS_ROLES": permissions.CLIENTS_ROLES,
    "PRESALES_ROLES": permissions.PRESALES_ROLES,
    "RECRUITMENT_ROLES": permissions.RECRUITMENT_ROLES,
    "TALENTPOOL_ROLES": permissions.TALENTPOOL_ROLES,
    "TALENTPOOL_BRANDING_ROLES": permissions.TALENTPOOL_BRANDING_ROLES,
    "AI_RECRUITMENT_ROLES": permissions.AI_RECRUITMENT_ROLES,
    "HRD_ROLES": permissions.HRD_ROLES,
    "ESIGN_ROLES": permissions.ESIGN_ROLES,
    "BPJS_ROLES": permissions.BPJS_ROLES,
    "ATTENDANCE_SELFIE_ROLES": permissions.ATTENDANCE_SELFIE_ROLES,
    "AI_HR_ROLES": permissions.AI_HR_ROLES,
    "PAYROLL_ROLES": permissions.PAYROLL_ROLES,
    "FINANCE_ROLES": permissions.FINANCE_ROLES,
    "PAYMENT_REQUEST_ROLES": permissions.PAYMENT_REQUEST_ROLES,
    "AI_FINANCE_ROLES": permissions.AI_FINANCE_ROLES,
    "RATES_ROLES": permissions.RATES_ROLES,
    "ACCOUNTING_ROLES": permissions.ACCOUNTING_ROLES,
    "ACCOUNTING_TRANSACTIONS_ROLES": permissions.ACCOUNTING_TRANSACTIONS_ROLES,
    "AUDIT_ROLES": permissions.AUDIT_ROLES,
    "AUTH_ADMIN_ONLY_ROLES": permissions.AUTH_ADMIN_ONLY_ROLES,
    "APPS_TRIAL_ROLES": permissions.APPS_TRIAL_ROLES,
}


@pytest.mark.parametrize("area_name,allowed_roles", REGISTRY_AREAS.items())
def test_allowed_roles_pass(area_name, allowed_roles):
    dependency = require_roles(*allowed_roles)
    for role_value in allowed_roles:
        role = UserRole(role_value)
        assert (
            dependency(user=_user(role)) is not None
        ), f"{area_name}: role '{role_value}' seharusnya lolos, malah ditolak"


@pytest.mark.parametrize("area_name,allowed_roles", REGISTRY_AREAS.items())
def test_disallowed_roles_blocked(area_name, allowed_roles):
    dependency = require_roles(*allowed_roles)
    for role in ALL_ROLES:
        if role == UserRole.admin:
            continue  # admin selalu bypass require_roles — diuji terpisah di bawah.
        if role.value in allowed_roles:
            continue  # memang diizinkan di area ini.
        with pytest.raises(HTTPException) as exc:
            dependency(user=_user(role))
        assert (
            exc.value.status_code == 403
        ), f"{area_name}: role '{role.value}' seharusnya 403, malah lolos/error lain"


def test_admin_always_bypasses_require_roles():
    """`admin` lolos `require_roles(...)` apa pun isi daftarnya, termasuk
    daftar kosong (`AUTH_ADMIN_ONLY_ROLES`) — lihat `core/security.py`.
    """
    assert require_roles()(user=_user(UserRole.admin)) is not None
    not_hr_dependency = require_roles(*permissions.HRD_ROLES)
    assert "admin" not in permissions.HRD_ROLES
    assert not_hr_dependency(user=_user(UserRole.admin)) is not None


def test_platform_admin_has_no_bypass_for_tenant_admin():
    """Asimetris dgn `require_roles`: tenant `admin` biasa DITOLAK di rute
    platform — `require_platform_admin` tidak punya bypass admin sama sekali.
    """
    dependency = require_platform_admin()
    assert dependency(user=_user(UserRole.platform_admin)) is not None
    with pytest.raises(HTTPException) as exc:
        dependency(user=_user(UserRole.admin))
    assert exc.value.status_code == 403


def test_employee_role_value_is_karyawan_not_employee():
    """Jebakan: nama anggota enum `employee`, nilai string-nya `"karyawan"`.
    `require_roles` membandingkan `.value` — kanari ini jaga supaya kalau
    ada yang menulis `require_roles("employee")` di masa depan, ketahuan
    langsung lewat test ini alih-alih gagal senyap di produksi.
    """
    assert UserRole.employee.value == "karyawan"
    assert UserRole.employee.name == "employee"
