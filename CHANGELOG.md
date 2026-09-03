# Changelog

Semua perubahan penting pada AI Enterprise OS dicatat di sini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/).

## [Unreleased]

### Added — Fase 22: Component Library Frontend (Button, Badge, Card, ProgressStep)

- 4 komponen dasar baru di `frontend/src/components/ui/`: `Button`,
  `Badge`, `Card`, `ProgressStep` (yang terakhir benar-benar baru, 3
  lainnya reuse token `.btn`/`.pill`/`.card` yang sudah ada di
  `index.css`, sekarang lewat API komponen bukan className manual).
- 2 varian baru `.btn-ghost`/`.btn-danger` ditambahkan ke `index.css`.
- Migrasi 3 halaman auth (`Login.tsx`, `ForgotPassword.tsx`,
  `ResetPassword.tsx`) dari hardcode Tailwind `slate-*` ke token
  `var(--...)` + komponen baru — memperbaiki bug tidak merespons dark
  mode yang ditemukan saat audit design-system 2026-09-03.
- Detail keputusan di `PRD.md` Fase 22.

### Added — Polish: Foto Kandidat pada CV Standar & Page Tree Notion

- **Foto kandidat (§10.3)**: unggah/hapus foto (`/talentpool/candidates/{id}/photo`,
  PNG/JPEG ≤5 MB); tampil di header CV standar hanya bila branding tenant
  mengaktifkan `show_photo`; kegagalan baca foto tidak menggagalkan render PDF.
- **Page tree ala Notion (Fase 7 polish)**: modul `pages` — halaman buatan user
  berhierarki (parent/child, ikon emoji, konten) dengan anti-siklus induk dan
  hapus kaskade; editor `/pages/:id` + grup "📄 Halaman" dinamis di sidebar;
  gratis untuk staf internal. Kolom `candidates.photo_object_key` + tabel
  `notion_pages` (migrasi `r8s9t0u1v2w3`).
- Tes: `test_pages.py` (+2), `test_talentpool.py::test_foto_kandidat_toggle_show_photo`.

### Added — Fase 12: AI Kolaborasi (gelombang 2 chat)

- **Asisten @AEOS**: mention `@AEOS` di channel/DM memicu jawaban dari data
  lintas aplikasi terverifikasi (pipeline, job order, kandidat, karyawan, PR,
  invoice, payrol, laba rugi) — LLM sebagai lapisan bahasa dengan fallback
  deterministik; saran routing ke tim yang tepat (Finance / HR-Ops / HR /
  Recruiter / Business Dev) bila pertanyaan di luar cakupan data.
- **Rangkuman thread**: `POST /chat/messages/{id}/summarize` merangkum diskusi
  menjadi poin keputusan/tugas; hasil diposting bot AEOS ke thread.
- **Digest harian** `GET /chat/digest`: item deterministik — PR menunggu
  approval, payrol menunggu persetujuan klien, SLA job order ≤7 hari, kontrak
  berakhir ≤14 hari, invoice overdue; karyawan mendapat versi portal sendiri.
- **Slash command server-side**: `/help`, `/pr status`, `/jo status [kw]`,
  `/cuti sisa`, `/cuti ajukan <jenis> <mulai> <selesai> [alasan]` — dijawab
  bot AEOS sebagai thread reply; perintah personal (`/cuti*`) hanya boleh di DM.
- **Pemisahan paket**: fitur AI ter-guard lisensi `ai_addon`; slash command &
  digest gratis mengikuti chat. Identitas AEOS = user bot per tenant tanpa
  password aktif (tidak bisa login).
- Frontend Chat: tombol 🧵 Rangkum, panel 📋 Digest, hint slash/@AEOS.
- Modul baru `ai/collab.py`; tes `test_fase12_ai_kolaborasi.py` (+6).

### Added — Mobile GPS+selfie Absensi & Logo Branding CV

- **Absensi mobile GPS+selfie (Fase 8 lanjutan)**: `POST /me/attendance/clock-in|clock-out`
  (multipart selfie + koordinat) — satu record per hari (duplikat → 409), selfie
  JPG/PNG ≤5 MB tersimpan sebagai bukti, koordinat divalidasi, notifikasi otomatis
  ke HR/Ops tiap clock. HR/Ops melihat flag selfie + geo di daftar harian dan dapat
  membuka bukti (`GET /attendance/records/{id}/selfie/{which}/download-url`,
  role-gated + audit). Portal `/me` memuat URL selfie milik sendiri. Kolom baru
  `attendance_records` (migrasi `q7r8s9t0u1v2`).
- **App mobile**: tab "Absensi Saya" di Portal karyawan (`self_attendance_screen.dart`)
  — izin lokasi (geolocator) → foto depan (image_picker) → unggah multipart;
  `ApiClient.postMultipart` baru; deps pubspec bertambah geolocator & image_picker
  (verifikasi build butuh Flutter SDK).
- **Logo branding CV (§10.3)**: unggah/hapus logo perusahaan
  (`POST|DELETE /talentpool/branding/logo`, PNG/JPEG ≤2 MB, admin/management);
  logo tampil di header PDF CV standar; preview via panel "🎨 Branding CV Standar"
  pada halaman Talent Pool.
- Tes: `test_mobile_absensi.py` (+4), `test_talentpool.py::test_logo_upload_render_dan_hapus`.

### Added — Fase 13: Talent Pool & CV Standardization

- **Pipeline intake CV** (`POST /talentpool/intake`, modul `talentpool` baru,
  migrasi `p6q7r8s9t0u1`): unggah PDF (teks/scan), DOCX, atau gambar → deteksi
  jenis dokumen → ekstraksi LLM ke **skema tetap berversi** (scan/gambar via satu
  panggilan vision). File asli tersimpan sebagai bukti sumber dan tidak pernah
  ditimpa; intake gagal tetap tercatat dan bisa diproses ulang (`/reprocess`).
- **Confidence per kelompok field + review wajib**: skor model dikoreksi
  deterministik (validasi email/telepon, kelengkapan data); kelompok di bawah
  ambang 0.7 wajib dicek recruiter sebelum finalisasi; koreksi inline tersimpan.
- **Dokumen CV standar berversi**: finalisasi merender PDF struktur konsisten
  (identitas → ringkasan → pengalaman → pendidikan → skill/sertifikasi/bahasa →
  data penempatan) dengan **branding per tenant** (warna aksen + footer,
  configurable); tiap finalize membuat versi baru; **placement baru otomatis
  mengunci versi terbaru** sebagai bukti submission ke klien (§10.3).
- **Facet talent pool**: `GET /talentpool?q=&domisili=&skill=&readiness=&tp_status=`
  sesuai skema seragam §10.2.
- **Kepatuhan UU PDP**: consent wajib saat unggah; hak hapus subjek
  (`POST /talentpool/candidates/{id}/forget`) menghapus profil/snapshot dan
  membersihkan PII kandidat dengan jejak audit.
- Frontend: halaman "🧬 Talent Pool" (nav Recruitment) — unggah+consent, filter
  facet, badge "perlu cek", panel review, unduh versi PDF.
- Deps baru: `python-docx`. Tes: `backend/tests/test_talentpool.py`.

### Added — Fase 10 sisa AI: OCR Faktur, Rekonsiliasi Bank Cerdas, Prediksi Pembayaran

- **OCR faktur + auto-kategori (§8.8 #1)**: `POST /accounting/ai/ocr-bill` — foto
  faktur/nota (PNG/JPEG/WebP) diekstraksi satu panggilan model vision
  (`vision_completion` di `app/core/llm.py`) menjadi draft pembelian + saran COA
  dari riwayat tenant. Hasil berupa draft — bill tetap dibuat lewat endpoint
  pembelian agar jurnal terkontrol.
- **Rekonsiliasi bank cerdas (§8.8 #2)**: impor CSV rekening koran
  (`GET /cashbank/statement/template`, `POST /cashbank/statement/import`) dengan
  laporan baris gagal & duplikat; matching fuzzy deterministik ke transaksi kas-bank
  belum terekonsiliasi — skor = nominal 60% (toleransi ≤0,5%) + jarak tanggal ≤14 hari
  25% + kemiripan token deskripsi 15%, ambang usulan 75%. Konfirmasi usulan
  (`POST .../{id}/match`) menandai transaksi terekonsiliasi dan membersihkan usulan
  basi; baris tanpa pasangan diberi alasan yang bisa dibaca. Model baru
  `BankStatementLine` (migrasi `o5p6q7r8s9t0`).
- **Prediksi pembayaran klien (§8.8 #6)**: `GET /accounting/ai/payment-prediction` —
  skor risiko telat bayar per klien dari histori invoice (rasio keterlambatan +
  rata-rata hari telat + paparan overdue) → prioritas collection = outstanding × risiko.
- **Frontend**: tab baru "🤖 AI & Rekonsiliasi" pada halaman Akunting berisi Scan
  Faktur, Rekonsiliasi Bank Cerdas, dan tabel Prediksi Pembayaran Klien.
- Tes: `backend/tests/test_fase10_ai_sisa.py`.

### Added — Fase 9 penutup: Rantai Approval PR Multi-level per Tenant

- **Konfigurasi rantai** (`pr_approval_steps`, migrasi `n4o5p6q7r8s9`): urutan tahap
  approval per tenant — tiap tahap menunjuk satu user spesifik atau satu peran staf.
  `GET|PUT /payment-requests/approval-chain` (PUT khusus admin/management).
- **Eksekusi bertahap**: PR berjalan tahap demi tahap; hanya approver tahap berjalan
  yang dapat memutus (403 bila bukan); setujui tahap non-akhir melanjutkan ke approver
  berikutnya (notifikasi otomatis); tolak di tahap mana pun menggugurkan seluruh PR.
- **Jejak keputusan per tahap** (`pr_approvals`): step, approver, keputusan + catatan,
  waktu — tercatat juga di audit log. Progres `Tahap X/Y` tampil di daftar PR.
- **Kompatibilitas legacy**: tanpa konfigurasi rantai → perilaku lama (management/
  admin mana pun memutus). Kartu aksi chat PR ikut tunduk pada validasi rantai.
- Frontend: panel "Rantai Approval" di halaman Payment Request (tambah/hapus/simpan
  tahap), badge progres tahap per baris PR.
- Tes: rantai 2 tahap (peran → user), 403 approver salah tahap, penolakan per tahap,
  validasi config (422), reset ke legacy.

### Added — Saltab Export Excel/PDF + Pencarian & Mention Chat

- **Ekspor Saltab**: `GET /payroll/runs/{id}/saltab/export-excel` (openpyxl) dan
  `/export-pdf` (reportlab landscape A4); CSV tetap tersedia.
- **Pencarian pesan chat** + **autocomplete mention** ter-scope (karyawan hanya bisa
  menyebut sesama scope proyeknya).

### Added — Fase 11: Chat Workspace (gratis, WebSocket real-time — v1 REST polling)

- **Model chat** (`chat_channels`, `chat_channel_members`, `chat_messages`, `chat_message_reactions`, migrasi `l3m4n5o6p7q8`): Channel tipe `public/private/dm/broadcast`, pesan thread (`parent_id`), soft delete, reaksi emoji, anggota channel.
- **Akses ter-scope (PRD §9.2) dipaksakan server-side**: staff melihat semua channel tenant; karyawan outsourcing hanya channel yang dia member — penegakan di semua endpoint.
- **Broadcast channel** (📢 read-only untuk karyawan; hanya admin/Ops/management bisa posting).
- **Thread reply + reaksi**: kirim pesan ke channel/ke thread via `parent_id`; filter thread; toggle reaksi emoji; edit/hapus pesan milik sendiri.
- **Unread**: `unread_count` per channel untuk karyawan; `POST /channels/{id}/read-all`.
- **Channel gratis** (tanpa guard lisensi); rilis v1 memakai polling — WebSocket pluggable menyusul.
- **Halaman Chat** (`/chat`, nav 💬 Chat): layout dua panel (channel list + pesan), thread view Balas↩, polling 2.5–4 detik, reaksi per pesan, edit/hapus pesan milik sendiri.
- **Sisa Fase 11 lanjutan**: channel otomatis per job order / payroll periode / proyek penempatan; kartu notifikasi interaktif (PR & payroll) dengan tombol aksi dari chat; WebSocket real-time native FastAPI (bertahan sebagai fallback polling).
- Tes: channel CRUD, scope karyawan (403 → 200 setelah diinvite), broadcast hanya Ops/admin, thread + reaksi, unread count.

### Added — Fase 10: AI Layer Akuntansi (§8.8)

- **Asisten tutup buku** `GET /accounting/ai/close-checklist?year=&month=` — checklist deterministik tanpa LLM: jurnal memorial belum diposting, invoice/payrol/PR tanpa jurnal otomatis.
- **Deteksi anomali** `GET /accounting/ai/anomalies?year=&month=` — duplikasi bill vendor (nama+nominal dalam 7 hari), transaksi >3× median, sanity PPN (ppn ≠ rate×amount).
- **Kategori bill cerdas** `POST /accounting/ai/categorize-bill` — saran COA berdasarkan keyword + riwayat vendor serupa.
- **Narasi eksekutif** `GET /accounting/ai/executive-summary?year=[&month=]` — angka terverifikasi → narasi Bahasa Indonesia via LLM (fallback template bila AI tidak dikonfigurasi).
- **Tanya laporan** `POST /accounting/ai/ask` — pertanyaan natural → pre-computed data terverifikasi (laba rugi, neraca, per klien) → jawaban dirangkai LLM.
- Semua fitur AI berbasis data terstruktur yang bisa diverifikasi, bukan teks bebas; LLM opsional — checklist & anomali sepenuhnya deterministik.

### Added — Fase 10 lanjutan: Kas & Bank, Pembelian, Aset Tetap, Arus Kas Tidak Langsung

- **Kas & Bank** (`BankTransaction`, migrasi `k2l3m4n5o6p7`): penerimaan/pembayaran/transfer antar rekening dengan jurnal otomatis; rekonsiliasi manual per transaksi.
- **Pembelian** (`PurchaseBill`): bill vendor → Dr Beban/Aset + PPN Masukan / Cr Utang Usaha; pembayaran → Dr Utang / Cr Bank.
- **Aset tetap** (`FixedAsset`): perolehan (Dr Aset / Cr sumber dana), penyusutan garis lurus bulanan idempoten (Dr Beban Penyusutan / Cr Akum Penyusutan), disposisi dengan gain/loss otomatis.
- **Arus kas metode tidak langsung**: `GET /accounting/reports/cash-flow-indirect?year=` dari perubahan saldo grup akun — CFO/CFI/CFF terpisah.
- `ensure_coa` kini sync-upsert: menambah akun/rule template baru ke tenant lama tanpa duplikasi.
- Frontend Akunting: tab Kas & Bank / Pembelian / Aset Tetap + laporan arus kas tidak langsung.

### Added — Fase 10 (core): Accounting ala Accurate

- **Bagan akun dinamis per tenant** (`accounts`, migrasi `j1k2l3m4n5o6`): kode, kelompok 10 jenis ala Accurate, saldo normal, flag `is_cash_bank`/`is_control_ar_ap`; template default outsourcing di-seed otomatis; CRUD dengan guard "akun termutasi tidak boleh dihapus".
- **Jurnal memorial → posted**: `POST /accounting/journal?status=memorial` lalu `POST /accounting/journal/{id}/post` dengan validasi seimbang, periode open, akun aktif. Baris jurnal kini punya `account_id` FK, dimensi klien (`client_dim_id`), dan memo.
- **Periode & tutup buku**: `GET /accounting/periods`, `POST /periods/{y}/{m}/close|reopen` — input backdate ke periode tertutup ditolak; buka ulang tercatat di audit.
- **Mesin auto-journal idempoten** `post_auto_event()`: event unik per dokumen sumber (unique event+ref); rule aktif per tenant (`journal_rules`). Hook aktif: `invoice_issued`, `invoice_paid`, `payroll_finalized_internal/proyek`, `pr_executed`.
- **Laporan berbasis akun DB + hanya posted**: neraca saldo, buku besar, laba rugi (tahun/bulan), neraca; **laba rugi per klien** dari dimensi baris jurnal.
- **Frontend Akunting**: tab Jurnal (form memorial/posted, filter event, tombol Posting), Bagan Akun (+tambah akun), Periode & Tutup Buku (tutup/buka ulang).
- Sisa Fase 10 (irisan lanjut): kas-bank & rekonsiliasi, pembelian, aset tetap + penyusutan otomatis, arus kas tidak langsung, AI akuntansi.

### Added — Fase 9b-c: Saltab Line-item, BPJS Dua Sisi & Payment Request

- **Line-item Saltab** (`PayslipComponent`, migrasi `i0j1k2l3m4n5`): setiap slip kini punya rincian komponen (gaji pokok, tunjangan, lembur, PPh21, potongan lain, admin bank) yang dibangun otomatis saat generate — komponen ↔ agregat slip selalu "nol selisih".
- **Prorata absensi (opt-in)**: `prorata_absensi=true` pada `POST /payroll/runs/{id}/generate` memprorata gaji pokok & tunjangan dari hari hadir rekap tervalidasi ÷ hari kerja Sen–Jum bulan tsb (jejak di notes komponen).
- **BPJS dua sisi (opt-in)**: `bpjs_enabled=true` menambah potongan karyawan (Kesehatan/JHT/JP) + passthrough tanggungan perusahaan dari mesin BPJS ber-versi.
- **Grid Saltab**: `GET /payroll/runs/{id}/saltab` + override manual per komponen `PATCH /payroll/saltab/components/{id}` (gross/net recompute + audit) + ekspor CSV.
- **Invoice draft otomatis** saat payrol proyek disetujui klien (Σ earnings + BPJS employer; fee diatur Finance; idempoten per periode+klien).
- **Workflow Payment Request**: `PaymentRequest` dengan state machine diajukan → menunggu_atasan → disetujui → dieksekusi / ditolak (+catatan wajib); endpoint `/payment-requests` (create dari run final, list+filter, approve/reject management, execute finance); notifikasi approver & pemohon; nomor PR/ tahun berurutan.
- **Frontend**: grid Saltab editable inline di halaman Payroll; halaman "🧾 Payment Request" dengan aksi per status; tombol "+ Payment Request" pada run final.
- Tes: komponen/prorata/BPJS dua sisi, override + recompute, invoice otomatis, PR lifecycle lengkap.

### Added — Fase 9a: Payrol Dua Jalur + Approval Klien Ber-Token (ADR-0006)

- **`PayrollRun.run_type`** (`internal|proyek`) + `client_id` wajib untuk run proyek; duplikat diperiksa per (periode, jenis, klien). Migrasi `h9i0j1k2l3m4`.
- **State machine** sesuai PRD: proyek `draft → submitted_to_client → client_approved/rejected → finance_processing → final` (ditolak → perbaiki → kirim ulang); internal `draft → finance_processing → final` (finalisasi langsung dari draft tetap didukung).
- **Approval klien ber-token tanpa akun**: `POST /payroll/runs/{id}/submit-to-client` menghasilkan link `/payroll/client/{token}` (token disimpan sebagai hash SHA-256, masa berlaku 1–90 hari, link baru mencabut yang lama). Endpoint publik read-only `GET /payroll/client/{token}` + keputusan `POST .../decision` (nama & catatan wajib; kedaluwarsa 410; sudah diputus 409). Semua tercatat di audit + notifikasi HR.
- **Guard ADR-0006 dieksekusi**: shell `/payroll` jadi OR (`hr_payroll` ATAU `operations_billing`, role operations/management/hr), mutasi divalidasi lisensi per `run_type` di service.
- **Generate slip proyek** hanya menarik karyawan yang ditempatkan di klien run tersebut.
- **Frontend Payroll**: pilih jenis payrol + klien saat buat run; badge status 6 state; aksi kontekstual per status (Kirim ke Klien / Mulai Proses Finance / Finalisasi) + callout link approval dengan tombol salin URL.
- Tes: lifecycle internal & proyek lengkap, tolak→perbaiki→kirim ulang, token kedaluwarsa/terpakai, guard lisensi per jenis.

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
