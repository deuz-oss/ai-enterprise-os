# Product Requirements Document (PRD)

**Produk:** Outsourcing Operating System (working title: AI Enterprise OS)
**Pemilik Produk:** Brian — Head of Business & Operations
**Versi:** 1.0 · **Status:** Approved for MVP development
**Terakhir diperbarui:** 2026-08-23

---

## 1. Ringkasan Eksekutif

Sistem manajemen end-to-end untuk perusahaan outsourcing (manpower services) yang
mencakup seluruh siklus bisnis: dari akuisisi klien, onboarding klien beserta dokumen
legalitasnya, rekrutmen tenaga kerja, administrasi HR karyawan, operasional payrol,
hingga finance dan akunting.

Sistem dibangun sebagai **aplikasi web internal** yang dipakai tim Business &
Operations sehari-hari, menggantikan proses manual berbasis spreadsheet dan WhatsApp.

## 2. Masalah yang Diselesaikan

| # | Masalah saat ini | Dampak |
|---|------------------|--------|
| 1 | Pipeline calon klien dicatat manual di spreadsheet | Prospek bocor, tidak ada visibilitas status |
| 2 | Dokumen legalitas (perjanjian kerjasama, addendum) tersebar di email/drive pribadi | Sulit diaudit, versi dokumen tidak jelas |
| 3 | Rekrutmen (job order → kandidat → placement) tanpa sistem terpusat | SLA pengiriman kandidat lambat, database kandidat tidak terpakai ulang |
| 4 | Kontrak & dokumen HR karyawan tidak terstruktur | Risiko kepatuhan ketika audit klien/Disnaker |
| 5 | Payrol, PPh21, approval klien, invoice, dan cash flow dihitung terpisah-pisah | Sering salah hitung, tagihan telat, arus kas tak terpantau |

## 3. Pengguna & Peran

| Peran | Deskripsi | Fitur utama |
|-------|-----------|-------------|
| Admin | Owner / IT | Semua modul + manajemen user |
| Business Dev | Sales/presales | Pipeline, data klien, upload dokumen legalitas |
| Recruiter | Tim rekrutmen | Job order, kandidat, onboarding karyawan |
| HR | Personalia | Kontrak karyawan, dokumen pegawai, database karyawan |
| Operations | Operasional | Payrol, PPh21, monitoring approval klien |
| Finance | Keuangan | Invoice, pajak, aging/overdue, cash flow |
| Management | Direksi/Brian | Dashboard ringkasan semua modul |

## 4. Ruang Lingkup per Fase

### Fase 1 — MVP: Pre-sales s/d Rekrutmen ✅ *sedang dibangun*

**M1. Pre-sales / Pipeline Klien**
- CRUD lead/prospek klien dengan tahapan pipeline:
  `lead → kontak → presentasi → penawaran → negosiasi → deal / gagal`
- Pencatatan aktivitas (call, meeting, follow-up) per lead
- Dashboard funnel: jumlah lead & nilai potensi per tahapan

**M2. Client Onboarding & Dokumen Legalitas**
- Konversi lead "deal" menjadi klien
- Master data klien (NPWP, alamat, PIC, kontrak induk)
- Upload & simpan dokumen legalitas: perjanjian kerjasama (PKS), addendum, NIB/NPWP klien
- Versioning dokumen + reminder jatuh tempo kontrak/addendum

**M3. Rekrutmen**
- **Job order**: permintaan tenaga kerja dari klien (posisi, jumlah, kualifikasi, gaji, SLA)
- **Database kandidat**: profil, CV (upload), riwayat, status
- Proses seleksi: screening → interview klien → offering → placement
- Penempatan kandidat ke job order (placement) → menjadi pintu masuk data karyawan (fase 2)

**Di luar MVP:** mobile app, integrasi API pihak ketiga, multi-bahasa.

### Fase 2 — HRD
- Database karyawan (dari placement), kontrak kerja karyawan, tanda tangan kontrak
  (digital signature sederhana / tracking status TTD fisik), penyimpanan dokumen HR
  (KTP, NPWP, BPJS, dll), reminder akhir kontrak & BPJS.

### Fase 3 — Operasional
- Perhitungan payrol bulanan (gaji pokok, tunjangan, lembur, potongan)
- Perhitungan PPh21 pasal 17 & TER (peraturan terkini)
- Monitoring approval kehadiran/overtime oleh klien
- Integrasi absensi

### Fase 4 — Finance
- Pembuatan invoice otomatis dari payrol + fee management
- Pajak (PPN, PPh23/4(2)), tracking pembayaran & overdue (aging report)
- Cash flow management (proyeksi arus kas masuk/keluar)

### Fase 5 — Akunting
- Jurnal umum, buku besar, neraca saldo
- Laporan keuangan standar: Neraca, Laba Rugi, Arus Kas

### Fase 6+ — AI ✅
- Screening CV otomatis & matching kandidat ↔ job order ✅
- Asisten Q&A atas dokumen kontrak (RAG) ✅
- Forecast cash flow ✅

## 5. Kebutuhan Non-Fungsional

| Aspek | Kebutuhan |
|-------|-----------|
| Arsitektur | Modular monolith (FastAPI), siap dipecah jadi microservices jika skala meminta |
| Frontend | React SPA tunggal (admin & internal), responsif |
| Data | PostgreSQL; file dokumen di object storage (MinIO, S3-compatible) |
| Keamanan | Auth JWT, role-based access control, semua akses dokumen ter-audit ✅ (modul `audit`) |
| Kepatuhan | Retensi dokumen sesuai regulasi; data tetap self-hosted (kebutuhan kerahasiaan klien) |
| Deployment | Docker Compose untuk awal; path migrasi ke Kubernetes tersedia |
| Bahasa UI | Bahasa Indonesia (istilah domain: PKS, addendum, PPh21, BPJS) |

## 6. Metrik Keberhasilan (MVP)

1. 100% klien baru & lead tercatat di sistem (bukan spreadsheet) dalam 1 bulan pemakaian.
2. Waktu pencarian dokumen legalitas klien < 1 menit.
3. Time-to-submit kandidat per job order turun ≥ 30%.
4. Tidak ada kontrak/addendum yang lewat jatuh tempo tanpa reminder.

## 7. Halaman & Alur Utama (MVP)

```
Login
  └─ Dashboard (ringkasan funnel, job order aktif, kandidat baru)
  └─ Pipeline        : daftar lead, ubah tahapan, tambah aktivitas
  └─ Klien           : daftar klien, detail klien + tab dokumen legalitas (upload/unduh)
  └─ Job Orders      : daftar permintaan tenaga kerja per klien, status
  └─ Kandidat        : database kandidat, CV, proses seleksi, placement ke job order
```

## 8. Batasan & Asumsi

- Single-tenant (satu perusahaan outsourcing = satu instalasi).
- Tanda tangan digital berkualitas hukum (tersertifikasi) di luar cakupan fase awal;
  fase awal hanya melacak status TTD.
- Perhitungan pajak mengikuti regulasi Indonesia yang berlaku dan harus mudah
  diperbarui (rate/config terpisah dari kode).
