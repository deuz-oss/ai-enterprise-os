# Product Requirements Document (PRD) v3.0 — Final

**Produk:** AI Enterprise OS — operating system untuk perusahaan outsourcing & workforce umum
**Pemilik Produk:** Brian — Head of Business & Operations
**Versi:** 3.0 · **Status:** Draft Final — Internal-First, Talent-Centric, Horizontal + Vertical
**Terakhir diperbarui:** 2026-08-30
**Menggantikan:** PRD v2.0 (bundle 6) + PRD v2.1 Revisi (patch 11)

> **Changelog v3.0**
> - **Final bundle Opsi F (better dari E):** 4 SKU metered — **Talent Cloud (Rp 15k/talent aktif + Rp 2k/match) + Workforce Cloud (Rp 10k/employee) + Revenue Cloud (Rp 5k/invoice + Rp 8k/faktur) + Govern** + Foundation gratis + AI add-on per token. *Matching native di Talent Cloud, bukan add-on.* Klarifikasi: **bukan jualan kandidat** — talent milik tenant, tagih per record + compute.
> - **Mode operasi per-tenant override** (`tenants.billing_mode inherit|internal|commercial`) — coexist internal & komersial 1 deployment.
> - **Horizontal + Vertical:** Core Workforce horizontal (semua industri), Pack Operate-Outsourcing vertikal (client billing, approval klien) — TAM tidak hanya outsourcing.
> - **Dashboard Umum 8+1 widget** cross-bundle + `GET /overview/personal` role-aware.
> - **Sales CRM:** pipeline + klien aktif **auto** `prospek → aktif` saat placement pertama (idempoten + audit).
> - **Recruitment:** JO stage + talentpool + 3 action (interview/offering/onboard) + **AI Matching 0-100 + explain** native.
> - **People & Ops:** karyawan, kontrak, **BPJS (no+status+kartu+valid_until)**, **Asuransi one-to-many** (`employee_insurances` — polis+kartu per provider, valid_until).
> - **Payroll:** saltab grid, BPJS dual-side, PPh21, bukti potong.
> - **Finance:** invoice, **faktur pajak e-Faktur DJP lengkap** (lawan NPWP/DPP/kode transaksi/no seri/NSFP/QR, flow batal/pengganti, TEXT payload).
> - **Accounting:** Accurate.id lokal (tetap §8 v1.4).
> - **Desktop vs Mobile:** Desktop = kerja berat (grid, matching, faktur), Mobile = hanya butuh HP (Portal, approval, **Chat tab baru** — tanpa Talent read-only).

---

## 1. Mode Operasi (menggantikan §1 v2.0)

| Level | Config | Efek |
|---|---|---|
| Global default | `APP_MODE=internal|commercial` di `.env` (`backend/app/core/config.py:15`) | Fallback |
| Per-tenant override | `tenants.billing_mode: "inherit"|"internal"|"commercial"` (`platform/models.py` baru, `PATCH /platform/tenants/{id}/billing-mode` platform_admin) | `internal` → bypass guard walau global commercial; `commercial` → enforce walau global internal |

Guard `backend/app/core/security.py:123` urutan: `tenant.billing_mode == internal → bypass` > `commercial → enforce` > `config.app_mode`. Tenant `default` seed `internal`. `LEGACY_KEY_MAP` jaga kompat.

## 2. Portofolio Final — 4 SKU Metered + Foundation (menggantikan §4 v1.4 & §2 v2.0)

### 2.1 Foundation — Gratis Selalu Aktif

| Kapabilitas | Route | Guard | Platform |
|---|---|---|---|
| Dashboard Umum | `GET /overview`, `GET /overview/personal` | `require_tenant_user` | Desktop 3 kolom, Mobile 1 kolom |
| Chat Workspace | `/chat`, `/chat/ws`, `GET /chat/digest` (gratis) | gratis | Desktop full, Mobile tab baru |
| Pages Notion-style | `/pages` | gratis | Desktop |

### 2.2 4 SKU Metered — Opsi F Final (6 keys teknis → 4 paket komersial)

| Paket F | Keys Teknis `apps.py` | Route | Isi | Meter + TTL | Dependensi |
|---|---|---|---|---|---|
| **Talent Cloud** | `sales_crm` + `recruitment` | `/leads`, `/clients`, `/recruitment`, `/talentpool`, `/ai/match` | JO stage + progress, talentpool facet + confidence, **AI Matching native 0-100 + explain + auto-sourcing**, schedule interview, offering (esign), onboard | **15k / talent aktif / bulan** (`talentpool tp_status=baru/diproses` + `candidates where status!=arsip`, `last_match_at >180 hari → nonaktif` shadow billing 2 bulan) + **2k / match execution** (`POST /recruitment/job-orders/{id}/match` per JO) | — |
| **Workforce Cloud** | `people_ops` | `/employees`, `/bpjs`, `/me`, `/notifications`, `/esign`, `/attendance` | Karyawan, kontrak, dokumen legal, **BPJS (no+status+kartu+valid_until)**, **Asuransi one-to-many** (`employee_insurances`: provider, policy_no, status, valid_until, card/policy key), absensi, project/placement, ESS portal, TTE | **10k / employee aktif / bulan** (`employees.status=aktif`, resign/nonaktif tidak hitung) | — |
| **Revenue Cloud** | `payroll` + `finance` | `/payroll`, `/finance` | **Payroll hitung** (saltab grid, prorata, BPJS dual-side, PPh21, bukti potong) + **tagih** (invoice, **faktur DJP lengkap** `lawan_npwp/nama/alamat, dpp, kode_transaksi, no_seri_faktur unique/tenant/tahun`, outstanding/overdue, penagihan, cashflow) | **5k / invoice + 8k / faktur DJP** + base 1jt (0 invoice tetap 1jt, min charge) | `workforce` |
| **Govern Cloud** | `accounting` | `/accounting` | Accurate.id lokal: CoA dinamis, jurnal memorial→posted, kas-bank, pembelian, aset, periode & tutup buku, laporan + AI | Flat 5-7jt / bulan | `revenue` |
| **AI Add-on** | `ai_addon` | `/ai` | `@AEOS` lintas app, RAG kontrak, forecast (matching sudah native di Talent) | 300 / 1k token | — |

**Klarifikasi Talent Cloud (anti-salah paham):** Talent = **record kandidat milik tenant** (mereka upload CV sendiri via `POST /talentpool/intake`). AEOS **tidak sediakan kandidat**. Tagih per record yang mereka simpan + per klik Match yang mereka jalankan — seperti Google Drive per file + per pencarian.

**Paket Komersial (contoh harga final oleh produk, metered):**

| Paket | SKU Included | Contoh Tagihan 80 talent aktif, 80 employee, 5 invoice, 5 faktur |
|---|---|---|
| **Starter** | Foundation + Workforce (Core) | 80×10k=800k |
| **Growth** | Starter + Talent | + 80×15k=1,2jt + 10 match×2k=20k = 2,02jt |
| **Scale** | Growth + Revenue | + 5×5k+5×8k+1jt=1,065jt = 3,09jt |
| **Enterprise** | Scale + Govern (7jt) | = 10,09jt |
| *Retail 80 emp tanpa outsourcing* | Workforce + Revenue + Govern (tanpa Talent) | 800k+1,065jt+7jt=8,87jt |

Trial 14 hari per SKU, base Rp 1jt untuk Revenue Cloud.

**Dependensi dilonggarkan:** `talent`, `workforce` `depends_on=()` (standalone) — HR bisa tanpa rekrutmen. `revenue` butuh `workforce`.

## 3. Sales CRM — Pipeline & Klien Aktif Otomatis

- Pipeline `leads` per stage funnel + `estimated_value` + win rate.
- Klien Aktif = `clients.status=aktif`. Trigger: `recruitment/service.py::create_placement` → jika placement pertama untuk `client_id` tersebut dan `client.status!=aktif` → `client.status=aktif, activated_at=now(), audit client.auto_activated`. Idempoten, tidak auto-revert saat cancel (manual di `Clients.tsx`).
- PKS versioning + reminder expiry ≤14 hari (widget People).

## 4. Recruitment — JO Stage + TalentPool + 3 Action + Matching Native

**Tampilkan:**
- JO stage: `open → screening → interview → offering → filled → closed` — progress bar `JobOrders.tsx`.
- TalentPool `TalentPool.tsx`: facet `q/domisili/skills/readiness/tp_status/has_standard_cv` + confidence, plus filter `min_match_score`.

**3 Action:**
1. **Schedule Interview** — `InterviewSchedule` baru: `candidate_id, job_order_id, interviewer_id, scheduled_at, location|meeting_url, status scheduled|done|no_show|cancelled, feedback, score 1-5`. API `POST /recruitment/interviews` → notif in-app + chat DM + email; `PATCH .../{id}`.
2. **Offering** — offering letter PDF branded → status `offered` → kirim via `esign` (`sandbox`/`privy`).
3. **Onboard** — `POST /employees/onboard` → placement + `Employee` + kontrak draft → pindah Workforce Cloud.

**AI Matching Native (baru, bukan add-on):**
```
POST /recruitment/job-orders/{jo_id}/match  {top_k=50}
  → engine: talent aktif × embedding cosine + rules (domisili, readiness, expected_salary) + LLM rerank via `vision_completion`
  → output: [{candidate_id, match_score 0-100, explain: "skill 90% + lokasi OK", missing: ["sertifikasi K3"]}]
  → cost: 1 credit (Rp 2k) per JO, bukan per candidate
GET /recruitment/job-orders/{jo_id}/matches?min_score=70
```
Sumber: `CvIntake.extracted` JSON terstruktur (bukan `cv_text` mentah) — tutup gap audit `ai/service.py:64`. History vendor `ilike` tetap.

## 5. People & Operations / Project Management — Setelah Onboard

**`Employees.tsx` menampilkan:**

| Data | Sumber | Field Baru v3.0 |
|---|---|---|
| Data karyawan | `employees` | — |
| Dokumen legal/kontrak | `employee_documents` + `employment_contracts` | expiry ≤14 hari alert |
| BPJS Kesehatan | `bpjs_kesehatan_no` | `+ bpjs_kesehatan_status (aktif/nonaktif/menunggu)` + `bpjs_kesehatan_card_key` + `bpjs_kesehatan_valid_until` |
| BPJS Ketenagakerjaan | `bpjs_ketenagakerjaan_no` | `+ status` + `card_key` + `valid_until` |
| Asuransi | **`employee_insurances` one-to-many** | `provider` (prudential/allianz/axa/manulife/bri_life/sinarmas/other), `policy_no`, `status`, `start_date`, `valid_until`, `card_object_key`, `policy_object_key`, `uploaded_by` |
| Absensi | `attendance_records` + `summaries` | hadir rate, lembur |
| Project | `placements` → `clients` → `job_orders` | matrix per klien, margin per kontrak `profit-by-client` |

**API v3.0:**
- `GET|POST /employees/{id}/insurances` + `GET|PATCH|DELETE .../insurances/{ins_id}` + `POST .../{ins_id}/card` (JPG/PNG/PDF ≤5MB) + `POST .../{ins_id}/policy` (PDF ≤10MB) + `GET .../card/download-url` + `GET .../policy/download-url` + audit
- `POST /employees/{id}/bpjs-card` (kesehatan|ketenagakerjaan, param `valid_until`) + `GET .../bpjs-card/download-url`
- `PUT /employees/{id}` tambah `bpjs_*_status/valid_until`

## 6. Payroll — Saltab, BPJS, PPh21, Generate Dokumen

- Saltab grid `PayslipComponent` (earnings/deduction/passthrough) + prorata `gaji×present/workdays` + THP, BPJS split `bpjs/engine.py`, PPh21 TER `rates/pph21`.
- Generate: slip PDF/Excel/CSV, rekap BPJS, **bukti potong PPh21 PDF** (`GET /payroll/runs/{id}/bukti-potong/{emp}/pdf`, `no_bukti 1.1-YYYYMM-SEQ`).
- Flow: proyek `DRAFT→SUBMITTED→APPROVED→FINANCE→FINALIZED`, internal `DRAFT→FINALIZED`, jurnal auto via `post_auto_event`.

## 7. Finance — Invoice, Faktur Pajak e-Faktur DJP Lengkap, Cashflow

**Invoice `invoices`:**
- Faktur kolom lengkap v3.0: `tax_invoice_no` (String50), `tax_invoice_status` (belum_buat/draft/menunggu_approval/terkirim_djp/approved/ditolak/dibatalkan/pengganti), `tax_invoice_date`, `lawan_npwp/nama/alamat`, `dpp_amount`, `ppn_amount`, `kode_transaksi` (01/04/09), `no_seri_faktur` (010.001-24.12345678 unique/tenant/tahun), `efaktur_nsr`, `efaktur_qr_url`, `efaktur_payload TEXT`, `faktur_pengganti_ref FK`, `faktur_status_detail`.

**Flow:**
```
Invoice.sent (validasi DPP/NPWP/kode/no_seri unik)
  → Generate Faktur Draft PDF (QR dummy)
  → POST /finance/invoices/{id}/tax-invoice/send → DJP `efaktur_api_url` idempoten via no_seri
    → 200 → approved + NSFP + QR + jurnal PPN Keluaran
    → 4xx → ditolak + faktur_status_detail, retryable
    → timeout → menunggu_approval, retry 3x
  → Batal: POST .../tax-invoice/cancel → DJP cancel
  → Pengganti: POST .../tax-invoice/replace {pengganti_ref}
  → simulasi jika efaktur_provider="" → PDF lokal tanpa hit DJP
```
Config `efaktur_provider/api_url/api_key/npkp, efaktur_retry_max=3`. Audit `finance.tax_invoice_*`.

**Finance.tsx:** list invoice + badge faktur, KPI revenue/outstanding/overdue + aging `GET /finance/invoices/aging`, penagihan prioritas `predict_client_payments`, cash in/out chart.

## 8. Dashboard Umum — 8+1 Widget Cross-Bundle + AI (menggantikan Dashboard v1)

**`GET /overview` + `GET /overview/personal` (`dashboard/router.py:19`) — 3 kolom desktop, 1 kolom mobile.**

| # | Widget | Sumber | SKU |
|---|---|---|---|
| 1 | Ringkasan Eksekutif Today | total klien, pipeline value, JO open/filled/overdue, headcount, payroll status, revenue MTD | Foundation |
| 2 | Sales & Pipeline | funnel, win rate, top 5 overdue | Talent |
| 3 | Recruitment & Talent | JO progress bar, talent funnel, interview minggu ini `InterviewSchedule` | Talent |
| 4 | People & Compliance | matrix per proyek, expiry 14d, BPJS/insurance completeness % | Workforce |
| 5 | Operations & Projects | placement aktif per klien + margin `profit-by-client` | Workforce |
| 6 | Payroll & Compliance | saltab bulan berjalan gross/THP/employer cost + BPJS/PPh21 | Workforce |
| 7 | Finance & Cashflow | invoice sent/paid/overdue + faktur_belum + revenue/outstanding + cash in/out | Revenue |
| 8 | Accounting Health | period closed, memorial unposted, neraca balance, laba rugi MTD | Govern |
| 9 | AI Insight | `GET /accounting/ai/executive-summary` + `GET /chat/digest` (PR menunggu, JO ≤7h, kontrak ≤14h) | AI add-on fallback deterministik |

Index: `employees(status)`, `invoices(due_date,status)`, `employment_contracts(end_date)`, `interview_schedules(scheduled_at)`. Cache 60s/tenant, `?period=YYYY-MM`. Role matrix §8 v2.1 tetap.

## 9. Desktop vs Mobile Scope (baru v3.0)

| Platform | Stack | Scope v3.0 |
|---|---|---|
| **Desktop** | React SPA (`frontend/src/pages/*` 22 pages) + `Dashboard.tsx` + `CommandPalette` | **Kerja berat:** grid Saltab, matching ranking, faktur DJP, laporan — semua bundle |
| **Mobile** | Flutter (`mobile/lib/screens/*`) + `home_shell.dart:34` | **Hanya butuh HP:** Portal ESS (profil, kontrak, slip, cuti, sisa cuti), **Chat tab baru** (`chat_tab.dart` polling `GET /chat/channels` + `GET /chat/channels/{id}/messages` + WS), Absensi approve, Approval klien — **tanpa Talent read-only** (sesuai instruksi). Upload kartu BPJS/asuransi via kamera, selfie GPS `self_attendance_screen.dart` |

Chat Mobile: `NavigationBar` 6 tab (Beranda, Absensi, Payrol, Kontrak, Portal, **Chat**) — role `all`. Talent tetap desktop-only.

## 10. Accounting — Accurate.id Lokal (detail dari v1.4 §8, diringkas)

- **CoA dinamis:** `Account` kode `1-1000`, `parent_code`, `group_type` 10 nilai, `is_cash_bank/is_control_ar_ap/is_active`, template default ±60 akun (PPN, Utang Gaji/PPh21/BPJS, Piutang, Uang Muka, aset+akum, prive, laba ditahan), CRUD per tenant, hapus diblokir jika termutasi.
- **Jurnal memorial→posted:** `JournalEntry` status, validasi `debit=kredit`, `client_dim_id (+project_dim_id)` dimensi per kontrak → L/R per klien, hanya via `post_auto_event` idempoten (unique `event_code+source_ref`).
- **Transaksi:** kas-bank (rekonsiliasi), pembelian (bill+PPN), aset tetap (garis lurus, penyusutan idempoten per bulan, disposisi gain/loss).
- **Periode & tutup buku:** `AccountingPeriod` open/closed, lock + jurnal ikhtisar L/R→Laba Ditahan (P0 follow-up), backdate ditolak, reopen audit.
- **Laporan:** ledger per akun, trial balance bulanan+YTD, L/R bulanan/YTD/per klien, neraca, arus kas tidak langsung, aging piutang, kartu utang, mutasi aset.
- **AI 7 fitur:** auto-kategori+OCR, rekonsiliasi cerdas, asisten tutup buku, NL→SQL terverifikasi, narasi eksekutif, prediksi pembayaran, anomali/kepatuhan — `backend/app/modules/accounting/ai_accounting.py`, `bank_statement.py`, `vision_completion`.

Dependensi `govern → revenue` (bukan `sales_crm`).

## 11. State Machines Eksplisit

- **Lead:** new→contacted→qualified→proposal→negotiation→won|lost
- **JobOrder:** open→screening→interview→offering→filled→closed
- **Candidate/Talent:** intake→review→finalized→offered→placed→nonaktif
- **Invoice:** draft→sent→paid|cancelled; **Faktur:** belum_buat→draft→menunggu_approval→terkirim_djp→approved|ditolak→dibatalkan|pengganti

## 12. Migrasi & Kompatibilitas

- `r3_0`: `tenants.billing_mode`, `interview_schedules`, `employee_insurances` + `employees.bpjs_*_valid_until`, `invoices` 7 kolom faktur (TEXT payload, no_seri unique), `clients.status/activated_at`, `leads.estimated_value`.
- `LEGACY_KEY_MAP` `apps.py:28` map `hr_payroll→workforce` etc + `sales_crm+recruitment→talent` + `payroll+finance→revenue` + `finance_accounting→govern` — idempoten.
- UI: `PlatformTenants.tsx` billing mode, `Apps.tsx` BUNDLE_REGISTRY 4 SKU, `Dashboard.tsx` 9 widget, `Employees.tsx` asuransi one-to-many, `Finance.tsx` faktur badge.

## 13. Metrik v3.0

- Auto prospek→aktif ≥95% (`audit client.auto_activated`).
- Interview→onboard median ≤14 hari (`InterviewSchedule→Employee.join_date`).
- Kelengkapan dokumen ≥90% (`employee_documents`).
- Faktur ≤1 hari setelah `Invoice.sent` (`tax_invoice_date - issued_date`).
- Matching: median talent→final <5 menit, akurasi field ≥90%, match click→hire conversion tracked.
- Dashboard p95 <1s (indexed + cache).

## 14. Alur Baru Ringkas

```
Login → Dashboard Umum (9 widget, role-aware)
  Foundation: Chat (desktop+mobile), Pages
  Talent Cloud: Pipeline → Klien (auto aktif) → JO (stage) → TalentPool (facet) → [Match 0-100] → [Interview] → [Offering] → [Onboard] → Workforce
  Workforce Cloud: Karyawan → Kontrak/Dokumen → BPJS (no+status+kartu+valid) → Asuransi (one-to-many polis+kartu) → Absensi → Project → TTE
  Revenue Cloud: Payroll (saltab→BPJS/PPh21→bukti potong) → Invoice → Faktur DJP (NSFP/QR) → Outstanding/Overdue → Penagihan → Cashflow → PR
  Govern Cloud: Accurate.id (CoA, jurnal, kas-bank, pembelian, aset, periode, laporan+AI)
```

---

*Dokumen ini menggantikan PRD v2.0 & v2.1. Kode `apps.py` & `config.py` sudah sync v2.0; patch v3.0 (4 SKU + metered + interview + insurance one-to-many + faktur lengkap + mobile chat) menyusul irisan implementasi.*
