# Changelog

Semua perubahan penting pada AI Enterprise OS dicatat di sini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/).

## [Unreleased]

### Added — Rates ber-versi untuk pajak, BPJS, billing, bank fee (NFR §11)

- **Tabel rate ber-versi** (`pph21_configs`, `bpjs_configs`, `billing_tax_configs`, `bank_fee_configs`) dengan `effective_from` — tarif terpisah dari kode, versi dicatat per periode agar laporan historis konsisten. Migrasi `g1h2i3j4k5l6` (seed 2025-01-01 dari konstanta kode).
- **Payroll & BPJS memakai DB**: `TaxProfile.from_db(db, effective_date)` dan `compute_contribution(db, effective_date)` → fallback ke konstanta bila DB kosong; snapshot `pph21_snapshot`/`bpjs_snapshot` disimpan di `payroll_runs` saat generate.
- **Billing**: `generate_invoice` memakai `billing_tax_configs` efektif per periode (PPN/PPh23/due_days) dengan fallback `finance/tax_config.py`.
- **Bank fee**: `POST/GET /rates/bank-fees` — potongan admin otomatis di slip gaji (non-Mandiri, default Rp 3.500, configurable per bank). Endpoint `GET /rates/{pph21,bpjs,billing}` list, `POST` buat versi baru (admin/finance/management).
- **CRUD rates**: `GET /rates/{pph21,bpjs,billing,bank-fees}` + `POST` (admin) — versi untuk tanggal yang sama ditolak 409.
- **Halaman "🧮 Tarif & Rate"** (`/rates`, role admin/finance/management): tab PPh21/BPJS/Billing/Bank Fee, tabel riwayat versi + form buat versi baru (bracket JSON), edit fee bank inline.
- **ADR-0006** — guard lisensi payrol per `run_type`: shell `/payroll` menjadi OR (`hr_payroll` ATAU `operations_billing`), mutasi divalidasi per objek; BPJS recap tetap any-of.

### Added — Fase 8: Absensi Harian (Clock-in/out)

- **Model harian `AttendanceRecord`** (`date`, `clock_in`, `clock_out`, `overtime_hours`, `status`, `source`, `notes`) dengan unique `(employee_id, date)`; kolom `employees.employment_type` (`internal/eksternal`, default eksternal). Migrasi `b4d5e6f7a8b9`.
- **Guard multi-app**: absensi dilindungi `require_any_licensed_app("hr_payroll", "operations_billing")` — cukup salah satu aplikasi berlisensi.
- **Input manual + agregasi otomatis**: `POST /attendance/records` upsert satu hari langsung menghitung ulang `AttendanceSummary` bulanan; angka berubah me-reset approval (`client_approved`).
- **Impor CSV mesin fingerprint**: template `GET /attendance/template` (delimiter `;`), upload `POST /attendance/import` mengembalikan `{inserted, updated, failed[]}` dengan laporan baris gagal.
- **Validasi dua jalur**: `POST /attendance/summaries/{id}/validate?lane=hr|klien` — internal divalidasi HR, eksternal divalidasi Operations/klien; endpoint legacy `/payroll/attendance/.../client-approval` kini menolak karyawan internal (422).
- **Integrasi ESS**: cuti/izin yang disetujui di portal otomatis membuat record harian ber-status `cuti/izin/sakit` (source `ess`, tidak menimpa record manual/impor).
- **Halaman Absensi** (`/attendance`, nav "📅 Absensi"): periode picker, rekap bulanan + tombol Validasi HR / Approval Klien, form input manual, panel impor CSV dengan tabel baris gagal, daftar record harian.
- Tes: CRUD + agregasi, dua jalur, impor CSV dengan baris gagal, template, sinkron cuti ESS.

### Added — Fase 7: View Papan, Callout & Properti Notion (bagian 3 dari 3)

- **View papan/kanban Pipeline**: toggle "Tabel | Papan" di halaman Pipeline; kolom per tahapan dengan jumlah lead + total nilai potensi, kartu lead dengan tombol pindah tahap cepat (←/→) dan dropdown tahapan.
- **Primitif komponen ala Notion** (`src/components/notion.tsx`): `PageHeader` (emoji besar + judul), `CalloutBlock` (4 tone berwarna lembut), `PropertyRow`/`PropertiesPanel` (properti metadata dengan pemisah putus-putus).
- **Properti metadata pada halaman detail**: detail lead terpilih dan header karyawan terpilih kini memakai panel properti ala Notion; reminder kontrak berubah menjadi callout warning.
- Fase 7 selesai penuh (entitlement, guard, launcher, design system, kanban pipeline + kandidat, properti & emoji judul).

### Added — Fase 7: Design System Notion-style (bagian 2 dari 3)

- **Token desain**: font Inter, teks hangat `#37352F`, border/hover sangat halus, radius kecil, sidebar abu lembut (`#f7f6f3`) — semua via CSS variables di `index.css`.
- **Dark mode paralel** dengan toggle 🌙/☀️ di sidebar (tersimpan di localStorage); aturan retro-fit memetakan kelas slate-* lama agar seluruh halaman ikut gelap tanpa rewrite per file.
- **Shell baru**: sidebar workspace dengan grup per aplikasi berlisensi (aksen warna khas tiap app pada item aktif), topbar breadcrumb (Workspace / App / Halaman + emoji), tombol ⌘K.
- **Command palette ⌘K**: cari & lompat ke halaman/aplikasi apa pun, navigasi panah + Enter, termasuk aksi ganti tema.
- Irisan tersisa Fase 7 (polish): view papan (kanban pipeline), callout block, properti metadata ala Notion.

### Added — Fase 7: Entitlement Multi-App (bagian 1 dari 3)

- **App registry** (`app/core/apps.py`): 7 aplikasi portofolio (Sales CRM, Recruitment, HR & Payroll, Operations & Billing, Finance & Accounting, E-Sign, AI Add-on) dengan metadata, dependensi, dan pemetaan prefix route — single source of truth.
- **Lisensi per tenant**: tabel `tenant_app_licenses` (status `trial/aktif/kedaluwarsa`, trial 14 hari sekali per aplikasi). Migrasi `a1b2c3d4e5f6`; tenant lama di-seed paket penuh.
- **Guard backend 403**: endpoint aplikasi tanpa lisensi ditolak; dipasang via `include_router(dependencies=[...])`. Tenant provisioning baru kini mulai tanpa lisensi — admin mengaktifkan trial mandiri dari menu Aplikasi; tenant default/dev tetap full package.
- **API**: `GET /apps` (nav dinamis + launcher), `POST /apps/{key}/trial` (admin/management), `GET|PATCH /platform/tenants/{id}/licenses/{app_key}` (platform admin).
- **Frontend**: halaman "Aplikasi" (launcher + upsell trial 14 hari), nav sidebar dinamis mengikuti lisensi, editor lisensi per tenant di halaman platform.
- Tes: pemetaan registry, guard 403 + pemulihan, alur trial/provisioning/expiry.

> Irisan berikutnya Fase 7: design system Notion-style (shell baru, ⌘K, dark mode) — sesi terpisah.

### Added — Lampiran Surat Sakit, Koreksi Absensi, dan Email Notifikasi

- **Lampiran pengajuan cuti**: karyawan dapat mengunggah berkas pendukung (mis. surat dokter, maks. 10 MB) pada pengajuan berstatus menunggu via `POST /me/leave-requests/{id}/attachment`; unduh lewat `/me/.../attachment/download-url` (karyawan) atau `/employees/leave-requests/{id}/attachment/download-url` (HR). Migrasi `e8b4c7d1a952`.
- **Koreksi absensi oleh karyawan**: alur ajukan → approval HR. Karyawan mengusulkan angka hadir/lembur per periode (`POST /me/attendance-corrections`); saat disetujui angka diterapkan ke rekap absensi dan approval klien di-reset agar diverifikasi ulang. Duplikat pending per periode ditolak. Migrasi `f9c2e6b8d314`.
- **Email notifikasi (opsional)**: isi `SMTP_HOST` (+ port/user/password/from) untuk meneruskan notifikasi keputusan/pengajuan ke email penerima; dikirim fire-and-forget di thread terpisah, gagal SMTP tidak memengaruhi bisnis. Tanpa SMTP_HOST fitur nonaktif.
- UI: kartu "Koreksi Absensi" di Portal Saya; tabel "Koreksi Absensi (Portal)" di halaman Karyawan; tombol lampiran di kedua sisi.
- Tes: alur lampiran (upload/unduh/isolasi/kunci setelah diputus) dan koreksi absensi (approve menerapkan angka, reset approval klien, duplikat 409).

### Added — Notifikasi & Ekspor CSV

- Modul `notifications` (tabel `notifications`, migrasi `d6e3f2a8c471`) dengan endpoint `/me/notifications`: daftar, unread-count, tandai dibaca per item, dan read-all.
- Pengajuan cuti/izin kini menotifikasi semua akun admin & HR tenant; keputusan HR (setujui/tolak) menotifikasi karyawan pemohon lewat portal.
- Ekspor CSV untuk HR di `/employees/reports/*` (pola sama dengan ekspor BPJS, delimiter `;`):
  - `GET /employees/reports/leave?year=` — rekap pengajuan cuti satu tahun.
  - `GET /employees/reports/attendance?year=&month=` — rekap kehadiran/lembur.
- Tombol unduh CSV di kartu "Pengajuan Cuti / Izin" halaman Karyawan; kartu "Notifikasi" di Portal Saya.

### Added — Jatah Cuti Tahunan (kuota)

- Model `LeaveBalance` (per karyawan per tahun) + migrasi `c5d1f8a9b263`.
- HR: `POST|GET /employees/{id}/leave-balance` untuk mengatur/melihat jatah; UI form di halaman Karyawan.
- Approval cuti tahunan otomatis memotong kuota dan ditolak (422) bila sisa tidak cukup; izin/sakit/unpaid bebas kuota; tanpa baris balance, approval tidak dibatasi (opt-in HR).
- Portal: kartu "Sisa Cuti Tahunan" via `GET /me/leave-balance`.
- Tes: alur potong kuota, penolakan melebihi jatah, kenaikan jatah, proteksi jatah di bawah pemakaian.

### Added — Portal Self-Service Karyawan (v2)

- Modul backend `ess` dengan endpoint `/api/v1/me/*`:
  - `GET /me/profile` — data pribadi karyawan.
  - `GET /me/contracts`, `GET /me/contracts/{id}/download-url` — kontrak kerja.
  - `GET /me/documents`, `GET /me/documents/{id}/download-url` — dokumen HR.
  - `GET /me/payslips` — slip gaji dari payroll run final saja.
  - `GET /me/attendance` — rekap kehadiran bulanan sendiri.
  - `POST|GET /me/leave-requests`, `POST /me/leave-requests/{id}/cancel` — pengajuan cuti/izin beserta pembatalan saat masih menunggu.
- Endpoint HR di `/api/v1/employees/*`:
  - `PATCH /employees/{id}` kini menerima `user_id` untuk menaut/melepas akun login self-service (validasi role, tenant, dan kepemilikan).
  - `GET /employees/selfservice-accounts` — daftar akun role karyawan yang belum tertaut.
  - `GET /employees/leave-requests?status=` dan `PATCH /employees/leave-requests/{id}/decision` — approval cuti/izin.
- Halaman frontend **Portal Saya** (`/portal-saya`) untuk role `karyawan`: profil, kontrak, dokumen, slip gaji, rekap kehadiran, form cuti/izin, dan ganti password sendiri. Login role karyawan langsung diarahkan ke portal.
- Halaman **Karyawan**: kartu "Akun Portal Karyawan" (aktifkan/lepas tautan) dan tabel "Pengajuan Cuti / Izin" (setujui/tolak).
- Migrasi: `a7f2d94c1e58` (kolom `employees.user_id`), `b3c8e5a2f741` (tabel `leave_requests`).
- Tes: `backend/tests/test_ess.py` mencakup isolasi data antar karyawan, blokir platform_admin, alur cuti lengkap, dan tautan akun via HR.

### Security

- Semua endpoint `/me/*` hanya melayani data milik akun login (resolusi via `Employee.user_id`), tanpa parameter employee_id dari klien; akses lintas karyawan mengembalikan 404.
- Unduhan dokumen/kontrak lewat portal diverifikasi kepemilikannya dan tercatat sebagai event audit (`ess.*`).

## [0.2.0]

### Added

- Modul HRD, Payroll (+ mesin PPh21 TER/Pasal 17), BPJS, E-Sign, Akunting, Finance, Audit, AI (RAG kontrak & forecast).
- Multi-tenant shared-schema dengan RLS PostgreSQL dan middleware konteks tenant.
- Platform admin: provisioning tenant via `/platform/*`.
