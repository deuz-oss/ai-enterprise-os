# Changelog

Semua perubahan penting pada AI Enterprise OS dicatat di sini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/).

## [Unreleased]

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
