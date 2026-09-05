# ADR-0007-Hapus-Guard-Lisensi-per-SKU-Opsi-G

- Status: Accepted
- Date: 2026-09-04
- Deciders: Brian (Product), Platform Engineering
- Technical Story: PRD §4.4 (Opsi G), PRD §5 Fase 28

## Context

Sejak v3.0, packaging Aeos (§4.1-4.3 PRD, "Opsi F") memakai model
**bundle metered per-SKU** — tiap Cloud (Talent/Workforce/Revenue/
Govern) harus dilisensikan tenant sebelum bisa dipakai, ditegakkan
lewat guard `require_licensed_app`/`require_any_licensed_app` di
level router (`core/security.py`) dan guard data-driven per-objek
untuk Payroll (`assert_run_license`, **ADR-0006**).

Dua masalah konkret muncul dari model ini:

1. **UX**: tenant harus commit beli/aktifkan SKU dulu sebelum bisa
   coba fiturnya — value baru kerasa setelah "beli", bukan sebelum.
2. **Development**: hampir tiap halaman/komponen frontend perlu
   logic "apakah Cloud ini dilisensikan buat tenant ini?" (locked-state
   overlay, redirect) tersebar di banyak tempat — menambah beban kerja
   linear tiap ada halaman baru.

Keputusan bisnis (PRD §4.4, "Opsi G") mengganti model ini: semua
fitur di semua kategori terbuka penuh untuk tenant `commercial`,
dimonetisasi lewat saldo credit (subscription bulanan + top-up),
bukan lagi gate per-SKU.

## Decision

1. **Guard lisensi per-SKU DIHAPUS** dari router
   (`require_licensed_app`/`require_any_licensed_app` di
   `core/security.py`) — diganti **satu guard tunggal**: "apakah
   tenant punya `TenantSubscription` aktif" (terlepas tier berapa).
2. **`assert_run_license` (ADR-0006) DIHAPUS** dari
   `payroll/service.py` — validasi `run_type` terhadap lisensi
   `hr_payroll`/`operations_billing` tidak lagi relevan karena tidak
   ada lagi lisensi per-app. Kolom `PayrollRun.run_type` TETAP
   dipertahankan (masih berguna untuk pelaporan/analitik, cuma
   fungsi guard-nya yang dicabut).
3. **Tabel `tenant_app_licenses`** (Fase 7, §12.6 TRACEABILITY-MATRIX)
   tidak dihapus dari skema — datanya jadi tidak lagi dipakai untuk
   enforcement, tapi dipertahankan sementara untuk keperluan histori/
   rollback selama masa transisi (lihat Consequences).
4. **Guard BARU** yang menggantikan: cek tunggal di level
   middleware/dependency — `require_active_subscription(tenant_id)`
   — dan pengecekan saldo credit (`TenantBudgetCycle`/
   `TenantCreditAccount`) di level SETIAP operasi metered individual
   (bukan di level router/prefix), karena yang membedakan sekarang
   bukan "app mana yang dilisensikan" tapi "apakah masih ada saldo
   untuk operasi metered ini".
5. **BPJS recap** (poin 4 ADR-0006 lama) tidak berubah secara
   substansi — tetap infrastruktur bersama, cuma sekarang otomatis
   accessible ke siapa pun yang tenant-nya subscription aktif (tidak
   perlu any-of check lagi karena tidak ada lagi kategori lisensi
   terpisah untuk dicek any-of-nya).

## Consequences

- ✅ Kompleksitas guard turun signifikan — dari "per-SKU + per-objek
  run_type" jadi "satu cek subscription aktif + cek saldo per-transaksi
  metered". Frontend tidak perlu lagi logic locked-state per-Cloud.
- ✅ Selaras keputusan bisnis Opsi G — akses fitur tidak lagi jadi
  penghalang funnel adopsi produk.
- ⚠️ **Migrasi tenant existing yang sudah aktif di Opsi F belum
  dirancang** (dicatat juga di PRD Fase 28) — perlu keputusan
  terpisah sebelum eksekusi: apakah tenant lama di-auto-convert ke
  tier terdekat, atau pilih manual. ADR ini TIDAK menjawab itu.
- ⚠️ Selama masa transisi (sebelum Fase 28 selesai), `core/security.py`
  akan punya DUA jalur guard berjalan bersamaan (lama per-SKU, baru
  per-subscription) — perlu feature flag atau `billing_mode` yang
  diperluas untuk membedakan tenant mana yang sudah dimigrasi.
- ⚠️ Tabel `tenant_app_licenses` yang dipertahankan (poin 3) berarti
  ada data yang secara teknis "mati" (tidak dipakai enforcement) untuk
  sementara — perlu rencana pembersihan/deprecation resmi di fase
  terpisah setelah migrasi selesai dan tidak ada lagi kebutuhan rollback.

## Alternatives considered

- **Pertahankan guard per-SKU, cuma naikkan generosity trial** —
  ditolak: tidak menyelesaikan masalah #2 (kompleksitas development
  frontend tetap ada, cuma trial-nya lebih panjang).
- **Hybrid: sebagian Cloud tetap bergerbang, sebagian terbuka** —
  ditolak: menambah kompleksitas keputusan ("kenapa X gratis tapi Y
  tidak") tanpa alasan produk yang kuat; keputusan bisnis (PRD §4.4)
  eksplisit memilih "semua terbuka, monetisasi lewat saldo" sebagai
  prinsip tunggal yang konsisten.

## Related

- **Menggantikan ADR-0006** (Payroll License Guard by Run Type) —
  isi keputusan ADR-0006 TIDAK diedit/dihapus (dipertahankan utuh
  sebagai catatan sejarah), hanya baris status yang diperbarui jadi
  "Superseded by ADR-0007".
- PRD §4.4 (Opsi G), §5 Fase 28, §2 baris #12 (masalah yang
  diselesaikan) · TRACEABILITY-MATRIX §12.6, §12.10 (perlu update
  terpisah SETELAH Fase 28 dieksekusi, bukan bagian dari ADR ini)
