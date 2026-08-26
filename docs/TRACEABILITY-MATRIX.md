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

### 12.17 Fase 10 — AI Layer Akuntansi (§8.8)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Asisten tutup buku, deteksi anomali & kepatuhan, kategori bill cerdas, narasi eksekutif, tanya laporan |
| Source Code | `backend/app/modules/accounting/ai_accounting.py`, endpoint di `accounting/router.py` |
| API | `GET /ai/close-checklist?year=&month=` · `GET /ai/anomalies?year=&month=` · `POST /ai/categorize-bill` · `GET /ai/executive-summary?year=[&month=]` · `POST /ai/ask` |
| Aturan | Checklist & anomali 100% deterministik (tanpa LLM); narasi/tanya-laporan memakai LLM sebagai lapisan bahasa di atas angka terverifikasi dengan fallback template; kategori berbasis keyword + riwayat vendor |
| LLM | Opsional via AI_BASE_URL; tanpa konfigurasi semua fitur tetap berfungsi kecuali narasi natural |

### 12.18 Fase 11 — Chat Workspace (gratis, WebSocket real-time — v1 REST polling)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Channel public/private/dm/broadcast + pesan thread + soft delete + reaksi emoji + unread per karyawan; akses ter-scope per proyek |
| Source Code | `backend/app/modules/chat/*`, migrasi `l3m4n5o6p7q8` |
| API | `GET|POST /chat/channels` · `POST /channels/{id}/members` · `GET|POST /channels/{id}/messages` · `PATCH|DELETE /messages/{id}` · `POST /messages/{id}/react` · `POST /channels/{id}/read-all` |
| Aturan | Channel gratis tanpa guard lisensi; akses dipaksakan server-side — karyawan hanya melihat channel di mana dia member; broadcast hanya Ops/admin bisa posting; thread via parent_id; polling v1, WebSocket pluggable menyusul |
| Frontend | Halaman Chat `/chat` (nav 💬 Chat): dua panel channel+pesan, thread view, reaksi per pesan, edit/hapus, polling, unread badge |
| Test | `backend/tests/test_chat.py` |

### 12.19 Fase 11 — Chat Lanjutan: Auto Channel & Card Interaktif + WebSocket

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Channel otomatis per job order / payroll periode / proyek; kartu interaktif PR & payroll ber-tombol aksi; WebSocket real-time |
| Source Code | `backend/app/modules/chat/service.py` (`ensure_*_channel`, `send_card_message`, `handle_card_action`), `ws_manager.py` |
| API | `POST /chat/messages/{id}/actions/{action_id}` · `WS /chat/ws?token=` |
| Aturan | Card PR: approve/reject/execute → `decide_payment_request`; channel #jo- / #proyek- / #payroll- dibuat idempoten via slug; WebSocket manager pluggable (in-memory v1, Redis pub/sub menyusul) |
| Test | `backend/tests/test_chat_sisa.py` |

### 12.16 Fase 10 — AI Layer Akuntansi (§8.8)

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Asisten tutup buku, deteksi anomali & kepatuhan, kategori bill cerdas, narasi eksekutif, tanya laporan |
| Source Code | `backend/app/modules/accounting/ai_accounting.py`, endpoint di `accounting/router.py` |
| API | `GET /ai/close-checklist?year=&month=` · `GET /ai/anomalies?year=&month=` · `POST /ai/categorize-bill` · `GET /ai/executive-summary?year=[&month=]` · `POST /ai/ask` |
| Aturan | Checklist & anomali 100% deterministik (tanpa LLM); narasi/tanya-laporan memakai LLM sebagai lapisan bahasa di atas angka terverifikasi dengan fallback template; kategori berbasis keyword + riwayat vendor |
| LLM | Opsional via AI_BASE_URL; tanpa konfigurasi semua fitur tetap berfungsi kecuali narasi natural |

### 12.15 Fase 10 lanjutan — Kas & Bank, Pembelian, Aset Tetap, Arus Kas

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Kas-bank transaksi + rekonsiliasi; pembelian bill vendor; aset tetap garis lurus + penyusutan idempoten + disposisi; arus kas metode tidak langsung |
| Source Code | `backend/app/modules/accounting/transactions_{service,router,schemas}.py` |
| API | `GET|POST /accounting/cashbank/transactions` (+reconcile) · `GET|POST /accounting/purchases` (+pay) · `GET|POST /accounting/assets` (+depreciate/dispose) · `GET /reports/cash-flow-indirect?year=` |
| Aturan | Setiap transaksi membentuk jurnal otomatis via post_auto_event; penyusutan idempoten per aset per bulan (dibatasi sisa nilai buku); disposisi gain/loss ke pendapatan/beban lain; rekonsiliasi manual |
| Frontend | Tab "Kas & Bank" / "Pembelian" / "Aset Tetap" di halaman Akunting + laporan arus kas tidak langsung |
| Migrasi | `k2l3m4n5o6p7` (3 tabel: bank_transactions/purchase_bills/fixed_assets) |
| Test | `backend/tests/test_fase10_transactions.py` |

### 12.20 Saltab Export Excel/PDF + Pencarian & Mention Chat

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Ekspor Saltab ke Excel/PDF; pencarian pesan chat; autocomplete mention ter-scope |
| Source Code | `backend/app/modules/payroll/{service,router}.py` (openpyxl/reportlab), `backend/app/modules/chat/{service,router}.py` |
| API | `GET /payroll/runs/{id}/saltab/export-excel|export-pdf` · `GET /chat/search?q=` · autocomplete mention di endpoint pesan |
| Frontend | Tombol unduh Excel/PDF di halaman Payroll; kotak cari + saran mention di halaman Chat |
| Aturan | Karyawan tetap hanya bisa menyebut/menemukan user dalam scope proyeknya |

### 12.21 Fase 9 penutup — Rantai Approval PR Multi-level per Tenant

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Urutan tahap approval Payment Request configurable per tenant (PRD §7: "rantai configurable, contoh COO") |
| Source Code | `backend/app/modules/finance/models.py` (`PRApprovalStep`, `PaymentRequestApproval`), `finance/service.py` (`get/set_approval_chain`, `decide_payment_request` multi-tahap) |
| API | `GET|PUT /payment-requests/approval-chain` (PUT admin/management); daftar PR kini memuat `progress` (tahap berjalan + riwayat keputusan) |
| Aturan | Tiap tahap = user spesifik atau peran staf; hanya approver tahap berjalan bisa memutus (403 bila bukan); setujui tahap non-akhir → lanjut + notifikasi approver berikutnya; tolak → PR gugur; tanpa rantai → legacy (management/admin mana pun); kartu chat ikut tervalidasi |
| Migrasi | `n4o5p6q7r8s9` (tabel `pr_approval_steps` + `pr_approvals`) |
| Frontend | Panel "Rantai Approval" + badge progres Tahap X/Y di halaman Payment Request |
| Test | `backend/tests/test_payment_request.py` (+3 skenario rantai) |

### 12.22 Fase 10 sisa AI — OCR Faktur, Rekonsiliasi Bank Cerdas, Prediksi Pembayaran

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | §8.8 #1 foto faktur → draft pembelian + saran COA; #2 impor rekening koran + matching fuzzy + alasan ketidakcocokan; #6 skor risiko telat bayar klien → prioritas collection |
| Source Code | `accounting/ai_accounting.py` (`ocr_extract_bill`, `predict_client_payments`), `accounting/bank_statement.py` (impor + matching deterministik), `app/core/llm.py` (`vision_completion`) |
| API | `POST /accounting/ai/ocr-bill` (multipart gambar; 503 bila AI tak dikonfigurasi) · `GET /cashbank/statement/template` · `POST /cashbank/statement/import` (CSV, lapor baris gagal/duplikat) · `GET /cashbank/statement` · `POST /cashbank/statement/{id}/match` · `POST /cashbank/statement/{id}/ignore` · `GET /accounting/ai/payment-prediction` |
| Aturan | OCR satu panggilan vision LLM → DRAFT saja (bill tetap dibuat via endpoint pembelian); matching 100% deterministik: nominal (toleransi ≤0,5%) 60% + jarak tanggal ≤14 hari 25% + kemiripan token deskripsi 15%, ambang usulan 75%; konfirmasi match menandai transaksi terekonsiliasi & membersihkan usulan basi baris lain; prediksi: rasio telat 60% + avg delay 40% (+10 overdue berjalan), prioritas = outstanding × risiko |
| Model | `BankStatementLine` (`bank_statement_lines`, migrasi `o5p6q7r8s9t0`) |
| Frontend | Tab "🤖 AI & Rekonsiliasi" halaman Akunting: Scan Faktur, Rekonsiliasi Bank Cerdas, Prediksi Pembayaran Klien |
| Test | `backend/tests/test_fase10_ai_sisa.py` (prediksi ranking, impor+match+confirm+ignore, baris gagal/duplikat, validasi OCR) |

### 12.23 Fase 13 — Talent Pool & CV Standardization

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Pipeline CV → profil terstruktur berversi → review recruiter (confidence) → PDF CV standar bertemplate branding tenant; facet talent pool; hak hapus UU PDP; snapshot submission (PRD §10) |
| Source Code | `backend/app/modules/talentpool/{models,schemas,service,router}.py`; hook lock di `recruitment/service.py::create_placement` |
| API | `POST /talentpool/intake` (multipart + consent UU PDP) · `GET /talentpool/intake/{id}` · `POST .../review` · `POST .../finalize` · `POST .../reprocess` · `GET /talentpool` (facet q/domisili/skill/readiness/tp_status/has_standard_cv) · `GET /talentpool/cv-versions/{id}/download` · `GET|PUT /talentpool/branding` · `POST /talentpool/candidates/{id}/forget` |
| Aturan | Deteksi jenis dokumen: pdf teks vs scan (pypdf ≥40 char), DOCX (python-docx), gambar; scan/gambar → satu panggilan vision LLM; skema tetap berversi (SCHEMA/PROMPT_VERSION); confidence per kelompok dikoreksi deterministik (regex email/telepon, kelengkapan array); < 0.7 = wajib review — finalisasi diblokir selama belum dicek; file asli tak pernah ditimpa; tiap finalize = versi baru snapshot PDF; placement baru mengunci versi terbaru (bukti submission); intake gagal tetap tersimpan & bisa diproses ulang; forget menghapus profil/snapshot + scrub PII kandidat |
| Guard | Lisensi aplikasi `recruitment`; role recruiter/operations/hr/management; branding PUT admin/management |
| Migrasi | `p6q7r8s9t0u1` (`cv_intakes`, `standard_cv_versions`, `tenant_cv_branding`) |
| Frontend | Halaman "🧬 Talent Pool" (`/talent-pool`, nav Recruitment): unggah+consent, facet filter, tabel status TP, panel review (highlight wajib cek, koreksi inline), unduh versi PDF |
| Test | `backend/tests/test_talentpool.py` (8 skenario: validasi consent/format, gagal-tanpa-AI + reprocess, pipeline mocked→finalize→PDF, blokir finalize sebelum review, facet+hak hapus, lock saat placement, branding, unit normalize_and_score) |

### 12.24 Fase 8 lanjutan — Mobile GPS+selfie Absensi

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Clock-in/out dari app mobile dengan bukti selfie kamera depan + koordinat GPS (PRD Fase 8) |
| Source Code | `ess/service.py` (`mobile_clock`, `_save_selfie`, `own_selfie_url`), kolom baru `attendance_records` (geo+selfie key per arah), migrasi `q7r8s9t0u1v2` |
| API | `POST /me/attendance/clock-in|clock-out` (multipart: file selfie + latitude/longitude) · `GET /me/attendance/{id}/selfie/{in|out}/download-url` (pemilik) · `GET /attendance/records` kini memuat `*_geo` + `has_*_selfie` · `GET /attendance/records/{id}/selfie/{which}/download-url` (admin/hr/operations/management) |
| Aturan | Satu record/hari: clock-in kedua & clock-out ganda → 409; record manual/cuti hari ini memblokir clock-in; koordinat divalidasi rentang; selfie JPG/PNG ≤5 MB tersimpan di storage; notifikasi ke HR & Ops tiap clock; akses selfie HR terbatas role + audit log |
| Mobile | Tab "Absensi Saya" di Portal (`self_attendance_screen.dart`): izin lokasi (geolocator) → foto depan (image_picker) → unggah multipart (`postMultipart`); deps baru pubspec; verifikasi build butuh Flutter SDK (AGENTS.md) |
| Test | `backend/tests/test_mobile_absensi.py` (4 skenario: alur in/out + duplikat + flag HR, validasi akun/koordinat/format, blokir oleh record manual, hak akses selfie pemilik vs HR) |

### 12.25 Branding CV — Logo Perusahaan

| Aspek | Detail |
| ------------------------- | ------------------------------------------------------------------ |
| Capability | Logo tenant pada header CV standar (pelengkap §10.3 branding) |
| API | `POST /talentpool/branding/logo` (PNG/JPEG ≤2 MB, admin/management) · `DELETE .../branding/logo` · `GET /talentpool/branding/logo/download` (preview `<img>`) · `GET /branding` kini memuat `has_logo`+`logo_url` |
| Render | Logo diambil dari storage saat finalize; tinggi tetap 14 mm, lebar mengikuti rasio; logo rusak tidak menggagalkan render PDF |
| Frontend | Kartu "🎨 Branding CV Standar" di halaman Talent Pool (warna aksen, footer, unggah/hapus logo — admin/management) |
| Test | `backend/tests/test_talentpool.py::test_logo_upload_render_dan_hapus` (validasi format, upload, preview, finalize dengan logo, hapus) |

---

# End of Requirement Traceability Matrix
