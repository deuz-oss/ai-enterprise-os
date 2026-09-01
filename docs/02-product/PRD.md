# Product Requirements Document (PRD)

**Produk:** AI Enterprise OS — operating system untuk perusahaan outsourcing &
workforce umum (portofolio aplikasi modular, model bisnis ala Mekari)
**Pemilik Produk:** Brian — Head of Business & Operations
**Versi:** 3.1 · **Status:** Approved — 4-Cloud Metered SaaS, Talent-Centric
**Terakhir diperbarui:** 2026-09-01

> **Dokumen ini adalah gabungan (reconciled) dari PRD v1.4 + patch v2.0/v2.1/
> v3.0/v3.1** yang sebelumnya tersimpan sebagai file terpisah
> (`PRD-v2.0-Internal-First.md`, `PRD-v2.1-Revisi.md`, `PRD-v3.0.md`,
> `PRD-v3.1-Revisi.md`) dan tidak pernah digabung balik ke sini. File-file
> patch itu tetap disimpan sebagai arsip sejarah keputusan, tapi PRD.md ini
> yang jadi rujukan status implementasi terkini.

> **Changelog**
> - **v3.1 (2026-09-01)** — **5 patch atas v3.0** (audit gap + riset arsitektur
>   pembanding, detail keputusan di `PRD-v3.1-Revisi.md`): **AI Usage
>   Metering** (`ai_usage_events`, instrumentasi sentral di `core/llm.py`,
>   16 titik panggil dilabeli `feature`) — ✅ selesai, AI sudah live pakai
>   provider berbayar (keputusan bisnis: performa dulu, biaya ditagih ke
>   klien + margin, bukan lagi self-hosted gratis). **Recruitment Pipeline
>   13-tahap** (`PlacementStatus` sourced→...→onboarded, `requires_ojt`,
>   `InterviewSchedule.interview_type`) — ✅ selesai. **Job Order field
>   tambahan** (request_id, request_date+alert 30 hari, area,
>   contract_duration, gross_salary, business_status, upload dokumen+AI
>   auto-fill) — ✅ selesai. **Job Portal** (lamaran publik guest-apply per
>   `{tenant_slug}`, `is_public`/`public_client_label` biar identitas klien
>   tersamar) — ✅ selesai. **AI Interview** (template+kriteria terpisah dari
>   instance, gate approval manusia wajib, mode async dulu bukan voice
>   real-time) — ❌ **baru riset arsitektur + desain skema, belum ada
>   kode sama sekali.** Juga (di luar 5 patch, ditemukan lewat audit
>   terpisah): 4 perbaikan accounting — reversal/void jurnal posted, hapus
>   jurnal memorial, AP aging, cek penyusutan otomatis di close checklist —
>   semuanya ✅ selesai.
> - **v3.0 (2026-08-30)** — **Restrukturisasi jadi 4 SKU metered + Foundation**
>   (menggantikan model bundle 6-aplikasi v2.0/v2.1, lihat §4): **Talent
>   Cloud** (Rp 15k/talent aktif + Rp 2k/match, AI Matching native 0-100+
>   explain, bukan add-on lagi), **Workforce Cloud** (Rp 10k/employee,
>   asuransi one-to-many `employee_insurances`, BPJS +status+kartu+valid_until),
>   **Revenue Cloud** (Rp 5k/invoice + Rp 8k/faktur, e-Faktur DJP lengkap:
>   NPWP lawan, DPP, kode transaksi, no seri unik/tenant/tahun, QR, flow
>   batal/pengganti), **Govern Cloud** (flat Rp 5-7jt, accounting Accurate.id
>   lokal — tetap §8, tidak berubah). Mode operasi per-tenant
>   (`tenants.billing_mode inherit|internal|commercial`) supaya deployment
>   yang sama bisa jalan internal & komersial berbarengan. Dashboard 9 widget
>   cross-bundle. Sales CRM: klien `prospek→aktif` otomatis saat placement
>   pertama. Mobile dapat tab Chat baru. Semua ✅ selesai & sinkron kode.
> - **v2.1 & v2.0 (2026-08-27/28)** — draft transisi menuju struktur v3.0 di
>   atas (bundle 6-aplikasi awal, lisensi per-app) — **digantikan penuh**
>   oleh v3.0, tidak ada sisa konten yang perlu dipertahankan terpisah.
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

## 4. Portofolio Aplikasi & Packaging — 4 Cloud Metered *(v3.0, menggantikan bundle 6-aplikasi v1.4/v2.0/v2.1)* ✅

Sejak v3.0 (2026-08-30), packaging direstrukturisasi dari 7 aplikasi berlisensi
independen menjadi **Foundation gratis + 4 SKU metered ("Cloud") + AI Add-on**
— lebih dekat ke model konsumsi (bayar sesuai pakai) daripada kursi/lisensi
statis, dan lebih jujur secara bisnis: Talent Cloud menagih per record kandidat
yang tenant SIMPAN + per klik Match yang tenant JALANKAN (bukan jualan
kandidat — kandidat tetap milik tenant, di-upload sendiri via `POST
/talentpool/intake`).

### 4.1 Mode Operasi — Internal vs Komersial per Tenant

Satu deployment yang sama bisa melayani tenant internal (semua fitur aktif
tanpa cek lisensi) dan tenant SaaS berbayar (lisensi per SKU) berbarengan:

| Level | Config | Efek |
|---|---|---|
| Global default | `APP_MODE=internal\|commercial` (`.env`, `backend/app/core/config.py`) | Fallback kalau tenant tidak override |
| Per-tenant override | `tenants.billing_mode: inherit\|internal\|commercial` (`PATCH /platform/tenants/{id}/billing-mode`, platform_admin saja) | `internal` → bypass guard lisensi walau `APP_MODE=commercial` global; `commercial` → tetap enforce walau global `internal` |

Urutan guard (`core/security.py`): `billing_mode=internal` menang duluan →
baru `billing_mode=commercial` → baru fallback `APP_MODE` global. Tenant
`default` (dev/demo) di-seed `internal` (full akses tanpa lisensi).

### 4.2 Foundation — Gratis, Selalu Aktif (semua tenant)

| Kapabilitas | Isi |
|---|---|
| Dashboard Umum | `GET /overview` (+ `/overview/personal` role-aware) — 9 widget lintas Cloud, lihat §8 |
| Chat Workspace | Channel/DM/thread ala Slack (§9) — gratis di semua paket, platform capability untuk engagement |
| Pages | Notion-style docs (`/pages`) |

### 4.3 Empat SKU Metered

| Cloud | Modul kode (`apps.py`) | Isi utama | Skema tagihan | Bergantung ke |
|---|---|---|---|---|
| 🎯🧲 **Talent Cloud** | `sales_crm` + `recruitment` | Pipeline lead, klien (auto `prospek→aktif` saat placement pertama), Job Order (pipeline 13-tahap §5), Talent Pool + CV standar, **AI Matching native 0-100+explain** (bukan add-on lagi), Job Portal publik, jadwal interview, offering (esign), onboard | Rp 15rb / talent aktif / bulan + Rp 2rb / eksekusi match | — (standalone) |
| 💼 **Workforce Cloud** | `people_ops` | Karyawan, kontrak, dokumen legal, BPJS (no+status+kartu+`valid_until`), **asuransi one-to-many** (`employee_insurances`: provider/no polis/status/valid_until/kartu), absensi, ESS portal, TTE | Rp 10rb / employee aktif / bulan | — (standalone) |
| 📊 **Revenue Cloud** | `payroll` + `finance` | Payrol dua jalur (saltab, BPJS dual-side, PPh21, bukti potong), invoice, **e-Faktur DJP lengkap** (NPWP lawan, DPP, kode transaksi, no seri unik/tenant/tahun, QR, flow kirim/batal/pengganti), aging, cash flow, Payment Request | Rp 5rb / invoice + Rp 8rb / faktur DJP + base Rp 1jt/bulan | `workforce` |
| 🏛️ **Govern Cloud** | `accounting` | Setara Accurate.id: bagan akun dinamis, jurnal memorial→posted, mesin auto-journal, kas-bank, pembelian, aset tetap, periode & tutup buku, laporan lengkap + AI akuntansi (§8) | Flat Rp 5-7jt / bulan | `revenue` |
| ✨ **AI Add-on** | `ai_addon` | `@AEOS` lintas app, RAG kontrak, forecast (matching sudah native di Talent, bukan di sini lagi) | Rp 300 / 1.000 token (diukur nyata via `ai_usage_events`, lihat Fase 17 §5) | — |

**Contoh tagihan** (80 talent aktif, 80 employee, 5 invoice, 5 faktur/bulan):

| Paket | SKU included | Estimasi/bulan |
|---|---|---|
| Starter | Foundation + Workforce | ~Rp 800rb |
| Growth | Starter + Talent | ~Rp 2,02jt |
| Scale | Growth + Revenue | ~Rp 3,09jt |
| Enterprise | Scale + Govern | ~Rp 10,09jt |

Trial 14 hari per SKU (base Rp 1jt untuk Revenue Cloud tetap berlaku saat trial). Upsell in-product: nav menyembunyikan Cloud nonaktif, halaman menampilkan ajakan install/trial.

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

### Fase 12 — AI Kolaborasi — ✅ Selesai (2026-08-26)

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

### Fase 14 — Restrukturisasi 4-Cloud Metered (v3.0) — ✅ Selesai (2026-08-30)

Detail bisnis penuh di §4. Highlight teknis:

- **AI Matching native** 0-100+explain, native di Talent Cloud (bukan add-on
  lagi): `POST /recruitment/job-orders/{jo_id}/match` — embedding cosine +
  rules (domisili, readiness, expected salary) + LLM rerank, sumber dari
  `CvIntake.extracted` terstruktur (bukan teks CV mentah).
- **Asuransi one-to-many** (`employee_insurances`: provider, no polis,
  status, `valid_until`, kartu+polis object key) menggantikan field asuransi
  tunggal lama; BPJS tambah `status`+`card_key`+`valid_until` per jenis.
- **e-Faktur DJP lengkap**: `tax_invoice_no`, status faktur (`belum_buat` →
  `draft` → `menunggu_approval` → `terkirim_djp` → `approved`/`ditolak` →
  `dibatalkan`/`pengganti`), NPWP+nama+alamat lawan transaksi, DPP, kode
  transaksi, no seri unik per tenant per tahun, QR, payload TEXT tersimpan;
  simulasi lokal tanpa hit DJP kalau `efaktur_provider` kosong.
- **Dashboard Umum 9 widget** lintas Cloud + `GET /overview/personal`
  role-aware; **Mode Operasi per-tenant** (§4.1); klien `prospek→aktif`
  otomatis saat placement pertama (idempoten, audit).
- **Mobile**: tab Chat baru di aplikasi Flutter (talent tetap desktop-only).

### Fase 15 — Recruitment Pipeline 13-Tahap + Job Order Field Tambahan — ✅ Selesai (2026-09-01)

Detail keputusan bisnis di `PRD-v3.1-Revisi.md` Patch 2+3 (patch v3.1
sekarang tergabung di sini). Alasan: pipeline rekrutmen v3.0 ("3 action:
interview/offering/onboard") terlalu kasar dibanding alur operasional nyata.

- `PlacementStatus` (bukan `CandidateStatus` — satu kandidat bisa dikejar
  untuk >1 JO sekaligus dengan tahap berbeda) diperluas 4→13 nilai:
  `sourced → screening → interview_rekruter → disubmit → dikirim_ke_klien →
  screening_klien → interview_klien → ojt → proposed → accepted → onboarded`
  (+ `rejected`/`cancelled` terminal dari tahap manapun).
- `JobOrder.requires_ojt` (per-JO, bukan per-klien — posisi klien yang sama
  bisa beda kebijakan OJT); UI skip tahap OJT kalau `False`.
- `InterviewSchedule.interview_type` (internal/klien) — 1 kandidat bisa
  punya jadwal internal & klien yang jelas beda perannya.
- **Job Order — field operasional tambahan**: `request_id` (auto-generate
  `JO/{tahun}/{urutan}` kalau klien tidak kasih), `request_date` + alert
  stale ≥30 hari masih `open`, `area`, `contract_duration_months`,
  `gross_salary` (field baru, terpisah dari `salary_min/max` yang tetap
  dipakai AI Matching), `business_status` (Open/OnHold/Cancel/Filled —
  konsep terpisah dari status pipeline di atas, bukan pengganti).
- **Upload dokumen Job Order** ("Manpower Requisition" fisik) → AI
  auto-fill field JO (pola sama seperti CV Intake); dokumen sumber
  tersimpan, bisa dilihat lagi lewat klik Request ID di tabel JO.

### Fase 16 — Job Portal: Lamaran Publik — ✅ Selesai (2026-09-01)

Detail di `PRD-v3.1-Revisi.md` Patch 5. Sumber sourcing kandidat baru selain
Talent Pool internal: kandidat apply sendiri ke lowongan yang di-post publik.

- Guest-apply tanpa akun (kandidat AEOS tidak pernah punya akun `User`) via
  `invite_token`-style link, ke `JobOrder` yang ditandai `is_public=True`.
- Portal per-tenant (`/careers/{tenant_slug}`) — sejalan sifat white-label
  AEOS, bukan satu marketplace gabungan lintas-tenant.
- `public_client_label` menyamarkan nama klien asli di lowongan publik
  (kebutuhan nyata: dokumen Job Order internal SPC eksplisit mensyaratkan
  identitas klien disembunyikan dari lowongan publik).
- Screening question custom per JO mengurangi beban tahap `screening`
  manual (Fase 15) untuk lamaran yang masuk lewat jalur ini.
- Reuse penuh pipeline `CvIntake` (ekstraksi CV) yang sudah ada — tidak ada
  duplikasi logic ekstraksi antara jalur staf dan jalur publik.

### Fase 17 — AI Usage Metering — ✅ Selesai (2026-09-01)

Detail di `PRD-v3.1-Revisi.md` Patch 1. Prasyarat wajib sebelum fitur AI
apa pun ditambah lagi (termasuk Fase berikutnya, AI Interview) — SKU **AI
Add-on** (§4.3) sudah dijanjikan harga per-token sejak v3.0, tapi sampai
sebelum fase ini tidak ada satu pun mekanisme yang benar-benar menghitung
pemakaian token per tenant.

- Tabel `ai_usage_events` (tenant, feature, model, token in/out, status,
  `cost_idr` best-effort/nullable) diinstrumentasi **sentral** di satu
  titik pemanggilan AI (`core/llm.py`), bukan manual di tiap titik panggil
  — 16 titik panggil AI di 8 modul otomatis ikut terinstrumen, tak satu
  pun bisa lupa.
- Token mentah jadi sumber kebenaran (harga vendor berubah-ubah; dihitung
  ulang jadi Rupiah kapan saja tanpa migrasi data).
- Konsekuensi langsung: AI sekarang genuinely aktif di lingkungan produksi
  (pakai model berbayar/frontier — keputusan bisnis eksplisit: performa
  dulu, biaya ditagih ke klien + margin, bukan lagi self-hosted gratis).

### Fase 18 — Accounting: Reversal, Hapus Memorial, AP Aging, Cek Penyusutan — ✅ Selesai (2026-09-01)

Bukan bagian dari patch v3.1 manapun — ditemukan lewat audit terpisah
terhadap 8 area accounting, disatukan di sini karena masing-masing kecil.
Detail teknis di §8 (accounting tetap §8 v1.4, keempat fixed ini
melengkapinya):

- **Reversal/void jurnal posted** (`POST /journal/{id}/reverse`) — gap
  prioritas tertinggi: sebelumnya tidak ada cara membalik jurnal `posted`
  selain koreksi manual tanpa jejak. Jurnal asli TIDAK pernah diedit/dihapus
  (higiene akuntansi standar) — reversal selalu entri BARU dengan
  debit/kredit tertukar per baris.
- **Hapus jurnal memorial** (`DELETE /journal/{id}`) — draft yang batal
  sekarang bisa dibersihkan; jurnal `posted` tetap ditolak (pakai reversal).
- **AP aging** (`GET /cashbank/bills/aging`) — utang vendor jatuh tempo per
  bucket 1-30/31-60/>60, mencerminkan aging piutang (§8.7) yang sudah lama
  ada di sisi AR.
- **Cek penyusutan otomatis** — checklist tutup buku (§8.8 #3) sekarang
  memperingatkan aset tetap yang belum disusutkan periode berjalan
  (severity warning, tidak memblokir closing); plus endpoint batch
  `POST /assets/depreciate-period` supaya tidak perlu klik aset satu-satu.

### Berikutnya — AI Interview *(v3.1 Patch 4 — riset & desain selesai, KODE BELUM ADA)*

Kapabilitas penilaian kandidat berbasis AI di bawah Talent Cloud, pelengkap
`InterviewSchedule` manual yang sudah ada. Riset arsitektur (5 repo
open-source pembanding) dan desain skema tabel/endpoint penuh sudah
selesai dan tersimpan di plan file kerja — **belum ada satu baris kode pun**
(`backend/app/modules/ai_interview/` belum eksis). Ringkasan arah:

- 2 entitas baru: `AIInterviewTemplate` (definisi: pertanyaan bertipe +
  kriteria penilaian) terpisah dari `AIInterviewResponse` (instance per
  kandidat, akses via token tanpa akun — pola sama seperti Job Portal).
- **MVP mode async** (kandidat jawab teks/rekaman, dinilai belakangan) —
  BUKAN voice real-time (kompleksitas infra jauh lebih tinggi; kalau nanti
  dibutuhkan, rekomendasi riset adalah "beli" kapabilitas voice dari vendor
  pihak ketiga, bukan bangun sendiri).
- Skor AI **wajib** direview manusia (`review_status`) sebelum final —
  tidak pernah otomatis jadi keputusan hire/reject, mengikuti prinsip
  `CONFIDENCE_THRESHOLD` yang sudah dipakai di CV Intake.

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

### 9.6 Gelombang 2 — AI Kolaborasi *(✅ terimplementasi)*

1. **@AEOS** di DM: jawaban atas pertanyaan tenant via RAG lintas aplikasi yang sudah ada.
   Mention `@AEOS` di channel/DM mana pun memicu jawaban dari data lintas app
   terverifikasi (pipeline, job order, kandidat, karyawan, PR, invoice, payrol,
   laba rugi); balasan diposting sebagai pesan bot AEOS per tenant. Tanpa
   `AI_BASE_URL` tetap berfungsi dengan ringkasan deterministik.
2. **Rangkuman thread** panjang menjadi poin-poin keputusan/tugas — tombol 🧵 Rangkum
   pada thread; hasil diposting AEOS ke thread.
3. **Digest harian**: 📋 panel digest di Chat — item deterministik: PR menunggu
   approval, payrol menunggu persetujuan klien, job order jatuh tempo ≤7 hari,
   kontrak berakhir ≤14 hari, invoice overdue. Karyawan melihat versi portal
   (cuti menunggu + pengingat clock GPS).
4. **Slash command** dieksekusi server-side: `/help`, `/pr status`, `/jo status [kw]`,
   `/cuti sisa`, `/cuti ajukan <jenis> <mulai> <selesai> [alasan]` — perintah
   personal hanya di DM (privasi); hasil dijawab bot AEOS sebagai thread reply.
5. Routing pertanyaan ke tim/peran yang tepat bila AI tidak bisa menjawab:
   kata kunci dipetakan ke Finance / HR-Ops / HR / Recruiter / Business Dev dan
   disertakan pada balasan @AEOS.

Pemisahan paket: fitur AI (@AEOS, rangkuman) ter-guard lisensi **ai_addon**;
slash command & digest gratis mengikuti chat.

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

Tambahan v3.0/v3.1 (4-Cloud metered, AI Interview menyusul):

12. Auto `prospek→aktif` ≥ 95% dari placement pertama tercatat via audit
    `client.auto_activated` (Fase 14).
13. Faktur DJP terbit ≤ 1 hari kerja setelah `Invoice.sent` (Fase 14).
14. Median AI Matching talent→final <5 menit, akurasi field ekstraksi ≥90%,
    match-click→hire conversion terlacak (Fase 14).
15. Interview→onboard median ≤14 hari kerja (Fase 15).
16. **100% panggilan AI tercatat** di `ai_usage_events` (nol panggilan tak
    terlacak) — prasyarat langsung penagihan SKU AI Add-on akurat (Fase 17).
17. Job Portal: ≥1 lamaran masuk lewat jalur publik per tenant aktif dalam
    3 bulan pasca-aktivasi (Fase 16) — indikator kanal sourcing baru benar
    dipakai, bukan cuma tersedia.

## 13. Halaman & Alur Utama

Shell baru (lihat mockup): sidebar workspace → grup Cloud → halaman; app
launcher; ⌘K lintas app; tema terang/gelap. Pengelompokan halaman berikut
mengikuti struktur 4-Cloud sejak v3.0 (§4) — nama modul kode di
`apps.py` beda dari label produk (lihat tabel §4.3).

```
Login ──► Beranda (Dashboard Umum, 9 widget lintas Cloud yang dilisensikan)
  🎯🧲 Talent Cloud    : Pipeline (tabel/papan), Klien + dokumen legalitas,
                        Job Orders (pipeline 13-tahap), Talent Pool (upload
                        CV → auto-profil + CV standar bertemplate, AI
                        Matching 0-100+explain), placement, jadwal interview
  💼 Workforce Cloud  : Karyawan, kontrak, dokumen legal, BPJS+asuransi,
                        Absensi, Portal Saya (ESS), TTE
  📊 Revenue Cloud    : Saltab proyek (grid), Approval klien (token),
                        Payment Request, Invoice + faktur DJP, Kas & Bank,
                        Pembelian, Aset Tetap
  🏛️ Govern Cloud     : Tutup Buku, Jurnal & Bagan Akun, Laporan (termasuk
                        per klien), Tanya-Laporan AI
  💬 Chat (gratis)    : Channel, DM, thread — tersambung entitas (job order,
                        payrol, proyek); karyawan outsourcing ter-scope
  ✨ AI Add-on        : Asisten @AEOS, RAG kontrak, forecast

Publik (tanpa login, per-tenant white-label):
  /careers/{tenant_slug}         : Listing lowongan publik (Job Portal, Fase 16)
  /careers/{tenant_slug}/{jo_id} : Detail + form lamaran (guest-apply)
  /careers/track                 : Cek status lamaran via token
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
- **Strategi model AI (v3.1)**: AEOS memakai model berbayar/frontier untuk
  performa terbaik, bukan wajib self-hosted gratis — biaya ditagih ke klien
  + margin (via SKU AI Add-on, §4.3), diukur nyata lewat `ai_usage_events`
  (Fase 17). Self-hosted (Ollama/vLLM) tetap opsi arsitektur terbuka untuk
  klien yang mensyaratkan data tidak keluar infrastruktur sendiri (`core/
  llm.py` sudah provider-agnostic, kompatibel skema OpenAI apa pun) — belum
  jadi prioritas eksekusi.
- **Job Order tanpa cascade guard (gap diketahui, belum diperbaiki)**:
  `DELETE /job-orders/{id}` mengembalikan 500 kalau JO masih punya
  `Placement`/`InterviewSchedule` terkait. Dicatat sebagai temuan, bukan
  disengaja — perlu guard/cascade eksplisit sebelum jadi masalah produksi.
- **AI Interview (Fase berikutnya) belum punya kode** — desain skema/endpoint
  sudah final (lihat penutup §5), tapi jangan diasumsikan tersedia sampai
  benar-benar diimplementasikan.
