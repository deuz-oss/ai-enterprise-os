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

---

# End of Requirement Traceability Matrix
