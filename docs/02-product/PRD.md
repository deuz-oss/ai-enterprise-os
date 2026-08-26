# Product Requirements Document (PRD)

**Produk:** Outsourcing Operating System — portofolio aplikasi bisnis untuk
industri *manpower services* (working title: AI Enterprise OS)
**Pemilik Produk:** Brian — Head of Business & Operations
**Versi:** 1.4 · **Status:** Approved — Repositioning Multi-App SaaS
**Terakhir diperbarui:** 2026-08-25

> **Changelog**
> - **v1.4 (2026-08-25)** — **Talent Pool & CV Standardization**: setiap CV yang
>   di-upload otomatis diproses (ekstraksi teks/OCR + LLM ke skema tetap)
>   menghasilkan profil kandidat terstruktur dan **dokumen CV standar bertemplate**
>   dengan branding per tenant, melalui tahap review recruiter. Termasuk dukungan
>   OCR untuk CV hasil scan/foto sejak awal.
> - **v1.3 (2026-08-25)** — Fitur **Chat Workspace ala Slack**, gratis di semua
>   paket: channel/DM/thread/mention/notifikasi interaktif, channel otomatis per
>   entitas (job order, payrol, onboarding), dan **karyawan outsourcing ikut dengan
>   hak akses ter-scope per proyek** (hanya bisa berkomunikasi dengan sesama karyawan
>   proyek + tim Ops proyek; tidak dapat menemukan/menyebut user di luar scope).
>   Gelombang 2 = AI kolaborasi (@AEOS, rangkuman thread, digest).
> - **v1.2 (2026-08-25)** — Modul **Finance & Accounting mengadopsi konsep Accurate**
>   secara lengkap: bagan akun dinamis + template, jurnal memorial/terposting,
>   mesin auto-journal berbasis rule, modul kas-bank/pembelian/aset tetap,
>   periode & tutup buku, dimensi analisis klien/proyek, laporan lengkap —
>   plus **AI Layer akuntansi** sebagai pembeda (§8.8).
> - **v1.1 (2026-08-25)** — Repositioning dari web internal menjadi **portofolio
>   aplikasi modular yang dijual terpisah maupun paket** (model bisnis ala Mekari);
>   arah UI **Notion-style** dengan app launcher; pemisahan **payrol internal vs
>   payrol proyek**; modul **absensi** harian; **Saltab digital** (pengganti Excel
>   salary tabulasi); workflow **approval klien ber-token** dan **Payment Request (PR)**;
>   integrasi **BPJS dua sisi** (perusahaan → ditagihkan ke klien, karyawan → potongan).
> - **v1.0 (2026-08-23)** — Web internal end-to-end untuk satu perusahaan
>   outsourcing; Fase 1–6 + platform (multi-tenant, TTE, BPJS recap, ESS, mobile).

---

## 1. Ringkasan Eksekutif

Sistem operasional end-to-end untuk perusahaan outsourcing yang mencakup seluruh
siklus bisnis: akuisisi klien → onboarding & dokumen legalitas → rekrutmen
(job order, kandidat, placement) → HRD → payrol & PPh21 → finance & akunting.

Mulai v1.1, produk diposisikan sebagai **portofolio aplikasi modular** (model ala
Mekari):

1. Setiap aplikasi **dapat dipakai dan dijual secara mandiri** (stand-alone).
2. Saat beberapa aplikasi dipasang bersama, mereka **terintegrasi tanpa
   sinkronisasi manual** karena berbagi satu database dan satu model data.
3. Dijual **per aplikasi, dalam bundle, maupun full package**, dengan satu akun
   dan satu billing per tenant.
4. Fondasi teknis telah siap: modular monolith (modul per domain) + multi-tenant
   SaaS (`tenant_id` pada semua tabel bisnis).

## 2. Masalah yang Diselesaikan

| # | Masalah saat ini | Dampak |
|---|------------------|--------|
| 1 | Pipeline calon klien dicatat manual di spreadsheet | Prospek bocor, tidak ada visibilitas status |
| 2 | Dokumen legalitas tersebar di email/drive pribadi | Sulit diaudit, versi dokumen tidak jelas |
| 3 | Rekrutmen tanpa sistem terpusat | SLA pengiriman kandidat lambat, database kandidat tidak terpakai ulang |
| 4 | Kontrak & dokumen HR tidak terstruktur | Risiko kepatuhan saat audit klien/Disnaker |
| 5 | Payrol manual di Excel **Saltab** (salary tabulasi): impor absensi, prorata manual, komponen gaji–potongan manual | Rawan salah rumus/salin-tempel, tidak ada jejak revisi |
| 6 | Approval payrol proyek via email file Saltab ke klien; eksekusi via email Payment Request ke atasan (di PT Sinergi Performa Cipta: COO) | Lambat, status tidak terlacak, bukti approval tersebar |
| 7 | Absensi hanya rekap bulanan manual | Selisih jam kerja/lembur baru ketahuan saat payrol |

## 3. Pengguna & Peran

| Peran | Deskripsi | Fitur utama |
|-------|-----------|-------------|
| Admin | Owner / IT | Semua modul + manajemen user + lisensi aplikasi |
| Business Dev | Sales/presales | Pipeline, data klien, upload dokumen legalitas |
| Recruiter | Tim rekrutmen | Job order, kandidat, onboarding karyawan |
| HR | Personalia | **Karyawan internal**: kontrak, dokumen pegawai, absensi internal, **payrol internal** |
| Operations | Operasional proyek | **Karyawan outsourcing**: monitoring penempatan, absensi outsourcing, **Saltab/payrol proyek**, approval klien, **Payment Request proyek** |
| Finance | Keuangan | Eksekusi PR, invoice, pajak, aging/overdue, cash flow |
| Management | Direksi | Dashboard ringkasan + **approver rantai PR** (configurable per tenant; contoh: COO) |
| Karyawan (ESS) | Internal & outsourcing | Portal Saya: slip gaji, absensi/cuti, profil, **chat ter-scope proyek** |
| Tenant Admin *(baru)* | Pemilik/admin perusahaan outsourcing pelanggan SaaS | Kelola lisensi aplikasi, user, billing tenant sendiri |

**Pembatasan proses payrol (aturan bisnis inti v1.1):**

```
Karyawan INTERNAL                    Karyawan OUTSOURCING (proyek)
dihitung oleh HR                     dihitung oleh Operations
  → Payrol Internal                   → Payrol Proyek per klien
  → PR diajukan HR                    → approval kalkulasi oleh KLIEN
  → approve atasan → Finance          → PR diajukan Ops → approve atasan → Finance
```

HR tidak otomatis melihat payrol proyek, dan sebaliknya (RBAC per jenis run).

## 4. Portofolio Aplikasi & Packaging *(baru)*

| Aplikasi | Isi utama | Modul kode | Aksen |
|----------|-----------|-----------|-------|
| 🎯 Sales CRM | Lead/pipeline, aktivitas, konversi klien, dokumen legalitas | `presales`, `clients` | biru |
| 🧲 Recruitment | Job order, kandidat, seleksi, placement | `recruitment` | ungu |
| 💼 HR & Payroll | Karyawan internal, kontrak, dokumen HR, absensi internal, payrol internal, ESS portal | `hrd`, `ess`, `payroll` (internal) | hijau |
| 🏗️ Operations & Billing | Monitoring penempatan, absensi outsourcing, Saltab digital/payrol proyek, approval klien, Payment Request, draft invoice | `payroll` (proyek), `finance` (invoice/PR) | oranye |
| 📊 Finance & Accounting | Setara Accurate: bagan akun dinamis, jurnal & memorial, auto-journal, kas-bank, pembelian, aset tetap, periode & tutup buku, laporan lengkap + AI akuntansi | `accounting`, `finance`, `ai` | kuning-emas |
| ✒️ E-Sign | TTE tersertifikasi kontrak kerja & PKS | `esign` | merah |
| ✨ AI Add-on | Screening CV, matching, RAG kontrak, forecast, insight lintas app | `ai` | violet |

**Dependensi antar aplikasi** (install otomatis menarik dependensinya):
Recruitment & Operations membutuhkan master klien (Sales CRM); Operations
membutuhkan placement (Recruitment); Accounting menerima jurnal dari semua;
AI melintasi aplikasi sebagai add-on.

**Model harga (prinsip; angka final oleh produk, benchmark: Mekari):**

1. Langganan per aplikasi (bulanan/tahunan), skala per jumlah karyawan/user.
2. **Trial 14 hari** per aplikasi, aktivasi mandiri dari dalam produk.
3. Bundle hemat (contoh: *People Suite* = HR & Payroll + Operations & Billing).
4. **Full Package** = semua aplikasi + AI Add-on dengan diskon signifikan.
5. Upsell in-product: nav menyembunyikan app nonaktif, halaman menampilkan ajakan install/trial.
6. **Chat Workspace termasuk gratis** di semua paket — platform capability untuk
   engagement, kolaborasi, dan stickiness (bukan aplikasi berbayar).

## 5. Ruang Lingkup per Fase

Fase 1–6 (MVP presales → akunting, AI layer) dan platform awal (multi-tenant,
TTE sandbox PrivyID, rekap BPJS, ESS, kerangka mobile) — **✅ selesai**; detail
lihat [FEATURE_ROADMAP](FEATURE_ROADMAP.md). Lanjutan:

### Fase 7 — Platform Multi-App & UI Notion — ✅ Selesai (2026-08-25)

**Entitlement & lisensi**
- App registry: daftar aplikasi + metadata + grafik dependensi (single source of truth). ✅ `backend/app/core/apps.py`
- Lisensi per tenant di modul `platform`: status `trial/active/expired` per app,
  aktivasi trial mandiri, perpanjangan/upgrade dari dalam produk. ✅ Trial 14 hari sekali per app (`POST /apps/{key}/trial`);
  pengaturan langganan oleh platform admin via editor lisensi halaman Tenant.
  *Catatan perilaku: tenant hasil provisioning baru mulai tanpa lisensi; tenant default/dev full package.*
- Guard backend: endpoint app tanpa lisensi → `403`; guard frontend: nav dinamis +
  halaman upsell "Tambah aplikasi". ✅ Guard via `include_router(dependencies=...)`;
  webhook e-sign tetap terbuka. *Catatan arsitektur (ADR menyusul): `/payroll` & `/bpjs`
  sementara di-guard utuh ke HR & Payroll — Fase 9 memecah guard per `run_type`.*
- App Launcher (grid aplikasi ala Mekari) sebagai gerbang navigasi. ✅ Halaman "🚀 Aplikasi".

**Design system Notion-style**
- Token desain: Inter; teks hangat `#37352F`; border/hover sangat halus; radius 4–6px;
  sidebar abu lembut; dark mode paralel. ✅ CSS variables + retro-fit kelas lama.
- Shell baru: sidebar (workspace switcher, grup aplikasi, page tree), topbar
  breadcrumb, judul halaman emoji besar, properti metadata, view tabel/papan,
  callout block, **command palette ⌘K** lintas aplikasi. ✅ kecuali page tree
  (ditunda — belum ada konsep page user-generated) dan emoji besar baru di sebagian halaman.
- Aksen warna per aplikasi di atas satu design system yang sama. ✅
- View tabel/papan: ✅ Pipeline (kanban + pindah tahap); Kandidat menyusul.
- Callout block ✅ · Properti metadata ✅ (detail lead & karyawan terpilih).
- Referensi visual: [`docs/design/mockup-notion-ui.html`](../design/mockup-notion-ui.html).

### Fase 8 — Absensi — ✅ Selesai (2026-08-25)

- Model harian `AttendanceRecord`: tanggal, clock-in/out, jam lembur, status
  `hadir/terlambat/izin/sakit/cuti/alpa/libur/dinas-luar`, sumber `manual/impor/mobile`.
- Sumber prioritas: **impor CSV mesin fingerprint** (template + laporan baris gagal);
  input manual; mobile GPS+selfie menyusul (memanfaatkan app Flutter); pengajuan
  cuti/izin yang di-approve di ESS otomatis menjadi record absensi.
- Rekap bulanan (`AttendanceSummary`) menjadi **artefak agregasi otomatis**, bukan tempat input.
- Validasi dua jalur: internal → **HR**; outsourcing → **Operations**.
  Rekap tervalidasi menjadi masukan Saltab.

### Fase 9 — Payrol Dua Jalur, Saltab Digital, PR & Invoice — ✅ Selesai (2026-08-26)

- `Employee.employment_type` = `internal | eksternal`; `PayrollRun.run_type` =
  `internal | proyek`; run proyek **per klien per periode**. ✅
- State machine payrol proyek:
  `DRAFT → SUBMITTED_TO_CLIENT → CLIENT_REJECTED (→DRAFT) → CLIENT_APPROVED → FINANCE_PROCESSING → FINALIZED`
  Payrol internal: `DRAFT → FINANCE_PROCESSING → FINALIZED`. ✅
- Approval klien via **link ber-token** (tanpa akun): ringkasan Saltab per klien,
  tombol approve/reject + nama & catatan, kedaluwarsa token, tercatat di audit.
  Export Excel/PDF tetap tersedia sebagai lampiran email (fallback proses lama). ✅
- **Saltab digital** grid editable + ekspor Excel/PDF/CSV; BPJS dua sisi. ✅
- **Payment Request (PR)** di modul finance dengan **rantai approval multi-level
  configurable per tenant** (`GET|PUT /payment-requests/approval-chain`) — tiap tahap
  user spesifik atau peran; jejak keputusan per tahap; tanpa rantai = management/
  admin mana pun. Detail §7. ✅
- Invoice proyek otomatis saat `CLIENT_APPROVED` (rincian §6). ✅
- Jurnal otomatis saat `FINALIZED` via mesin auto-journal Fase 10
  (internal: beban gaji/BPJS; proyek: piutang ke klien). ✅

### Fase 10 — Finance & Accounting ala Accurate — ✅ Selesai (2026-08-26)

Menggantikan modul akunting minimal dengan konsep setara Accurate Online,
ditambah dimensi analisis dan AI layer sebagai pembeda. Spesifikasi penuh di §8;
ringkas:

- Bagan akun dinamis (tabel + template default jasa outsourcing, CRUD per tenant). ✅
- Jurnal umum dengan status memorial → terposting; semua modul membentuk jurnal
  lewat mesin auto-journal berbasis rule config (idempoten per dokumen sumber). ✅
- Modul transaksi: kas & bank (rekonsiliasi), pembelian (bill vendor),
  aset tetap (penyusutan bulanan otomatis); penjualan = invoice; payroll dari Fase 9. ✅
- Periode akuntansi bulanan + tutup buku (lock, jurnal ikhtisar, audit bila dibuka ulang). ✅
- Dimensi analisis klien/proyek pada baris jurnal → **laba rugi per kontrak**. ✅
- Laporan: buku besar, neraca saldo bulanan, laba rugi (bulan/YTD/per klien),
  neraca, arus kas tidak langsung, aging piutang, mutasi aset tetap. ✅
- **AI akuntansi (pembeda)**: auto-kategori + OCR, rekonsiliasi bank cerdas,
  asisten tutup buku, tanya-laporan natural language, narasi eksekutif otomatis,
  prediksi pembayaran klien, deteksi anomali/kepatuhan (§8.8). ✅

### Fase 11 — Chat Workspace ala Slack *(gratis)*

Real-time chat untuk seluruh pengguna — pendorong kolaborasi sekaligus engagement.
Spesifikasi penuh di §9; ringkas:

- Channel publik/private, DM & group DM, **broadcast channel** (khusus
  pengumuman: hanya tim Ops yang bisa posting), thread reply, emoji reaction,
  mention (@user/@channel/@here), edit/hapus pesan, unread badge, pencarian.
- **Channel otomatis per entitas**: job order (`#jo-…`), payrol per periode
  (`#payroll-{bulan}`, thread per klien), onboarding karyawan baru.
- **Notifikasi interaktif**: event sistem menjadi pesan dengan tombol aksi —
  approval PR, approve/reject klien, alert SLA job order — aksi divalidasi ulang
  di server saat ditekan.
- **Karyawan outsourcing ikut, dengan hak akses ter-scope** (detail §9.2):
  hanya channel proyeknya + DM dengan sesama karyawan se-proyek dan tim Ops
  proyek tersebut; tidak dapat menemukan/menyebut/menghubungi siapa pun di
  luar scope (Finance, Direktur, dst.) — dipaksakan di server, bukan hanya UI.
- Keanggotaan channel proyek tersinkron otomatis dari data placement.

### Fase 12 — AI Kolaborasi *(gelombang 2 chat)*

Setelah dasar chat stabil: asisten **@AEOS** via DM (RAG lintas aplikasi),
rangkuman thread panjang, digest harian channel, slash command (`/pr`, `/cuti`,
`/jo`), routing pertanyaan ke tim/peran yang tepat. Detail §9.6.

### Fase 13 — Talent Pool & CV Standardization — ✅ Selesai (2026-08-26)

Semua kandidat ("talent pool") distandarkan otomatis agar informasi seragam,
bisa dicari/difilter, dan siap dikirim ke klien dengan format konsisten.
Spesifikasi penuh di §10; ringkas:

- Upload CV (PDF/DOCX/**hasil scan/foto via OCR**) → ekstraksi + LLM ke
  **skema tetap** → draft profil terstruktur + **dokumen CV standar**.
- Dokumen CV dirender dari template dengan **branding per tenant**
  (logo, warna, footer) — nilai profesional saat submission ke klien.
- **Review step wajib**: field ber-confidence rendah ditandai; recruiter
  koreksi → finalize. File asli selalu tersimpan untuk audit.
- Screening & matching AI yang sudah ada beralih memakai data terstruktur
  (lebih akurat dan lebih murah daripada mengirim teks CV mentah).

## 6. Spesifikasi Inti: Saltab Digital *(baru)*

Pengganti dokumen Excel "Saltab". Satu `Payslip` = satu baris; komponen berupa
line-item `PayslipComponent`.

| Kelompok | Komponen | Perlakuan |
|----------|----------|-----------|
| Pemasukan (billable) | Gaji pokok **prorata**, tunjangan **prorata**, lembur, insentif, reimbursement, perjalanan dinas, kompensasi UU Cipta Kerja (ops.), THR (ops.) | Masuk gross, ditagihkan ke klien (proyek), kena PPh21 sesuai aturan |
| Potongan | PPh21, **BPJS tanggungan karyawan**, kasbon/cash advance, admin bank (non-Mandiri Rp 3.500 — config daftar bank), hold salary | Mengurangi THP |
| Pass-through | **BPJS tanggungan perusahaan** | **Bukan pendapatan karyawan** (di luar gross/THP/PPh21); ditagihkan ke klien dan masuk invoice |

Aturan perhitungan:

1. **Prorata otomatis** dari absensi tervalidasi:
   `gaji_pokok_prorata = gaji_pokok × hari_efektif ÷ hari_kerja_sebulan`
   (tunjangan idem). Nilai dapat di-*overwrite* manual di grid dengan jejak audit.
2. **THP = Σ pemasukan − Σ potongan.**
3. Grid editable ala spreadsheet + ekspor Excel/PDF (menggantikan file Saltab manual).
4. Angka BPJS dari mesin `bpjs/engine.py` (employer vs employee) menjadi satu
   sumber kebenaran untuk payslip, rekap iuran portal, dan invoice.
5. Kasbon: saldo per karyawan + cicilan n-bulan (config), potongan otomatis hingga lunas.
   Hold salary: flag + rilis pada run berikutnya sebagai komponen pemasukan.

**Komposisi invoice proyek (otomatis per klien per periode):**

| Line item | Sumber |
|---|---|
| Σ komponen pemasukan karyawan klien tsb | Saltab |
| BPJS tanggungan perusahaan | mesin BPJS |
| Fee management | % / flat dari kontrak |
| PPN | rate config (terpisah dari kode) |

## 7. Workflow Payment Request — PR *(baru)*

Satu mesin PR untuk kedua jalur (pemohon berbeda: Ops untuk proyek setelah klien
approve; HR untuk internal):

```
PR {nomor, tipe: proyek|internal, ref payroll_run, jumlah, lampiran}
DIAJUKAN (pemohon)
  → MENUNGGU_ATASAN      approver: rantai configurable per tenant (contoh: COO)
      ↘ DITOLAK (+catatan) → revisi → ajukan ulang
  → DISETUJUI_ATASAN
  → DIEKSEKUSI           Finance menjalankan pembayaran (checklist transfer per bank)
  → jurnal otomatis → Accounting
```

**Rantai approval multi-level (✅ terimplementasi):** tenant dapat mengonfigurasi
urutan tahap (`GET|PUT /payment-requests/approval-chain`, PUT khusus admin/
management) — tiap tahap menunjuk satu **user spesifik** atau satu **peran staf**.
Hanya approver tahap berjalan yang dapat memutus; setuju di tahap non-akhir
melanjutkan ke approver berikutnya (notifikasi otomatis); tolak di tahap mana pun
menggugurkan PR. Setiap keputusan tersimpan per tahap + audit log. Tanpa rantai →
management/admin mana pun memutus.

Semua transisi tercatat di modul `audit` + notifikasi in-app/email.

## 8. Spesifikasi Inti: Accounting ala Accurate *(baru)*

### 8.1 Bagan Akun (Chart of Accounts)

- Entitas `Account`: kode (format `1-1000`, dst.), nama, `parent_code` (hierarki
  grup ala Accurate), `group_type`
  (`aset_lancar · aset_tetap · liabilitas_pendek · liabilitas_panjang · ekuitas ·
  pendapatan · hpp · beban_usaha · beban_lain · pendapatan_lain`),
  saldo normal (debit/kredit), flag `is_cash_bank`, `is_control_ar_ap`, `is_active`.
- Saldo akun **tidak disimpan** — selalu dihitung dari jurnal (single source of truth).
- Template default ±60 akun untuk jasa outsourcing: PPN Keluaran/Masukan,
  Utang Gaji/PPh21/BPJS, Piutang Klien, Uang Muka Klien, kelompok aset tetap +
  akumulasi penyusutan, prive, laba ditahan, dst.
- CRUD per tenant; akun yang sudah termutasi tidak boleh dihapus.

### 8.2 Jurnal Umum & Memorial

- `JournalEntry.status`: `memorial` (draft) → `posted`. Saat posting divalidasi:
  debit = kredit, tanggal dalam periode `open`, semua akun aktif.
- `JournalLine` bertambah kolom: `account_id` (FK ke bagan akun), dimensi analisis
  `client_id` / `project_id` (opsional), memo baris.
- Aturan arsitektur: modul lain **tidak boleh** menulis tabel jurnal langsung —
  hanya melalui mesin auto-journal (8.3).

### 8.3 Mesin Auto-Journal

- Config `JournalRule` per tenant: `event_code → pasangan akun debit/kredit +
  sumber nilai`. Contoh event: `invoice_issued`, `invoice_paid`,
  `payroll_finalized_internal`, `payroll_finalized_proyek`, `pr_executed`,
  `purchase_bill_received`, `purchase_bill_paid`, `asset_acquired`,
  `depreciation_monthly`, `asset_disposed`, `opening_balance`.
- **Idempoten**: satu dokumen sumber → tepat satu jurnal (unique constraint pada ref).
- Setiap jurnal menyimpan referensi balik ke dokumen sumber (invoice / payroll run /
  bill / aset) sehingga setiap angka laporan dapat ditelusuri asalnya.

### 8.4 Modul Transaksi

| Modul | Isi | Jurnal otomatis |
|---|---|---|
| Penjualan | Invoice (modul finance, sudah ada) | Dr Piutang Usaha / Cr Pendapatan + Cr PPN Keluaran |
| Kas & Bank | Penerimaan/pembayaran, transfer antar rekening, **rekonsiliasi bank** | Dr/Cr Kas-Bank vs akun lawannya |
| Pembelian | Bill vendor (operasional, kantor, reimbursement klien) + status utang | Dr Beban/Aset + Dr PPN Masukan / Cr Utang Usaha |
| Aset Tetap | Daftar aset, metode garis lurus, masa manfaat | Perolehan; **penyusutan bulanan otomatis**; disposisi |
| Payroll | Dari Fase 9 (`FINALIZED`) | Dr Beban Gaji+BPJS / Cr Utang Gaji, PPh21, BPJS |

### 8.5 Periode & Tutup Buku

- `AccountingPeriod` per bulan dengan status `open/closed`.
- Tutup buku = lock periode + jurnal ikhtisar otomatis (L/R → Laba Ditahan Tahun Berjalan).
- Input backdate ke periode tertutup ditolak; pembukaan ulang periode wajib
  meninggalkan jejak di modul audit.

### 8.6 Dimensi Analisis Klien/Proyek

- Baris jurnal dapat diberi dimensi klien/kontrak → **laba rugi per kontrak klien**
  (pendapatan − biaya langsung tenaga kerja − reimbursable).
- Laporan konsolidasi tetap level entitas; dimensi hanya memecah analitik —
  pembeda vertikal untuk pitch "margin per klien".

### 8.7 Laporan

Buku besar per akun per periode · neraca saldo bulanan + YTD · laba rugi
bulanan/YTD **dan per dimensi klien** · neraca · **arus kas metode tidak
langsung** · aging piutang · kartu utang · mutasi & depresiasi aset tetap.

### 8.8 AI Layer Akuntansi (pembeda)

Memanfaatkan infrastruktur modul `ai` yang ada (LLM kompatibel OpenAI, RAG,
embedding). Semua jawaban AI berbasis data terstruktur yang bisa diverifikasi,
bukan teks bebas.

| # | Fitur | Nilai |
|---|-------|-------|
| 1 | **Auto-kategori + OCR** — foto faktur/nota/bill → draft transaksi pembelian + saran COA (belajar dari riwayat tenant) | Input berkali-kali lipat lebih cepat; akurasi naik seiring pemakaian |
| 2 | **Rekonsiliasi bank cerdas** — impor mutasi rekening, matching fuzzy ke jurnal/invoice, penjelasan item yang tidak cocok | Tutup buku cepat; uang menggantung ketahuan |
| 3 | **Asisten tutup buku** — checklist otomatis: selisih balance, invoice tanpa jurnal, mutasi anomali, usulan jurnal penyesuaian | Mengurangi ketergantungan pada akuntan senior |
| 4 | **Tanya laporan (NL → SQL terverifikasi)** — "Berapa margin proyek Bank Daerah Jaya Q3?" dijawab dari query ter-audit | Eksekusi/sales bisa analisis mandiri tanpa Excel |
| 5 | **Narasi eksekutif otomatis** — ringkasan bulanan Bahasa Indonesia + sorotan per kontrak | Manajemen hemat waktu membaca laporan |
| 6 | **Prediksi pembayaran klien** — skor risiko telat bayar dari histori invoice → prioritas collection | Cash flow lebih terprediksi |
| 7 | **Deteksi anomali & kepatuhan** — duplikasi bill, transaksi tak wajar, sanity-check PPN sebelum pelaporan | Menurunkan risiko kesalahan pajak |

## 9. Spesifikasi Inti: Chat Workspace ala Slack *(baru)*

### 9.1 Konsep & Model Data

| Konsep | Implementasi |
|---|---|
| Workspace | = tenant |
| Channel | `type`: public · private · dm · broadcast · entity-linked; `scope`: tenant \| project (+ref entitas/proyek) |
| Keanggotaan | `ChannelMember` — untuk channel proyek diturunkan otomatis dari placement |
| Pesan | `Message` — `parent_id` untuk thread, edit terlacak, soft delete |
| Interaksi | `Reaction` (emoji), pin/bookmark, reminder |
| Belum dibaca | `ReadState` per user per channel → unread badge |
| Lampiran | memakai modul storage yang ada |
| Pencarian | PostgreSQL full-text search (config Bahasa Indonesia) |

### 9.2 Model Hak Akses (bagian paling kritis)

| Peran | Direktori user | Channel | Mention/DM |
|---|---|---|---|
| Admin, Management, Finance, HR, Business Dev, Recruiter, Operations | seluruh tenant | semua channel tenant + semua proyek | siapa pun |
| **Karyawan outsourcing** (akun ESS, role `karyawan`) | **hanya**: sesama karyawan se-proyek + anggota tim Ops proyeknya | channel proyeknya (`#proyek-…`, broadcast read-only) | hanya anggota scope — autocomplete menyaring dan server menolak mention di luar scope |

Aturan penguat:

1. Scope karyawan = himpunan proyek dari **placement aktif**-nya (bisa >1).
2. Placement berakhir/pindah → keanggotaan channel dicabut otomatis; akses baca
   arsip channel lama hilang (privasi antar klien).
3. Broadcast channel proyek: Ops mengumumkan jadwal/shift; karyawan hanya bisa baca & reaction.
4. Semua batasan dipaksakan di **server** (REST + WebSocket): pencarian direktori,
   autocomplete mention, validasi mention per pesan, DM initiation.
5. Karyawan internal (staff) tidak terbatas.

### 9.3 Channel Otomatis & Integrasi Entitas

- Job order dibuat → `#jo-{klien}-{posisi}` (anggota: recruiter + tim Ops terkait).
  Thread diskusi halaman job order me-link ke channel ini.
- Payrol proyek disubmit → pesan status di `#payroll-{bulan}` dengan ringkasan
  per klien; perubahan status approval klien ikut ter-update sebagai pesan sistem.
- Placement baru → invite ke `#proyek-{klien}` + thread onboarding.
- Notifikasi interaktif: kartu pesan dengan tombol (Approve/Reject PR, dsb.);
  penekanan tombol tetap divalidasi ulang RBAC di server; hasil aksi dikirim
  sebagai balasan thread.

### 9.4 Teknis

- WebSocket native FastAPI; handshake autentikasi JWT yang sama dengan REST.
- Presence & typing indicator bersifat ephemeral (tidak dipersisten).
- Delivery idempoten: klien melakukan dedup berdasarkan message id.
- Scale-out multi-instance nanti memakai Redis pub/sub — desain manager
  koneksi dibuat pluggable sejak awal.

### 9.5 Moderasi & Keamanan

Admin tenant dapat menghapus pesan siapa pun; pengguna dapat melaporkan pesan;
semua moderasi tercatat di audit log. Data pribadi karyawan tidak tampil lintas
scope. Chat bukan kanal dokumen legal — kontrak/PKS tetap lewat modul dokumen+TTE.

### 9.6 Gelombang 2 — AI Kolaborasi

1. **@AEOS** di DM: jawaban atas pertanyaan tenant via RAG lintas aplikasi yang sudah ada.
2. **Rangkuman thread** panjang menjadi poin-poin keputusan/tugas.
3. **Digest harian**: ringkasan aktivitas channel penting (approval menunggu, SLA).
4. **Slash command**: `/pr buat…`, `/cuti ajukan…`, `/jo status…`.
5. Routing pertanyaan ke tim/peran yang tepat bila AI tidak bisa menjawab.

## 10. Spesifikasi Inti: Talent Pool & CV Standardization *(baru)*

### 10.1 Pipeline Pemrosesan CV

```
Upload (PDF / DOCX / scan / foto)
  → deteksi jenis dokumen: ada text-layer? (pypdf/python-docx) : OCR
  → normalisasi teks + pembersihan layout
  → LLM structured extraction → JSON sesuai skema tetap (validasi ketat)
  → draft profil kandidat + render draf CV standar bertemplate
  → REVIEW recruiter: field ber-confidence rendah disorot wajib dicek
  → FINALIZE → masuk talent pool, siap matching & submission
```

- **Confidence score per field**; di bawah threshold = wajib review manusia.
- File asli tidak pernah ditimpa/dihapus — tersimpan sebagai bukti sumber.
- Pipeline bisa dijalankan ulang (re-process) saat skema/prompt naik versi.

### 10.2 Skema Data Kandidat Seragam

| Kelompok | Field |
|---|---|
| Identitas | Nama lengkap, no. HP, email, domisili (kota), tanggal lahir |
| Pendidikan | Jenjang, institusi, jurusan, tahun lulus, IPK (opsional) — array |
| Pengalaman kerja | Perusahaan, posisi, periode, industri (ops.), ringkasan tugas — array |
| Skill & sertifikasi | Skill (array), sertifikasi {nama, penerbit, tahun}, bahasa + tingkat |
| Khas outsourcing | **Kesiapan penempatan** (segera/n-minggu), **lokasi yang bersedia** (multi-kota), **expected salary**, preferensi jenis kontrak |
| Meta | Sumber CV, tanggal masuk, status talent pool (baru · diproses · placed · non-aktif) |

### 10.3 Dokumen CV Standar

- Render HTML → PDF dari template tenant: logo, warna aksen, footer kontak
  (konfigurasi branding per tenant).
- Struktur selalu sama: header identitas → ringkasan profil → pengalaman →
  pendidikan → skill/sertifikasi → data penempatan.
- **Versi & snapshot**: tiap finalize membuat versi baru; saat kandidat
  disubmit ke job order, PDF versi terkunci ikut tersimpan sebagai bukti
  apa yang dikirim ke klien pada waktu itu.
- Tampilkan foto kandidat: toggle opsional per tenant (beberapa klien mensyaratkan).

### 10.4 AI & Infrastruktur

- OCR sejak awal: dokumen tanpa text-layer diproses lewat model vision pada API
  LLM yang sudah dikonfigurasi (satu panggilan: OCR + ekstraksi terstruktur).
- DOCX memakai parser python-docx; prompt & skema berversi (config terpisah).
- Screening/matching AI (Fase 6) membaca data terstruktur ini, bukan teks mentah.

### 10.5 Integrasi & Kepatuhan

- Filter/facet pencarian talent pool per field skema (domisili, skill, kesiapan, dsb.).
- Submission kandidat otomatis melampirkan CV standar versi terkunci.
- CV berisi data pribadi → patuh UU PDP: consent saat sumber eksternal, retensi
  configurable, hak hapus atas permintaan subjek.

## 11. Kebutuhan Non-Fungsional

| Aspek | Kebutuhan |
|-------|-----------|
| Arsitektur | Modular monolith (FastAPI); batas modul dijaga; entitlement tanpa memecah deployment |
| Frontend | React SPA; **design system Notion-style** (§Fase 7); responsif; Bahasa Indonesia |
| Data | PostgreSQL; file di object storage MinIO/S3; SQLite+folder lokal untuk dev |
| Multi-tenant | Shared schema + `tenant_id`; provisioning via `/platform/tenants`; lisensi per tenant |
| Keamanan | JWT, RBAC per peran **dan per jenis payrol**; token approval klien berbatas waktu & cakupan; audit trail penuh |
| Kepatuhan | Rate/config pajak-BPJS-bank **terpisah dari kode**; retensi dokumen; opsi self-host |
| Deployment | Docker Compose (Caddy TLS produksi); path Kubernetes terbuka |
| Realtime | WebSocket native FastAPI untuk chat & notifikasi interaktif; Redis pub/sub saat scale-out multi-instance |

## 12. Metrik Keberhasilan

Operasional (warisan v1.0, dievaluasi dengan data riil):

1. 100% klien baru & lead tercatat di sistem dalam 1 bulan pemakaian.
2. Waktu pencarian dokumen legalitas klien < 1 menit.
3. Time-to-submit kandidat per job order turun ≥ 30%.
4. Tidak ada kontrak/addendum lewat jatuh tempo tanpa reminder.

Tambahan v1.1 (fokus Saltab & komersial):

5. Waktu penyusunan Saltab per siklus turun ≥ 70% vs Excel manual.
6. **Nol selisih** angka antara Saltab ↔ slip gaji ↔ rekap BPJS ↔ invoice.
7. Siklus approval klien (submit → approve) terukur; target median ≤ 2 hari kerja.
8. Pasca Fase 7: ≥ 1 tenant eksternal aktif berbayar dalam 6 bulan.
9. Pasca Fase 10: tutup buku bulanan ≤ 3 hari kerja dengan asisten AI.
10. Pasca Fase 11 (engagement): WAU chat tim staff ≥ 70% dalam 3 bulan;
    ≥ 50% karyawan outsourcing aktif bulanan di channel proyeknya.
11. Pasca Fase 13: median waktu CV mentah → profil final < 5 menit; akurasi
    ekstraksi field inti ≥ 90% sebelum review.

## 13. Halaman & Alur Utama

Shell baru (lihat mockup): sidebar workspace → grup aplikasi → halaman; app
launcher; ⌘K lintas app; tema terang/gelap.

```
Login ──► Beranda (ringkasan lintas app yang dilisensikan)
  🎯 Sales CRM        : Pipeline (tabel/papan), Klien + dokumen legalitas
  🧲 Recruitment      : Job Orders, Kandidat (upload CV → auto-profil + CV
                        standar bertemplate, screening AI, placement)
  💼 HR & Payroll     : Karyawan internal, Absensi internal, Payrol internal, Portal Saya (ESS)
  🏗️ Ops & Billing    : Penempatan, Absensi outsourcing, Saltab proyek (grid),
                        Approval klien (token), Payment Request, Draft Invoice
  📊 Fin & Acc        : PR queue & eksekusi, Invoice, Kas & Bank, Pembelian,
                        Aset Tetap, Tutup Buku, Jurnal & Bagan Akun,
                        Laporan (termasuk per klien), Tanya-Laporan AI
  💬 Chat             : Channel, DM, thread — tersambung entitas (job order,
                        payrol, proyek); karyawan outsourcing ter-scope
  ✒️ E-Sign · ✨ AI    : Dokumen TTE · Asisten & insight
```

## 14. Batasan & Asumsi

- Multi-tenant shared schema sudah dibangun dan dipertahankan; isolasi per tenant
  via `tenant_id` + RBAC.
- TTE tersertifikasi via integrasi PrivyID — sandbox dulu, kredensial produksi menyusul.
- Regulasi (PPh21 TER, BPJS, PPN) berubah berkala: semua rate di config table,
  versi tarif dicatat per periode payroll agar laporan historis tetap konsisten.
- Approval klien ber-token dirancang read-only dan terbatas periode; klien tidak
  menjadi user penuh di fase ini.
- Mobile app (Flutter) tetap kanal sekunder; prioritas utama tetap web.
- CV kandidat = data pribadi (UU PDP): consent, retensi configurable, hak hapus
  atas permintaan subjek; template CV standar tidak boleh menampilkan data
  sensitif di luar yang disetujui tenant.
- Chat adalah kanal operasional harian, bukan pengganti dokumen legal; retensi
  pesan mengikuti kebijakan tenant. Moderasi menjadi tanggung jawab admin
  tenant — sistem menyediakan alatnya (hapus pesan, lapor, audit log).
