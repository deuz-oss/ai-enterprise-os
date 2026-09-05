# Design — Arah Visual & Component Library

> Menggantikan `notion-ui-parity-plan.md` (dihapus 2026-09-03) — dokumen
> itu men-track migrasi ke tema "Notion UI" yang sudah tidak relevan.
> Arah visual saat ini SaaS-admin bersih (lihat komentar di
> `frontend/src/index.css`), dan dokumen ini dibangun ulang dari nol
> untuk arah itu, bukan revisi dokumen lama.
>
> Status: **living document** — diupdate tiap ada keputusan desain baru,
> bukan ditulis sekali lalu dibiarkan usang seperti pendahulunya.

---

## 1. Konteks & Masalah yang Mau Diselesaikan

Audit 2026-09-03 menemukan: 32/41 file frontend bypass token `var(--...)`
dengan warna Tailwind mentah, tidak ada component library (`Button`/
`Card`/`Badge` tidak ada di `components/`), 3 halaman auth 100% tidak
merespons dark mode, dan border-radius/warna kategori tersebar tanpa
aturan jelas. Detail lengkap ada di riwayat audit — dokumen ini fokus ke
**arah ke depan**, bukan mengulang temuan.

Tujuan besar: Aeos naik kelas dari "terlihat internal tool" jadi
"terlihat produk SaaS komersial", karena rencana produk ini akan dijual
lintas industri (lihat `PRD.md` §1 arah v4.0), bukan cuma dipakai
internal SPC.

## 2. Referensi Benchmark

Diriset dan dibahas eksplisit (2026-09-03), masing-masing untuk konteks
berbeda — bukan satu app ditiru mentah-mentah:

| Referensi | Kekuatan diambil | Dipakai untuk |
|---|---|---|
| **Rippling** | Data-dense tapi lega: card border tipis (bukan shadow), tabel jadi "wajah produk", satu warna aksen dipakai pelit, tipografi kecil tapi weight jelas | Modul admin/ops-heavy: Finance, Payroll, Recruitment |
| **BambooHR** | "Lightness": whitespace lega, navigasi predictable, config kompleks dipecah jadi wizard step-by-step | Portal Karyawan (ESS) — audiens beda dari staf ops |
| **Deel** | Unifikasi kompleksitas ke satu dashboard, pre-flight check sebelum aksi besar (payroll run), compliance alert jadi elemen visual utama | Onboarding klien, dashboard lintas modul, payroll review |
| **LinovHR** | **Kompetitor langsung** (sama pasar Indonesia, sama regulasi) — jadi *benchmark minimum*, bukan tujuan akhir. Kekuatannya: multi-entity clarity, dashboard analitik. Secara visual sendiri sudah terasa agak dated dibanding standar SaaS 2026 | Sinyal "jangan sampai kalah dari ini" saat sales pitch |

Prinsip gabungan: **Rippling/Deel untuk kerapian & kepadatan data,
BambooHR untuk modul yang disentuh user awam, LinovHR sebagai lantai
minimum yang harus dilewati.**

## 3. Warna Aksen — STATUS: FINAL (2026-09-04)

**Teal gelap `#0F6E56`** (+ terang `#5DCAA5`, + varian aktif/gelap
`#0A4D3C`) — dikonfirmasi lewat 2 jalur independen: (1) hasil
eksplorasi Claude Design/Stitch kembali ke hex yang sama persis tanpa
diminta ulang, (2) dibandingkan terhadap identitas SPC (parent
company, biru `#1B6FC4`+merah `#D32E36`) — beda ±45° hue, cukup jauh
dibedakan tapi masih terasa "evolusi", bukan "berlawanan total" (lihat
riwayat keputusan di bawah untuk konteks lengkap trade-off ini).

**Palet lengkap (final):**
- Aksen: `#0F6E56` (primer), `#5DCAA5` (terang/hover), `#0A4D3C` (aktif/gelap)
- Latar: `#F8FAFC` (canvas), `#FFFFFF` (card/surface)
- Border: `#E2E8F0` (normal), `#F1F5F9` (subtle)
- Teks: `#0F172A` (utama), `#64748B` (muted), `#94A3B8` (subtle)
- Status semantik (independen dari aksen, TETAP dipakai di semua kondisi):
  Sukses `#10B981` (bg `#ECFDF5`, border `#A7F3D0`) · Warning `#F59E0B`
  (bg `#FFFBEB`, border `#FDE68A`) · Error `#EF4444` (bg `#FEF2F2`,
  border `#FECACA`) · Info `#3B82F6` (bg `#EFF6FF`, border `#BFDBFE`)

**Riwayat keputusan (untuk konteks, bukan status aktif):** sempat
dibandingkan dengan opsi coral/terracotta sebagai alternatif yang
lebih "berlawanan total" dari SPC — tidak dieksplor lebih lanjut
karena teal sudah dikonfirmasi lewat 2 tool desain independen.

## 3a. Tipografi & Skala (dikonfirmasi via Stitch, selaras Inter yang sudah dipakai Aeos)

- Font: Inter (sudah jadi default Aeos di `tailwind.config.ts`, tidak berubah)
- Skala: Judul halaman 20-24px/600 · Header section 16px/600 ·
  Table/label 11-13px/400-500 — skala kecil-tapi-tegas ini yang
  dimaksud "data-dense" di §2 (referensi Rippling)
- Angka finansial: tabular-nums, rata kanan di tabel (belum ada aturan
  eksplisit soal ini sebelumnya — sekarang wajib diterapkan di semua
  tabel yang menampilkan nominal Rupiah)

## 3b. Spacing & Tinggi Baris

- Skala spacing: 4/8/12/16/20/24px — jangan pakai angka di luar skala ini
- Tinggi baris tabel standar: 32-36px *(direvisi dari 36-40px semula,
  2026-09-05, setelah review implementasi nyata — lihat
  `component-implementation-spec.md` §1.6 untuk detail & alasan;
  prinsip dasarnya tetap sama: "tabel adalah wajah produk" dari
  Rippling, §2)*
- Radius: sm 4px (badge kecil), md 6px (input/button), lg 8px (card)
  — catatan: ini SEDIKIT beda dari radius yang sudah ada di
  `index.css`/Tailwind config Aeos sekarang (`rounded-lg`/`rounded-xl`
  campur di banyak halaman, temuan audit awal); saat migrasi token
  berlanjut (§5), pakai skala sm/md/lg ini sebagai acuan penyeragaman.

## 4. Component Library

Lokasi: `frontend/src/components/ui/`. Detail lengkap di `PRD.md`
Fase 22. Ringkasan:

| Komponen | Status | Sumber warna |
|---|---|---|
| `Button` | ✅ Ada (reuse `.btn`/`.btn-secondary`, + varian baru `ghost`/`danger`) | `var(--accent)` — ikut berubah kalau §3 final |
| `Badge` | ✅ Ada (reuse `.pill`/`.p-*`, API `tone` semantik) | **SENGAJA independen dari `--accent`** — warna status (sukses=hijau, dst.) universal, tidak boleh ikut goyah |
| `Card` | ✅ Ada (reuse `.card`) | Netral, tidak terpengaruh §3 |
| `ProgressStep` | ✅ Ada (baru, dipakai tracker `PlacementStatus` di PRD Fase 21) | `var(--accent)` — ikut berubah kalau §3 final |

**Aturan wajib** (selaras `AEP-014` §17): jangan bikin komponen baru
kalau yang sesuai sudah ada di tabel ini. Kalau butuh varian baru,
extend komponen existing, jangan duplikat.

## 5. Progress Migrasi Token

Dari 41 file frontend yang ditemukan bypass token saat audit awal:

| Halaman | Status |
|---|---|
| `Login.tsx` | ✅ Migrasi selesai (2026-09-03) |
| `ForgotPassword.tsx` | ✅ Migrasi selesai (2026-09-03) |
| `ResetPassword.tsx` | ✅ Migrasi selesai (2026-09-03) |
| 38 file lain | ⬜ Belum disentuh |

Migrasi dilakukan bertahap per halaman saat halaman itu disentuh untuk
alasan lain (bukan proyek migrasi besar sekaligus) — update tabel ini
setiap ada halaman baru yang dimigrasi.

## 6. Prinsip Kerja Ke Depan

1. **Token dulu, styling manual belakangan.** Warna, radius, spacing
   baru selalu lewat `var(--...)` atau komponen `ui/`, tidak pernah hex
   langsung di halaman.
2. **Satu keputusan warna, satu tempat.** `--accent` di `index.css`
   adalah satu-satunya sumber kebenaran warna brand.
3. **Warna makna ≠ warna brand.** Status (sukses/gagal/warning) pakai
   token semantik tetap, tidak pernah ikut ganti kalau `--accent` ganti.
4. **Radius & spacing ikut skala yang sudah ada** — jangan angka baru
   yang belum ada di `index.css`/Tailwind config tanpa alasan
   terdokumentasi di sini.
5. **Dokumen ini diupdate, bukan dibiarkan usang.** Kalau arah desain
   berubah drastis (seperti kasus `notion-ui-parity-plan.md`), tulis
   ulang bagian yang relevan di sini — jangan biarkan jadi jejak sejarah
   yang menyesatkan developer berikutnya.

## 7. Perubahan Model Komersial (2026-09-04) — Dampak ke Frontend

**Keputusan bisnis (detail penuh menyusul di PRD, dicatat di sini
karena efeknya langsung ke cara UI dibangun):** Opsi F (bundle
per-Cloud yang harus "diaktifkan" satu-satu sebelum bisa dipakai)
digantikan model baru — **semua fitur di semua Cloud terbuka penuh**
untuk tenant `commercial`, dimonetisasi lewat **saldo credit** yang
diisi dari subscription bulanan (3 tier: Rp500rb/2jt/5jt) + top-up
manual kalau habis.

### Yang HILANG dari checklist frontend (jangan dibangun lagi)

Sebelumnya, hampir tiap halaman/komponen perlu mikirin: *"apakah Cloud
ini dilisensikan buat tenant ini?"* — locked-state overlay, blur,
redirect ke halaman upgrade, dst. **Ini SUDAH TIDAK RELEVAN.** Kalau
ada kode/desain lama yang masih melakukan pengecekan lisensi per-Cloud
di level UI, itu perlu dihapus, bukan dipertahankan "siapa tahu
kepakai lagi."

### Yang TETAP ada — dan yang BARU

Cuma 2 kategori state yang masih perlu ditangani di UI, dan
keduanya BEDA KARAKTER, jangan dicampur jadi satu komponen:

**A. Permission-denied (RBAC — tidak berubah dari sebelumnya)**
Ini soal *siapa boleh lihat apa di dalam tenant yang sama* — sama
sekali tidak berkaitan dengan billing/saldo. Contoh: Ops coba buka
data karyawan internal. Harus tampil pesan eksplisit ("Anda tidak
punya akses ke data ini"), bukan halaman kosong.

**B. Indikator saldo credit (BARU — wajib ada, bukan opsional)**
Karena semua fitur metered dan saldo bisa habis, UI WAJIB kasih tau
posisi saldo — bukan cuma nolak transaksi pas udah kepotong nanti.
Dua level:
- **Indikator ringkas** di header/topbar — selalu terlihat, 3 state:
  Normal (teal, >20% tersisa) → Peringatan (amber, ≤20%) → Habis
  (merah, auto-reload aktif atau minta top-up manual).
- **Halaman detail billing** — breakdown pemakaian, riwayat transaksi,
  tombol top-up manual.

Pengecualian: **Govern Cloud (Akunting)** — akses dasarnya bisa
"gratis" (termasuk di Tier 2/3, atau bayar Rp300rb/user di Tier 1),
TAPI fitur AI di dalamnya (OCR, rekonsiliasi, dst.) tetap motong
saldo credit yang sama. Jangan bikin state "gratis" yang mengira
seluruh modul termasuk AI-nya bebas biaya — cuma akses dasarnya yang
gratis.

**Kesimpulan buat siapa pun yang develop frontend ke depan:** logic
"apakah fitur ini boleh diakses" sekarang jauh lebih sederhana —
satu-satunya gate adalah RBAC (permission), bukan licensing per-Cloud.
Yang perlu effort desain justru pindah ke **visibilitas saldo**
(state B) supaya user tidak kaget di-charge.

### Struktur Sidebar Final — Hilangkan Branding "Cloud" (2026-09-04)

Nama "Talent Cloud", "Workforce Cloud", "Revenue Cloud", "Govern
Cloud" **dihapus dari tampilan** — diganti 5 kategori berdasarkan
fungsi nyata (nama modul kode `apps.py` TIDAK berubah, ini murni
label & pengelompokan UI):

- **CRM** — Pipeline, Klien, Quotation, Agreement, Lead Sourcing
- **Recruitment** — Job Orders, Kandidat, Talent Pool, AI Interview,
  Black Lists, **Referral** (ditambahkan 2026-09-05 — program referral
  karyawan→kandidat, penempatan dikonfirmasi masuk akal di sini)
- **Workforce** — Karyawan, kontrak, BPJS+asuransi, Absensi, ESS,
  TTE, **Payroll** (Saltab, PPh21 — sengaja di sini, bukan di Finance,
  karena ini soal karyawan)
- **Finance & Accounting** — Invoice, e-Faktur, Kas-Bank, Pembelian,
  Aset Tetap, Payment Request, Tutup Buku, Jurnal, Laporan,
  Tanya-Laporan AI (gabungan bekas Revenue Cloud + seluruh Govern Cloud)
- **Administration** — Settings, **Rate Configuration** (rename dari
  "Tarif & Rate": tarif PPh21/BPJS/bank yang dipakai Payroll)

Asumsi kerja (koreksi bila salah): Chat tetap top-level di luar 5
kategori ini; dashboard/pengaturan saldo credit masuk Administration.

Detail lengkap model komersial di baliknya (tier, model data,
payment gateway) ada di PRD §4.4 (Opsi G) — tidak diulang di sini,
dokumen ini fokus ke implikasi visual/struktural saja.
