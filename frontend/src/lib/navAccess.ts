/**
 * Akses halaman per area (audit 2026-11-11 Top-20 #4).
 *
 * Dulu tiap item sidebar membawa daftar `roles` sendiri yang harus
 * disinkronkan manual dengan backend, dan separuhnya kosong -- role finance
 * melihat Pipeline/Clients/Job Orders/Employees/Payroll yang semuanya 403,
 * lalu halamannya tampil dengan KPI nol dan tombol aksi aktif.
 *
 * Sekarang backend yang menentukan: `GET /auth/me` mengirim `allowed_areas`
 * (lihat `backend/app/core/permissions.py::NAV_AREAS`). Frontend hanya perlu
 * tahu area mana yang ber-guard; daftar di bawah WAJIB sama dengan kunci
 * `NAV_AREAS` -- dijaga `backend/tests/test_nav_areas.py`.
 *
 * Area = segmen pertama path (`/clients/123` -> "clients"). Halaman di luar
 * daftar (Overview, Chat, Pages, Portal Saya, Platform) tidak ber-guard role
 * di sini; karyawan & platform_admin punya aturan sendiri di Layout.tsx.
 *
 * Ini bukan keamanan -- backend tetap menolak (403) apa pun yang tidak boleh.
 */
export const GUARDED_AREAS = [
  "leads",
  "clients",
  "quotations",
  "agreements",
  "suppressed-contacts",
  "job-orders",
  "referral",
  "talent-pool",
  "ai-interview",
  "blacklist",
  "employees",
  "attendance",
  "payroll",
  "payment-requests",
  "finance",
  "accounting",
  "rates",
  "billing",
  "audit",
  "users",
] as const;

const GUARDED = new Set<string>(GUARDED_AREAS);

/** Area ber-guard untuk path ini, atau null bila halamannya terbuka. */
export function guardedAreaOf(pathname: string): string | null {
  const segment = pathname.split("/")[1] ?? "";
  return GUARDED.has(segment) ? segment : null;
}

/**
 * Boleh membuka path ini? `allowedAreas` undefined = belum diketahui (backend
 * lama tanpa field ini) -> jangan memblokir; backend tetap gerbang
 * sesungguhnya.
 */
export function canOpenPath(pathname: string, allowedAreas: readonly string[] | undefined): boolean {
  const area = guardedAreaOf(pathname);
  if (area === null || allowedAreas === undefined) return true;
  return allowedAreas.includes(area);
}
