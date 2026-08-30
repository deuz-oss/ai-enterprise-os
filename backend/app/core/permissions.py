"""Registry terpusat role RBAC — satu sumber kebenaran utk `require_roles(...)`.

Sebelum file ini ada, tiap router menulis daftar role sendiri-sendiri secara
inline (24 titik tersebar di 17 file). Perilaku aksesnya sudah benar dan
teruji lewat pemakaian nyata, tapi tidak ada satu tempat yang bisa dibaca utk
tahu "siapa boleh apa" tanpa buka satu-satu file router. File ini murni
memindahkan literal string itu ke satu tempat — **tidak mengubah role yang
diizinkan di mana pun**.

Cara pakai di router: `require_roles(*FINANCE_ROLES)` alih-alih
`require_roles("finance", "management")`.

## 3 hal penting soal `require_roles` yang HARUS diketahui sebelum menambah
## atau mengubah daftar di bawah:

1. **`role == "admin"` SELALU lolos**, apa pun isi daftar role-nya — bahkan
   kalau daftarnya kosong (lihat `AUTH_ADMIN_ONLY_ROLES` di bawah, yang
   sengaja kosong justru supaya HANYA admin yang lolos, lewat bypass ini).
   Jadi menulis `"admin"` di dalam salah satu daftar di bawah ini
   **kosmetik/dokumentatif saja** — tidak menambah akses apa pun yang belum
   ada dari bypass. Lihat `core/security.py::require_roles`.
2. **`require_platform_admin()` TIDAK punya bypass admin ini.** Tenant admin
   biasa DITOLAK di endpoint `/platform/*`. Ini asimetris dgn poin 1 di atas
   secara sengaja — jangan disamakan. Lihat `core/security.py::require_platform_admin`.
3. **Jebakan penamaan**: anggota enum `UserRole.employee` nilainya string
   `"karyawan"` (bukan `"employee"`). `require_roles` membandingkan
   `user.role.value`, jadi role karyawan/ESS HARUS ditulis `"karyawan"` di
   sini. Sejauh registry ini dibuat (2026), belum ada satu pun endpoint yang
   membatasi akses ke role ini secara eksplisit lewat `require_roles` — akses
   karyawan diatur lewat `require_tenant_user()` (lolos semua role tenant)
   dan ESS scoping di level service, bukan RBAC per-route.

Lihat juga `backend/tests/test_rbac_matrix.py` — test yang membuktikan
ke-24 daftar di bawah ini benar-benar menahan/meloloskan role sesuai isinya,
plus test eksplisit utk 3 poin di atas.

## Cross-reference ke frontend

Sidebar (`frontend/src/components/Layout.tsx`, array `NAV_ITEMS`) punya field
`roles` sendiri yang independen dari file ini — itu cuma menyembunyikan menu,
BUKAN mekanisme keamanan (backend di file ini yang menegakkan akses
sesungguhnya). Kalau menambah/mengubah daftar di bawah, cek juga apakah
`NAV_ITEMS` terkait perlu disesuaikan supaya menu yang terlihat konsisten
dengan siapa yang benar-benar boleh akses.
"""

# ---------- Talent Cloud (sales_crm + recruitment) ----------

CLIENTS_ROLES = ("business_dev", "management")
PRESALES_ROLES = ("business_dev", "management")
RECRUITMENT_ROLES = ("recruiter", "management")
TALENTPOOL_ROLES = ("recruiter", "operations", "hr", "management")
TALENTPOOL_BRANDING_ROLES = ("admin", "management")
AI_RECRUITMENT_ROLES = ("recruiter", "management")

# ---------- Workforce Cloud (people_ops) ----------

HRD_ROLES = ("hr", "management")
ESIGN_ROLES = ("hr", "management")
BPJS_ROLES = ("operations", "hr", "finance", "management")
ATTENDANCE_SELFIE_ROLES = ("admin", "hr", "operations", "management")
AI_HR_ROLES = ("hr", "management")

# ---------- Revenue Cloud (payroll + finance) ----------

PAYROLL_ROLES = ("operations", "management", "hr")
FINANCE_ROLES = ("finance", "management")
PAYMENT_REQUEST_ROLES = ("operations", "hr", "finance", "management")
AI_FINANCE_ROLES = ("finance", "management")
RATES_ROLES = ("admin", "finance", "management")

# ---------- Govern Cloud (accounting + audit + users) ----------

ACCOUNTING_ROLES = ("finance", "management")
ACCOUNTING_TRANSACTIONS_ROLES = ("finance", "management")
AUDIT_ROLES = ("management",)
# Kosong disengaja: HANYA admin yang lolos, murni lewat bypass admin
# `require_roles` (lihat poin 1 di docstring atas) — bukan lupa isi.
AUTH_ADMIN_ONLY_ROLES: tuple[str, ...] = ()

# ---------- Lintas-bundle ----------

APPS_TRIAL_ROLES = ("admin", "management")
