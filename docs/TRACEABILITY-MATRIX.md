# AI Enterprise OS Requirement Traceability Matrix (RTM)

**File:** `docs/TRACEABILITY-MATRIX.md`

**Version:** 1.0

**Status:** Master Requirement Tracking Document

---

# 1. Purpose

Dokumen ini menjadi **single source of truth** untuk menelusuri setiap requirement dari tahap visi hingga implementasi.

Seluruh perubahan pada AI Enterprise OS harus dapat ditelusuri melalui dokumen ini.

Traceability memastikan bahwa:

* setiap visi memiliki capability,
* setiap capability memiliki desain,
* setiap desain memiliki implementasi,
* setiap implementasi memiliki pengujian,
* setiap perubahan dapat diaudit.

---

# 2. Traceability Flow

```text
AEP
(Product Vision)

 │

 ▼

ASF-BUILD
(Business Capability)

 │

 ▼

ASF-IMPLEMENTATION
(Engineering Design)

 │

 ▼

Repository Module

 │

 ▼

Source Code

 │

 ▼

Unit Test

 │

 ▼

Integration Test

 │

 ▼

Release
```

---

# 3. Requirement Status

Setiap requirement wajib memiliki salah satu status berikut:

| Status | Description |
| ----------- | --------------------- |
| Planned | Belum dimulai |
| In Progress | Sedang dikembangkan |
| Review | Sedang direview |
| Tested | Sudah lulus pengujian |
| Released | Sudah dirilis |
| Deprecated | Tidak lagi digunakan |

---

# 4. Requirement Matrix

| AEP | ASF-BUILD | ASF-IMPLEMENTATION | Repository Module | Source Code | Test | Status |
| ------- | ------------- | ---------------------- | ------------------------------------ | ----------- | ------- | --------- |
| AEP-000 | — | — | docs/AEP | — | — | Completed |
| AEP-001 | ASF-BUILD-001 | ASF-IMPLEMENTATION-003 | intelligence/strategy-intelligence | Pending | Pending | Planned |
| AEP-002 | ASF-BUILD-002 | ASF-IMPLEMENTATION-003 | intelligence/executive-intelligence | Pending | Pending | Planned |
| AEP-003 | ASF-BUILD-003 | ASF-IMPLEMENTATION-004 | platform/knowledge | Pending | Pending | Planned |
| ... | ... | ... | ... | ... | ... | ... |
| AEP-041 | ASF-BUILD-041 | ASF-IMPLEMENTATION-004 | intelligence/finance-intelligence | Pending | Pending | Planned |
| AEP-042 | ASF-BUILD-042 | ASF-IMPLEMENTATION-004 | intelligence/hr-intelligence | Pending | Pending | Planned |
| AEP-043 | ASF-BUILD-043 | ASF-IMPLEMENTATION-004 | intelligence/sales-intelligence | Pending | Pending | Planned |
| AEP-044 | ASF-BUILD-044 | ASF-IMPLEMENTATION-004 | intelligence/operations-intelligence | Pending | Pending | Planned |
| AEP-045 | ASF-BUILD-045 | ASF-IMPLEMENTATION-004 | intelligence/customer-intelligence | Pending | Pending | Planned |
| AEP-046 | ASF-BUILD-046 | ASF-IMPLEMENTATION-003 | intelligence/innovation-intelligence | Pending | Pending | Planned |
| AEP-047 | ASF-BUILD-047 | ASF-IMPLEMENTATION-003 | intelligence/ecosystem-intelligence | Pending | Pending | Planned |
| AEP-048 | ASF-BUILD-048 | ASF-IMPLEMENTATION-003 | intelligence/governance-intelligence | Pending | Pending | Planned |
| AEP-049 | ASF-BUILD-049 | ASF-IMPLEMENTATION-003 | intelligence/executive-intelligence | Pending | Pending | Planned |
| AEP-050 | ASF-BUILD-050 | ASF-IMPLEMENTATION-003 | intelligence/executive-intelligence | Pending | Pending | Planned |

> **Catatan:** Baris-baris di atas adalah template awal. Matriks ini harus diperbarui agar mencerminkan isi AEP dan ASF-BUILD yang sebenarnya seiring implementasi berlangsung.

---

# 5. Module Traceability

Setiap module wajib dapat ditelusuri kembali ke requirement.

Contoh:

```text
Executive Command Center

↓

AEP-050

↓

ASF-BUILD-050

↓

ASF-IMPLEMENTATION-003

↓

intelligence/executive-intelligence/

↓

apps/web/features/executive-dashboard/

↓

tests/integration/executive/
```

---

# 6. Pull Request Requirements

Setiap Pull Request wajib mencantumkan:

* AEP Reference
* ASF-BUILD Reference
* ASF-IMPLEMENTATION Reference
* Repository Module
* Test Result

Contoh:

```text
AEP Reference:
AEP-043

ASF-BUILD:
ASF-BUILD-043

Implementation:
ASF-IMPLEMENTATION-004

Module:
intelligence/sales-intelligence

Tests:
✔ Unit
✔ Integration
```

---

# 7. Test Traceability

Setiap requirement harus memiliki minimal:

* Unit Test
* Integration Test

Untuk fitur kritikal juga wajib memiliki:

* Security Test
* Performance Test
* End-to-End Test

---

# 8. Architecture Decision Mapping

Jika sebuah requirement membutuhkan keputusan arsitektur baru, maka wajib memiliki referensi ADR.

Contoh:

```text
ASF-IMPLEMENTATION-003

↓

ADR-004 Agent Runtime

↓

Implementation
```

---

# 9. Documentation Rule

Tidak boleh ada:

* Source code tanpa AEP.
* Source code tanpa ASF-BUILD.
* Source code tanpa ASF-IMPLEMENTATION.
* Source code tanpa pengujian.
* Source code tanpa dokumentasi.

---

# 10. Repository Audit Checklist

Sebelum release, pastikan:

* Semua requirement memiliki status yang benar.
* Semua modul memiliki mapping.
* Semua source code memiliki referensi requirement.
* Semua pengujian telah selesai.
* Semua dokumentasi diperbarui.

---

# 11. Traceability Lifecycle

```text
Vision

↓

Capability

↓

Architecture

↓

Implementation

↓

Verification

↓

Release

↓

Maintenance

↓

Evolution
```

Dokumen ini harus diperbarui setiap kali ada requirement baru, perubahan arsitektur, atau implementasi baru.

---

# 12. Implementation Log — Modul Aktual

Bagian ini memetakan modul yang **sudah diimplementasikan** di repository (bukan template).

## 12.1 Portal Self-Service Karyawan (`backend/app/modules/ess`)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Self-service karyawan: profil, kontrak, dokumen, slip gaji, absensi, cuti |
| Source Code | `backend/app/modules/ess/{models,schemas,service,router}.py` |
| API Karyawan (`/me/*`) | profile, contracts (+download-url), documents (+download-url), payslips, attendance, leave-requests (POST/GET/cancel) |
| API HR (`/employees/*`) | selfservice-accounts, leave-requests (list + decision) |
| Frontend | `frontend/src/pages/MyPortal.tsx` (route `/portal-saya`, role karyawan); kelola akun & approval cuti di `Employees.tsx` |
| Keamanan | Data selalu dari akun login (`Employee.user_id`); platform_admin diblokir; payslip hanya run final; download diverifikasi kepemilikan + audit log |
| Migrasi | `a7f2d94c1e58` (kolom `employees.user_id`), `b3c8e5a2f741` (tabel `leave_requests`), `c5d1f8a9b263` (tabel `leave_balances`) |
| Test | `backend/tests/test_ess.py` |

### 12.2 Jatah Cuti Tahunan

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Kuota cuti tahunan per karyawan per periode; approval memotong kuota |
| Source Code | `backend/app/modules/ess` (`LeaveBalance`, service, router) |
| API HR | `POST/GET /employees/{id}/leave-balance` |
| API Karyawan | `GET /me/leave-balance` |
| Frontend | Form "Jatah Cuti Tahunan" di `Employees.tsx`; kartu "Sisa Cuti Tahunan" di `MyPortal.tsx` |
| Aturan | Hanya `cuti_tahunan` memotong kuota; sisa kurang → approval 422; tanpa balance → tak dibatasi |

### 12.3 Notifikasi Cuti & Ekspor Rekap

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Notifikasi in-app alur cuti; ekspor CSV rekap cuti/absensi untuk HR |
| Source Code | `backend/app/modules/notifications`, fungsi CSV di `backend/app/modules/ess/service.py` |
| API Karyawan | `GET /me/notifications`, `GET /me/notifications/unread-count`, `POST .../{id}/read`, `POST .../read-all` |
| API HR | `GET /employees/reports/leave?year=`, `GET /employees/reports/attendance?year=&month=` (CSV `;`) |
| Frontend | Kartu "Notifikasi" di Portal Saya; tombol "Unduh CSV Cuti/Absensi" di halaman Karyawan |
| Migrasi | `d6e3f2a8c471` (tabel `notifications`) |

### 12.4 Aplikasi Mobile — Tab Portal

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Konsumsi endpoint portal `/me/*` di aplikasi Flutter internal staff |
| Source Code | `mobile/lib/screens/portal_tab.dart`, model di `mobile/lib/models/models.dart`, tab terdaftar di `home_shell.dart` (role karyawan + admin) |
| Cakupan | Profil ringkas, sisa cuti, form ajukan/batal cuti, slip gaji, notifikasi (tandai dibaca) |
| Build | Butuh Flutter SDK; jalankan `flutter create . --org id.aeos` dulu (lihat AGENTS.md) — verifikasi build di mesin dengan SDK |

### 12.5 Lampiran Cuti, Koreksi Absensi, Email Notifikasi

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Lampiran berkas pada pengajuan cuti; koreksi absensi oleh karyawan; notifikasi email opsional |
| Source Code | `backend/app/modules/ess` (model/service/router), `backend/app/modules/notifications/service.py`, `backend/app/core/config.py` |
| API Karyawan | `POST /me/leave-requests/{id}/attachment` (+download-url), `GET|POST /me/attendance-corrections` (+cancel) |
| API HR | `GET /employees/leave-requests/{id}/attachment/download-url`, `GET /employees/attendance-corrections?status=`, `PATCH .../{id}/decision` |
| Frontend | Kartu "Koreksi Absensi" di Portal Saya; tabel "Koreksi Absensi (Portal)" + tombol lampiran di halaman Karyawan |
| Aturan | Lampiran hanya saat menunggu (≤10 MB); koreksi disetujui menerapkan angka ke AttendanceSummary & reset approval klien; email hanya aktif bila SMTP_HOST diisi |
| Migrasi | `e8b4c7d1a952` (kolom lampiran), `f9c2e6b8d314` (tabel attendance_corrections) |

### 12.6 Fase 7 — Entitlement Multi-App (irisan 1)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | App registry + lisensi per tenant + guard 403 + nav dinamis & launcher |
| Source Code | `backend/app/core/apps.py`, modul `apps`, lisensi di modul `platform`; frontend `Apps.tsx`, `Layout.tsx`, `PlatformTenants.tsx` |
| API Tenant | `GET /apps`, `POST /apps/{key}/trial` (14 hari, sekali per app) |
| API Platform | `GET|PATCH /platform/tenants/{id}/licenses/{app_key}` |
| Aturan | Tanpa lisensi → 403 semua endpoint aplikasi tsb; provisioning baru mulai kosong; tenant default/dev full package; migrasi seed tenant lama |
| Migrasi | `a1b2c3d4e5f6` (tabel tenant_app_licenses + seed) |

### 12.7 Fase 7 — Design System Notion-style (irisan 2)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Token desain Notion (Inter/warm text/border halus), dark mode, shell baru dengan grup aplikasi + aksen, command palette ⌘K |
| Source Code | `frontend/tailwind.config.ts`, `src/index.css` (CSS variables + retro-fit dark), `src/components/Layout.tsx`, `src/components/CommandPalette.tsx`, `index.html` |
| Catatan | Dark memakai aturan pemetaan kelas slate-* agar seluruh halaman lama ikut tanpa rewrite; view papan/callout block masuk polish Fase 7 berikutnya |

### 12.8 Fase 7 — Kanban Pipeline & Properti Notion (irisan 3)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | View papan pipeline per tahapan, callout block, panel properti metadata ala Notion |
| Source Code | `frontend/src/components/notion.tsx`, `src/pages/Leads.tsx` + `Candidates.tsx` (toggle tabel/papan), `src/pages/Employees.tsx` (header properti + callout reminder); `PageHeader` konsisten di semua halaman |

### 12.9 Fase 8 — Absensi Harian (Clock-in/out)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Record harian clock-in/out, impor CSV fingerprint, validasi dua jalur, agregasi bulanan otomatis, integrasi ESS |
| Source Code | `backend/app/modules/attendance/{models,schemas,service,router}.py`, kolom `employees.employment_type`, guard `require_any_licensed_app` |
| API HR/Ops (`/attendance`) | `GET /attendance/template`, `GET /attendance/records?year=&month=`, `POST /attendance/records`, `POST /attendance/import`, `POST /attendance/summaries/{id}/validate?lane=` |
| Integrasi | Cuti/izin ESS disetujui → record harian otomatis (source `ess`); tidak menimpa record manual/impor |
| Aturan | Dua jalur: internal→HR, eksternal→Ops/klien; angka berubah me-reset approval; impor: template ; + laporan baris gagal |
| Frontend | Halaman "📅 Absensi" (`/attendance`) — periode picker, rekap + tombol Validasi, form manual, panel impor + tabel gagal, daftar harian |
| Migrasi | `b4d5e6f7a8b9` (tabel `attendance_records` + kolom `employment_type`) |
| Test | `backend/tests/test_attendance.py` |

### 12.10 Rates Ber-versi + ADR-0006 Guard Payrol

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Rate pajak/BPJS/billing/bank fee terpisah dari kode, ber-versi per tanggal efektif; snapshot historis |
| Source Code | `backend/app/modules/rates/*`, integrasi di `payroll/{tax,service}.py`, `bpjs/{engine,service}.py`, `finance/service.py`, `payroll/models.py` (snapshot) |
| API | `GET/POST /rates/pph21`, `/rates/bpjs`, `/rates/billing` (POST admin/finance/management), `GET/POST /rates/bank-fees`; duplikat tanggal 409 |
| Integrasi | Slip gaji: PPh21 dari config efektif + potongan bank fee otomatis; BPJS recap per periode; invoice memakai PPN/PPh23/due_days versi; snapshot JSON tersimpan di `payroll_runs` |
| Frontend | Halaman "🧮 Tarif & Rate" (`/rates`) — 4 tab: tabel versi + form buat versi baru + edit fee bank inline |
| Keputusan | **ADR-0006**: guard lisensi payrol per `run_type` (shell OR, mutasi per objek) — dieksekusi di Fase 9 irisan a |
| Migrasi | `g1h2i3j4k5l6` (4 tabel rate + kolom snapshot `payroll_runs` + seed 2025-01-01) |
| Test | `backend/tests/test_rates.py` |

### 12.11 Fase 9a — Payrol Dua Jalur & Approval Klien Ber-Token

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Payrol internal vs proyek per klien; state machine PRD; approval klien via link ber-token tanpa akun |
| Source Code | `backend/app/modules/payroll/{models,schemas,service,router}.py` (`PayrollRunType`, `PayrollRunToken`, transisi `_ALLOWED_TRANSITIONS`, `assert_run_license`) — sesuai **ADR-0006** |
| API Internal | `POST /payroll/runs` (run_type=internal) · `/start-processing` · `/finalize` (draft/finance_processing) |
| API Proyek | `POST /payroll/runs?run_type=proyek&client_id=` · `/submit-to-client` (token 1–90 hari) · publik `GET|POST /payroll/client/{token}[/decision]` |
| Guard | Shell OR dua lisensi; mutasi divalidasi lisensi per run_type (403 menyebut aplikasi); BPJS recap any-of |
| Frontend | Halaman Payroll: pilih jenis/klien, badge 6 status, aksi kontekstual, callout link approval + salin URL |
| Integrasi ESS | Generate slip proyek difilter placement→job order→klien; lembur tetap butuh approval klien di rekap absensi |
| Migrasi | `h9i0j1k2l3m4` (kolom run_type/client_id + tabel payroll_run_tokens) |
| Test | `backend/tests/test_payroll_dua_jalur.py` (7 skenario) |
| Sisa Fase 9 | Saltab grid line-item + prorata, BPJS dua sisi ke invoice, Payment Request workflow, invoice/jurnal otomatis (irisan b–c, terkait Fase 10) |

### 12.12 Fase 9b-c — Saltab Line-item, BPJS Dua Sisi & Payment Request

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Grid Saltab line-item + prorata absensi + BPJS dua sisi; invoice draft otomatis saat klien approve; workflow Payment Request |
| Source Code | `payroll/{models,schemas,service}.py` (`PayslipComponent`, saltab), `finance/{models,schemas,service,router}.py` (`PaymentRequest`) |
| API Saltab | `GET /payroll/runs/{id}/saltab` · `PATCH /payroll/saltab/components/{id}` (override manual ber-audit) · `GET .../saltab/export` (CSV) |
| API PR | `GET|POST /payment-requests` · `POST /{id}/approve|reject|execute` (approve: management; execute: finance/management) |
| Aturan | Prorata & BPJS opt-in per generate; THP = Σ pemasukan − Σ potongan; BPJS employer pass-through ditagih ke klien; override manual recompute agregat + audit; tolak PR wajib catatan |
| Migrasi | `i0j1k2l3m4n5` (tabel `payslip_components` + `payment_requests`) |
| Test | `backend/tests/test_saltab.py`, `backend/tests/test_payment_request.py` |
| Sisa Fase 9 | Ekspor Excel/PDF (CSV tersedia); rantai approval multi-level configurable |

### 12.13 Fase 10 (core) — Accounting ala Accurate

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Bagan akun dinamis + template; jurnal memorial→posted; periode & tutup buku; mesin auto-journal idempoten; laporan berbasis akun DB + laba rugi per klien |
| Source Code | `backend/app/modules/accounting/*` (`Account`, `AccountingPeriod`, `JournalRule`, status jurnal), integrasi hook di `finance/service.py` & `payroll/service.py` |
| API | `GET|POST /accounting/accounts`, `PATCH/DELETE /accounts/{id}` · `GET /periods`, `POST /periods/{y}/{m}/close|reopen` · `POST /journal` (status memorial/posted) · `POST /journal/{id}/post` · laporan existing + `GET /reports/profit-by-client` |
| Aturan | Saldo akun tidak disimpan (dihitung dari jurnal posted); backdate periode tertutup ditolak; auto-journal idempoten (unique event+ref) dan melewati periode tertutup |
| Migrasi | `j1k2l3m4n5o6` (tabel accounts/accounting_periods/journal_rules, kolom status & account_id & dimensi, data migration map baris legacy → COA) |
| Test | `backend/tests/test_accounting_fase10.py` |
| Sisa Fase 10 | Kas-bank & rekonsiliasi, pembelian, aset tetap + penyusutan otomatis, arus kas tidak langsung, AI akuntansi (§8.8) |

---

# End of Requirement Traceability Matrix
