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

# Pengelompokan di bawah mengikuti 5 kategori navigasi Opsi G (Fase 28) yang
# dipakai sidebar (`Layout.tsx`, `CATEGORY_ORDER`) — menggantikan judul lama
# bergaya "Talent/Workforce/Revenue/Govern Cloud" (paket komersial Opsi F)
# yang sudah tidak dipakai lagi dan bikin salah baca arsitektur aktif.
# Pengelompokan ini murni penataan/dokumentasi: tidak ada satu pun daftar role
# yang isinya berubah.

# ---------- CRM ----------

CLIENTS_ROLES = ("business_dev", "management")
# Lookup baca-saja (id + nama) untuk dropdown lintas modul. Modul Klien
# sendiri tetap milik CRM, tapi alur role lain butuh MEMILIH klien: finance
# membuat invoice, recruiter membuat job order, HR/operations menjalankan
# payroll proyek. Sebelum ada lookup ini `GET /clients` menolak mereka (403)
# sehingga dropdown kosong tanpa pesan (audit 2026-11-11 Top-20 #1).
CLIENT_LOOKUP_ROLES = ("business_dev", "management", "recruiter", "hr", "operations", "finance")
# Lokasi kerja (geofencing) dipilih HR di halaman Karyawan.
CLIENT_SITE_LOOKUP_ROLES = ("business_dev", "management", "hr")
PRESALES_ROLES = ("business_dev", "management")
AI_PRESALES_ROLES = ("business_dev", "management")

# ---------- Recruitment ----------

RECRUITMENT_ROLES = ("recruiter", "management")
TALENTPOOL_ROLES = ("recruiter", "operations", "hr", "management")
TALENTPOOL_BRANDING_ROLES = ("admin", "management")
AI_RECRUITMENT_ROLES = ("recruiter", "management")
# Masa retensi data AI Interview (UU PDP) -- keputusan kepatuhan, bukan
# operasional recruiter harian; baca pengaturan tetap RECRUITMENT_ROLES.
AI_INTERVIEW_SETTINGS_ROLES = ("management",)

# ---------- Workforce ----------
# Payroll ada di sini (bukan Finance & Accounting) mengikuti keputusan
# Fase 28 — lihat komentar pada item `/payroll` di `NAV_ITEMS` Layout.tsx.

HRD_ROLES = ("hr", "management")
# Daftar & detail karyawan (baca) juga dibuka untuk operations -- lihat
# `employees_view_router` di hrd/router.py.
EMPLOYEES_VIEW_ROLES = (*HRD_ROLES, "operations")
ESIGN_ROLES = ("hr", "management")
BPJS_ROLES = ("operations", "hr", "finance", "management")
ATTENDANCE_ROLES = ("admin", "hr", "operations", "management")
ATTENDANCE_SELFIE_ROLES = ("admin", "hr", "operations", "management")
AI_HR_ROLES = ("hr", "management")
PAYROLL_ROLES = ("operations", "management", "hr")

# ---------- Finance & Accounting ----------

FINANCE_ROLES = ("finance", "management")
PAYMENT_REQUEST_ROLES = ("operations", "hr", "finance", "management")
AI_FINANCE_ROLES = ("finance", "management")
ACCOUNTING_ROLES = ("finance", "management")
ACCOUNTING_TRANSACTIONS_ROLES = ("finance", "management")

# ---------- Administration ----------

RATES_ROLES = ("admin", "finance", "management")
AUDIT_ROLES = ("management",)
# Aksi yang menggerakkan uang/langganan tenant (subscribe, top up, auto-reload).
# Baca saldo tetap terbuka utk staf (indikator topbar Layout.tsx).
BILLING_MANAGE_ROLES = ("finance", "management")
# Kosong disengaja: HANYA admin yang lolos, murni lewat bypass admin
# `require_roles` (lihat poin 1 di docstring atas) — bukan lupa isi.
AUTH_ADMIN_ONLY_ROLES: tuple[str, ...] = ()
# Lookup baca-saja (id + nama) anggota tim: pemilik lead (business_dev) dan
# pewawancara (recruiter). Daftar akun lengkap (`GET /auth/users`: email,
# role, status) tetap khusus admin.
USER_LOOKUP_ROLES = ("business_dev", "recruiter", "management")

# ---------- Lintas-kategori ----------

APPS_TRIAL_ROLES = ("admin", "management")

# ---------- Area navigasi (sidebar & guard halaman frontend) ----------
# Kunci = segmen pertama route frontend (`/finance` -> "finance"). Nilainya
# role yang lolos guard backend untuk DATA UTAMA halaman itu. `GET /auth/me`
# mengirim `allowed_areas` hasil `allowed_areas()` di bawah, dan frontend
# (`Layout.tsx`) memakainya untuk menyaring sidebar serta menampilkan "Tidak
# ada akses" -- menggantikan daftar `roles` terpisah di NAV_ITEMS yang dulu
# harus disinkronkan manual dan separuhnya kosong (audit 2026-11-11 Top-20 #4:
# role finance melihat 7 menu yang semuanya 403).
#
# Ini TETAP bukan mekanisme keamanan: yang menegakkan akses adalah
# `require_roles(...)` di tiap router. Halaman tanpa guard role (Overview,
# Chat, Pages) sengaja tidak ada di sini = selalu tampil.
NAV_AREAS: dict[str, tuple[str, ...]] = {
    "leads": PRESALES_ROLES,
    "clients": CLIENTS_ROLES,
    "quotations": PRESALES_ROLES,
    "agreements": PRESALES_ROLES,
    "suppressed-contacts": PRESALES_ROLES,
    "job-orders": RECRUITMENT_ROLES,
    "referral": RECRUITMENT_ROLES,
    "talent-pool": TALENTPOOL_ROLES,
    "ai-interview": RECRUITMENT_ROLES,
    "blacklist": RECRUITMENT_ROLES,
    "employees": EMPLOYEES_VIEW_ROLES,
    "attendance": ATTENDANCE_ROLES,
    "payroll": PAYROLL_ROLES,
    "payment-requests": PAYMENT_REQUEST_ROLES,
    "finance": FINANCE_ROLES,
    "accounting": ACCOUNTING_ROLES,
    "rates": RATES_ROLES,
    "billing": BILLING_MANAGE_ROLES,
    "audit": AUDIT_ROLES,
    "users": AUTH_ADMIN_ONLY_ROLES,
}


def allowed_areas(role: str) -> list[str]:
    """Area navigasi yang boleh dibuka `role` (admin tenant: semuanya,
    selaras bypass admin di `require_roles`)."""
    if role == "admin":
        return list(NAV_AREAS)
    return [area for area, roles in NAV_AREAS.items() if role in roles]
