# Component & Page-Archetype Implementation Spec (v2 — berdasarkan referensi Stitch 2026-09-05)

> Pelengkap `design.md` (prinsip/token). Versi ini REVISI TOTAL dari v1
> — v1 ditulis dari deskripsi teks, terlalu longgar untuk hasil
> konsisten. Versi ini diekstrak langsung dari 5 mockup Stitch nyata
> (Billing, Invoice, Payroll, CRM Pipeline, Executive Dashboard) yang
> user konfirmasi sebagai acuan kualitas target — jadi jauh lebih
> presisi, bukan interpretasi ulang.
>
> **Cara pakai**: terapkan §1 (komponen presisi) + §2 (archetype) ke
> SEMUA halaman via mapping §3, dikerjakan per-archetype (bukan per
> halaman acak) — lihat prompt eksekusi terpisah.

## 0. Prinsip Wajib — Visual HARUS Merefleksikan Data Asli (baca dulu sebelum §1)

**Setiap elemen visual di spec ini — badge, angka, progress bar,
warna status, chip kontekstual — HANYA boleh dipasang kalau ada data
backend asli di baliknya.** Ini bukan preferensi, ini aturan keras:

- "Opsional" di sepanjang dokumen ini berarti **opsional secara
  tampilan** (boleh tidak ada elemennya), **BUKAN** "boleh diisi data
  karangan kalau backend belum punya". Kalau backend belum expose
  data yang dibutuhkan suatu elemen (mis. skor anomali, prediksi AI,
  status integrasi eksternal), elemen itu **dihilangkan dari halaman
  itu**, bukan diisi placeholder/dummy yang kelihatan seperti data
  nyata.
- Ini beda dari **skeleton/loading state** (data sedang dimuat, boleh
  tampil shimmer/spinner) — yang dilarang adalah data yang KELIHATAN
  final & meyakinkan padahal fiktif.
- Kalau ragu apakah suatu bagian spec (§1.4, §1.7, §1.8, §1.9 —
  semua yang menyebut "opsional"/"kalau ada") punya padanan data di
  backend Aeos, **cek dulu ke source code/API, jangan asumsikan** —
  dan kalau ternyata belum ada, laporkan sebagai temuan gap (pola
  yang sama dengan audit-audit Fase 20-27 sebelumnya), bukan alasan
  untuk membuat data palsu supaya "kelihatan lengkap kayak mockup".

## 1. Komponen Presisi

### 1.1 Topbar (WAJIB sama persis di semua halaman)
```
[Logo+Tier badge]  [Search bar ⌘K]  [💳 Saldo: Rp X (Y%) [Top Up]]  [Tenant switcher ▾]  [🔔]  [Avatar+Nama+Role]
```
- Widget saldo credit BUKAN teks polos — **card kecil berlatar hijau/teal
  muda** (bukan putih polos), isi: ikon petir/kilat, "Saldo: Rp X", "(Y%)"
  di baris kedua kecil, tombol "Top Up" solid di ujung kanan widget.
  Warna widget berubah sesuai state (normal/peringatan/habis, sudah
  ditetapkan di `design.md` §7).
- Tenant switcher: ikon building + nama tenant (truncate dengan "...") + chevron.
- Avatar kanan: foto/inisial + nama + role DI BAWAH nama (2 baris, role lebih kecil & muted).

### 1.2 Breadcrumb + Page Header
```
KATEGORI › SUBHALAMAN                                    [status pill kanan, opsional]
Judul Halaman Besar (≈28px/600)
Subjudul konteks (≈13px, muted, bisa 2 baris)              [Tombol outline] [Tombol solid teal]
```
Breadcrumb uppercase kecil, abu-abu, kategori pertama BUKAN link warna
(sesuai §4.4.2 kategori: CRM/RECRUITMENT/WORKFORCE/FINANCE & ACCOUNTING/
ADMINISTRATION). Kadang ada status tambahan di kanan breadcrumb (mis.
"● Sinkronisasi Real-time Aktif · Pembaruan 14:32 WIB") — pola ini
dipakai di halaman yang datanya live/sinkron sistem eksternal.

### 1.3 KPI Card (versi presisi, upgrade dari v1)
```
┌───────────────────────────────┐
│ LABEL UPPERCASE 11px      [🔲]│ ← ikon kecil kanan atas, warna kontekstual
│ Rp 845.200.000          20-24px/600, tabular-nums
│ 12 Faktur belum terlunasi  [AR Aktif]│ ← teks konteks + badge kecil di ujung kanan (opsional)
│ ▓▓▓▓▓▓░░░░ (mini progress bar, opsional)│
└───────────────────────────────┘
```
- Badge kontekstual pojok kanan-bawah TIDAK selalu ada — muncul kalau
  ada info status tambahan yang perlu ditonjolkan (mis. "Kritis" merah,
  "+18.4% MoM" hijau, "Stabil" abu).
- Mini progress bar di baris terakhir OPSIONAL — dipakai kalau KPI itu
  punya makna "porsi dari target/total" (Total Nilai Pipeline dgn win
  rate, Sisa Saldo Credit dgn kuota bulanan). Kalau KPI-nya angka absolut
  tanpa pembanding (mis. Total Karyawan Aktif), tidak perlu progress bar.
- Susun 3-4 kartu per baris, grid rata gap 10-14px.

### 1.4 Pre-flight / Compliance Alert Box (konfirmasi presisi)
```
⚠️  [Judul tebal]: [ringkasan 1 kalimat, bisa 2 baris]        [Lihat N Kasus]  [✕]
```
- Bg `#FFFBEB`, border `#FDE68A`, judul & teks `#92400E`.
- SELALU py mekanisme dismiss (✕ kanan atas box).
- Tombol aksi di kanan: outline putih border sama warna box, teks
  "Lihat N Kasus" / "Review N Data" — bukan tombol solid teal (supaya
  tidak bersaing dengan CTA utama halaman).
- Muncul di BAWAH page header, SEBELUM KPI row.

### 1.5 Tab/Pill Filter Row (di atas tabel — BARU, belum ada di v1)
```
[Semua (54)] [Draft (4)] [Terkirim (18)] [Lunas (28)] [Jatuh Tempo]     [🔍 Cari...] [📅 Rentang tanggal] [⚙ Filter]
```
- Tab aktif: pill solid teal, teks putih. Tab lain: teks abu, tanpa
  background. Tiap tab tampilkan COUNT dalam kurung.
- Sejajar kanan: search input, lalu filter tambahan (date range,
  dropdown) sesuai kebutuhan halaman.
- Ini WAJIB untuk halaman List/CRUD (archetype B) yang datanya punya
  status/kategori jelas (invoice, quotation, job order) — kalau
  datanya tidak berkategori (mis. audit log polos), boleh skip.

### 1.6 Data Table — Pola Sel Kaya (upgrade dari v1 §1.3)
- **Gridline vertikal WAJIB antar kolom** (border-right 0.5px
  `var(--border)` di tiap kolom kecuali kolom terakhir) — pemisah
  horizontal antar baris SAJA tidak cukup untuk kesan enterprise-dense,
  harus ada garis pemisah kolom juga.
- **Sel majemuk**: nama/ID utama di baris atas, detail sekunder (NIK/
  departemen/PIC) di baris bawah lebih kecil & muted — BUKAN kolom
  terpisah kalau infonya erat kaitannya (nama+jabatan, invoice+e-faktur).
- **Avatar/inisial berwarna** di kolom pertama: lingkaran kecil, warna
  berbeda per baris (rotasi palet netral: biru/hijau/kuning/ungu muda)
  — BUKAN identitas kategori (beda dari CATEGORY_META sidebar). Hanya
  untuk entitas berupa ORANG (kandidat, karyawan, PIC klien) — bukan
  untuk baris non-personal (invoice, jurnal).
- **Highlight anomali dalam sel**: kalau ada nilai yang butuh perhatian
  (PPh21 salah hitung, NPWP kadaluarsa), beri warna amber + tanda
  bintang (`Rp 1.098.000*`) dan catatan kecil di baris sub-detail
  (mis. "(NPWP Exp)", "(NIK Duplikat)") — JANGAN diam-diam ditampilkan
  normal, anomali harus kelihatan beda dari baris normal secara visual.
- **Status inline**: dot warna + label pendek (bukan cuma badge pill
  polos) untuk status yang perlu deteksi cepat sambil scan tabel.
- Kolom nominal selalu rata kanan, tabular-nums (tidak berubah dari v1).
- **Row height 32-36px (bukan 36-40px)** — direvisi lebih ketat dari
  `design.md` §3b setelah review implementasi nyata; versi lama masih
  kerasa lega untuk standar enterprise-dense yang jadi target.

### 1.6a Header+Action Row — WAJIB di SEMUA card, bukan cuma §1.7 (BARU)
Setiap card/module/section di halaman manapun — bukan cuma "Kartu Info
Baris Bawah" — WAJIB punya baris header eksplisit sebelum isinya:
```
[ikon kecil] Judul Section                    [tombol/dropdown aksi opsional]
─────────────────────────────────────────────────────────────────────
(isi card)
```
Card TANPA header+ikon (judul teks polos menggantung di atas isi,
tanpa garis pemisah) dianggap TIDAK SESUAI spec — ini kesalahan paling
sering ditemukan di implementasi awal (card "Aging", "Arus Kas" jadi
contoh yang perlu diperbaiki).

### 1.6b Kepadatan (Density) — perketat, jangan pilih ujung longgar skala
Skala spacing 4/8/12/16/20/24px (`design.md` §3b) TETAP berlaku, tapi
untuk kesan enterprise-dense yang jadi target, **default ke ujung
KECIL skala ini**, bukan tengah/besar:
- Padding internal card: **12px** (bukan 16-24px).
- Padding sel tabel: **8px vertikal, 12px horizontal** (bukan 12-16px).
- Gap antar KPI card dalam 1 baris: **10px** (bukan 14-16px).
Ini bukan token baru — cuma pemilihan nilai default di ujung bawah
skala yang sudah ada, supaya konsisten "dense" di semua halaman
tanpa perlu keputusan ad-hoc per komponen.

### 1.7 Kartu Info Baris Bawah (3-kolom, di bawah tabel utama)
```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ [ikon] Judul [badge status]│ ...          │ ...          │
│ Deskripsi 1-2 baris kecil  │              │              │
└──────────────┘ └──────────────┘ └──────────────┘
```
Dipakai untuk info pendukung yang bukan aksi utama halaman (status
integrasi eksternal, prediksi AI, pengingat kepatuhan). Selalu 3
kolom rata, ikon kecil + judul + badge status di kanan judul.

### 1.8 Kanban Board (KHUSUS Pipeline/CRM — archetype F, baru)
```
● Nama Tahap    N     Total: Rp X
┌─────────────────┐
│ [Badge tipe]     │
│ Nama Perusahaan  │
│ Deskripsi peluang│
│ Rp Nilai         │
│ [avatar] Nama PIC  [chip status kecil]│
└─────────────────┘
```
- Kolom: dot warna tahap + nama tahap + count + total value tahap
  (BUKAN cuma nama kolom polos).
- Card: badge tipe/kategori di atas (warna beda per tipe layanan,
  independen dari status), nama entitas bold, deskripsi 1 baris,
  nilai Rupiah bold, baris bawah avatar+nama pemilik deal + chip
  status kecil kontekstual (warna & teks beda-beda: "Follow up",
  "Meeting besok", "Quotation v2", dst — bebas sesuai konteks nyata).
- Filter di atas board: search + pill filter tipe layanan (mirip §1.5)
  + avatar stack "Pemilik Deal" (siapa saja yang punya deal aktif).

### 1.9 Urgent Action Banner (KHUSUS Executive Dashboard — baru)
```
⚠️ N Tindakan Mendesak Membutuhkan Approval Eksekutif          [URGENT PRIORITY]
┌─────────┐ ┌─────────┐ ┌─────────┐
│[Kategori]│ │[Kategori]│ │[Kategori]│
│Deskripsi │ │Deskripsi │ │Deskripsi │
│[Link aksi →]│[Link aksi →]│[Link aksi →]│
└─────────┘ └─────────┘ └─────────┘
```
Beda dari Pre-flight Alert (§1.4) yang single-item per box — ini
MULTI-KATEGORI dalam satu banner besar, tiap sub-card mewakili 1
domain (Workforce/Finance/CRM) dengan link aksi sendiri-sendiri.
Khusus dipakai di Dashboard/Executive Overview, bukan di halaman
proses spesifik.

## 2. Page Archetype (6 pola — tambah F dari v1)

**A. Overview** — Breadcrumb+header → **Urgent Action Banner
(§1.9)** kalau ada item mendesak lintas-domain → KPI row (§1.3, 4
kartu) → 2 kolom: kiri konten utama (chart/proyeksi + log aktivitas),
kanan panel-panel kecil bertumpuk (pipeline ringkas, kesehatan
tenaga kerja, credit metering breakdown).

**B. List/CRUD** — Header (§1.2) → Pre-flight Alert (§1.4) KALAU ada
kondisi yang butuh perhatian sebelum aksi massal → KPI row (§1.3, 3-4
kartu ringkasan) → Tab/Pill Filter (§1.5) → Data Table (§1.6) →
Kartu Info Baris Bawah (§1.7) kalau relevan.

**C. Detail/Profile** — (tidak berubah dari v1) Header ringkasan →
tab horizontal → konten per tab campuran §1.3/§1.6/§1.7.

**D. Run/Process** (payroll run, tutup buku, batch approval) — Header
→ **Pre-flight Alert WAJIB** kalau ada anomali → KPI row (4 kartu) →
Tab/search/filter row → Data Table dengan highlight anomali (§1.6) →
Kartu Info Baris Bawah (kesiapan rekening, jadwal cut-off, dst).

**E. Form/Wizard** — (tidak berubah dari v1) Stepper → form section →
footer aksi.

**F. Kanban Board** (Pipeline/CRM khusus, BARU) — Header → KPI row
(4 kartu ringkasan: total nilai, win rate, target, estimasi komisi) →
search+filter+avatar-stack row → Kanban board (§1.8) horizontal-scroll.

## 3. Mapping Halaman → Archetype (revisi)

### 3.0 Daftar Item Sidebar per Kategori (referensi definitif — cek ini kalau ada item hilang/salah kategori)

| Kategori | Item (urutan tidak mengikat) |
|---|---|
| **CRM** | Pipeline, Klien, Quotation, Agreement, Lead Sourcing |
| **Recruitment** | Job Orders, Talent Pool, AI Interview, Black Lists, **Referral** (penempatan masuk akal — program referral karyawan→kandidat — meski awalnya tidak eksplisit diputuskan taruh di sini; konfirmasi tetap di sini kecuali ada alasan pindah) |
| **Workforce** | Karyawan, Kontrak, BPJS & Asuransi, Absensi, ESS, TTE, **Payroll** (sengaja di sini, bukan Finance — soal karyawan bukan soal uang keluar) |
| **Finance & Accounting** | Invoice, e-Faktur, Kas & Bank, Pembelian, Aset Tetap, Payment Request, Tutup Buku, Jurnal & Buku Besar, Laporan Keuangan, Tanya-Laporan AI |
| **Administration** | Rate Configuration (rename dari "Tarif & Rate"), Billing & Saldo Credit, Settings & RBAC |

**Koreksi 2026-09-05: "Kandidat" DIHAPUS sebagai item sidebar
terpisah.** Sesuai intention asli (deskripsi 2 jalur sourcing
kandidat, awal percakapan) dan referensi MYOHRIS — Talent Pool
ADALAH database kandidat tunggal (bukan 2 database beda). Kandidat
yang sedang berada di pipeline suatu Job Order dilihat lewat **tab
"Candidates" (Kanban, reuse pola §1.8) DI DALAM `JobOrderDetail.tsx`**
(archetype C) — persis pola MYOHRIS (tab "Candidates" di Job Detail,
bukan halaman sendiri di sidebar).

Kalau ada kategori yang render sebagai 1 baris tanpa sub-item (bug
yang pernah terjadi pada CRM & Workforce, 2026-09-05) — cocokkan
dulu ke tabel ini untuk pastikan semua item di atas benar terdaftar
di `CATEGORY_META`/menu array `Layout.tsx`, bukan cuma sebagian.


| Archetype | Halaman |
|---|---|
| A — Overview | `Dashboard.tsx` (label sidebar/UI: **"Overview"**, bukan "Dashboard" atau "Dashboard/Overview" — pola §1.9 WAJIB di sini), overview per-kategori lain jika masih dipertahankan |
| B — List/CRUD | `Clients.tsx`, `TalentPool.tsx`, `JobOrders.tsx`, `Blacklist.tsx`, `Quotations.tsx`, `Agreements.tsx`, `Employees.tsx`, `Users.tsx`, `PaymentRequests.tsx`, `Finance.tsx` (Invoice — KPI row WAJIB 4 kartu + tab filter status persis §1.5), `Rates.tsx`, `Referral.tsx`, `PlatformTenants.tsx`, `Audit.tsx` |
| C — Detail/Profile | `JobOrderDetail.tsx` (**tambah tab "Candidates" — Kanban, reuse §1.8**, menggantikan `Candidates.tsx` yang dihapus dari sidebar; kolom Kanban ikuti tahap `PlacementStatus`), halaman Employee Detail (cek lokasi file) |
| D — Run/Process | `Payroll.tsx` (Pre-flight WAJIB persis pola §1.4, 4 KPI card, 3 kartu info bawah: Kesiapan Rekening/Kepatuhan Pajak/Jadwal Cut-off), `PayrollClientPortal.tsx`, `Accounting.tsx`, `AccountingAi.tsx`, `Billing.tsx` (Saldo Credit — widget besar §1.1 style + auto top-up toggle + riwayat transaksi tabel) |
| E — Form/Wizard | Bagian create/edit `Quotations.tsx`/`Agreements.tsx`, `AIInterviewSession.tsx` |
| F — Kanban Board (BARU) | `Leads.tsx` (mockup Stitch nunjukkan "Pipeline" sebagai halaman Kanban penuh — cek apakah `Leads.tsx` ini yang dimaksud atau perlu file terpisah) |
| Khusus (pola sendiri) | `Login.tsx`/`ForgotPassword.tsx`/`ResetPassword.tsx`, `Chat.tsx`, `MyPortal.tsx`/`CareerPortal.tsx` (BambooHR-style, bukan archetype ini) |

## 4. Yang TIDAK berubah
Component library (`components/ui/`), token warna (`index.css`),
`CATEGORY_META` di `Layout.tsx`, RBAC/permission logic — semua sudah
final, dipakai sebagai fondasi, bukan ditulis ulang.
