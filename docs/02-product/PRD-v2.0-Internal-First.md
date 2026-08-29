# Product Requirements Document (PRD) v2.0 — Internal-First Bundling

**Produk:** AI Enterprise OS — operating system untuk perusahaan outsourcing
**Pemilik Produk:** Brian
**Versi:** 2.0 · **Status:** Draft — Pivot Internal-First → Komersial per Bundle
**Terakhir diperbarui:** 2026-08-30
**Menggantikan:** PRD v1.4 (multi-app per-aplikasi ala Mekari)

> Changelog v2.0
> - **Pivot bisnis:** Internal dulu (semua fitur aktif tanpa lisensi), komersial nanti per bundle (bukan per app).
> - **6 Bundle komersial + Foundation gratis** menggantikan 7 app keys lama (`hr_payroll`, `operations_billing`, `finance_accounting` → `people_ops`, `payroll`, `finance`, `accounting`).
> - **Dashboard Umum** baru: 8 widget cross-bundle + AI insight (spec lengkap §5).
> - **Sales CRM:** pipeline + klien aktif, auto-pindah `prospek → aktif` saat onboarding sukses.
> - **Recruitment:** JO stage + talentpool + 3 action (schedule interview / offering / onboard).
> - **People & Ops:** karyawan, inventori dokumen legal/kontrak, BPJS (nomor+status+kartu), Asuransi (polis+status+kartu), absensi, project management.
> - **Payroll:** saltab, BPJS, PPh21, generate dokumen.
> - **Finance:** invoice, faktur pajak e-Faktur DJP integrasi, revenue/outstanding/overdue, penagihan, cash in, cash flow.
> - **Accounting:** Accurate.id lokal (tetap §8 PRD v1.4).

---

## 1. Mode Operasi

| Mode | Env | Guard Lisensi | Tenant |
|---|---|---|---|
| **Internal** | `APP_MODE=internal` (default sekarang) | BYPASS — semua bundle aktif | `default` tenant + tenant uji lain full package |
| **Commercial** | `APP_MODE=commercial` | Enforce per bundle (`require_licensed_app`) | Tenant baru pilih bundle Starter/Growth/Scale/Enterprise + addon AI |

Implementasi: `backend/app/core/config.py: app_mode` + `backend/app/core/apps.py: BUNDLE_REGISTRY` + `core/security.py: LEGACY_KEY_MAP`. Switch mode tanpa migrasi DB — hanya env.

## 2. Portofolio Bundle (menggantikan §4 PRD v1.4)

### 2.1 Foundation — Gratis Selalu Aktif (bukan lisensi)

| Kapabilitas | Route | Guard |
|---|---|---|
| Dashboard Umum | `/overview` | `require_tenant_user` saja |
| Chat Workspace | `/chat`, `/chat/ws` | gratis |
| Pages Notion-style | `/pages` | gratis |
| AI Assistant (basic digest/slash) | — | gratis; `@AEOS` advanced butuh addon |

### 2.2 6 Bundle Sellable

| Bundle | Key | Route Prefix | Isi | Dependensi |
|---|---|---|---|---|
| **Sales CRM** | `sales_crm` | `/leads`, `/clients` | Pipeline, aktivitas, konversi, dokumen legalitas. | — |
| **Recruitment** | `recruitment` | `/recruitment`, `/talentpool` | JO + stage, talentpool, interview/offering/onboard, AI screening. | sales_crm |
| **People & Operations** | `people_ops` | `/employees`, `/bpjs`, `/me`, `/notifications`, `/esign`, `/attendance` | Karyawan, kontrak, dokumen legal, BPJS+kartu, asuransi polis+kartu, absensi, project/placement, ESS portal, TTE. | recruitment |
| **Payroll** | `payroll` | `/payroll` | Saltab grid, prorata, BPJS, PPh21, generate slip/dokumen, approval klien ber-token. | people_ops |
| **Finance** | `finance` | `/finance` | Invoice, faktur pajak (e-Faktur DJP), revenue, outstanding/overdue, penagihan, cash in/out, cash flow, PR. | payroll |
| **Accounting** | `accounting` | `/accounting` | Accurate.id lokal: CoA, jurnal memorial→posted, kas-bank, pembelian, aset, periode & tutup buku, laporan + AI. | finance |
| **AI Add-on** | `ai_addon` | `/ai` | Screening, RAG, forecast, narasi — addon untuk semua bundle. | — |

### 2.3 Paket Komersial (pricing final oleh produk)

| Paket | Bundle Included | Segment |
|---|---|---|
| **Starter** | Foundation + Sales CRM | Perusahaan kecil, fokus sales |
| **Growth** | Starter + Recruitment + People & Ops | Outsourcing mid-size (HR + project) |
| **Scale** | Growth + Payroll + Finance | Perusahaan dengan payroll & penagihan sendiri |
| **Enterprise** | Scale + Accounting | Full Accurate.id lokal |
| **AI Add-on** | + ai_addon ke paket mana pun | Upsell |

Trial 14 hari per bundle (pertama kali), upgrade/downgrade via `PlatformTenants.tsx` + `Apps.tsx`.

## 3. Sales CRM — Pipeline & Klien Aktif Otomatis

**PRD v1.4 warisan:** pipeline spreadsheet → Leads. **v2.0 tambahan:**

- Pipeline menampilkan `leads` per stage (funnel) + value estimasi.
- Klien Aktif = `clients` dengan `status=aktif`. Saat calon klien sukses onboarding:
  ```
  Lead.won → Client(prospect) → JobOrder.filled → Placement → Employee.onboard
    → Client.status = aktif (trigger otomatis)
  ```
  Implementasi: hook di `recruitment/service.py::create_placement` → jika placement pertama untuk client tersebut → `client.status=aktif`. Manual override tetap bisa di `Clients.tsx`.
- Dokumen legalitas klien (PKS) versioning di `clients` — reminder expiry.

## 4. Recruitment — JO Stage + TalentPool + 3 Action

**Menampilkan:**
- Job Order beserta progres stage: `Open → Screening → Interview → Offering → Onboarded/Filled/Closed`. Progress bar per JO di `JobOrders.tsx`.
- Data TalentPool: `TalentPool.tsx` facet (domisili, skill, readiness, status), confidence score.

**3 Action (di `Candidates.tsx` / `JobOrders.tsx`):**
1. **Set Schedule Interview** — kalender: pilih kandidat + JO + tanggal/jam + interviewer → create `InterviewSchedule` (baru) → notifikasi in-app + chat DM + email opsional.
2. **Offering** — kirim offering letter (template + branding tenant) → butuh approval → generate PDF → kirim via e-sign sandbox/PrivyID → status `offered`.
3. **Onboard** — `POST /employees/onboard` (sudah ada) → placement + `Employee` + kontrak draft + inventori dokumen → pindah ke People & Ops.

## 5. People & Operations / Project Management — Setelah Onboard

**Setelah `Onboard`, kandidat pindah ke `Employees.tsx` menampilkan:**

| Data | Sumber | Field Baru PRD v2.0 |
|---|---|---|
| Data karyawan | `employees` | — |
| Inventori dokumen legal per karyawan | `employee_documents` + `employment_contracts` | kontrak expiry alert ≤14 hari |
| BPJS Kesehatan | `employees.bpjs_kesehatan_no` | `+ bpjs_kesehatan_status (aktif/nonaktif/menunggu)` + `bpjs_kesehatan_card_key` (upload kartu) |
| BPJS Ketenagakerjaan | `employees.bpjs_ketenagakerjaan_no` | `+ status` + `card_key` |
| Asuransi swasta | **baru** | `insurance_provider` (prudential/allianz/axa/manulife/bri_life/sinarmas/lainnya) + `insurance_policy_no` + `insurance_status` + `insurance_card_key` + `insurance_policy_key` (polis PDF) |
| Absensi | `attendance_records` + `attendance_summaries` | hadir rate, Lembur |
| Project Management | `placements` → `clients` → `job_orders` | matrix karyawan per proyek/klien, margin per kontrak (dari `accounting/profit-by-client`) |

**API baru (PRD v2.0):**
- `POST /employees/{id}/bpjs-card` (kesehatan/ketenagakerjaan) + `GET .../bpjs-card/download-url`
- `POST /employees/{id}/insurance-card` + `POST .../insurance-policy` + `GET .../insurance-*/download-url`
- `PUT /employees/{id}` tambah field `insurance_*`, `bpjs_*_status`

## 6. Payroll — Saltab, BPJS, PPh21, Generate Dokumen

**Menampilkan (di `Payroll.tsx`):**
- Perhitungan saltab: grid line-item (sudah ada `PayslipComponent`) + prorata + THP + employer cost.
- Perhitungan BPJS: split employer vs employee per `bpjs/engine.py` + `rates` versioned.
- PPh21: TER per `rates/pph21` versioned + snapshot di `payroll_runs`.
- Generate dokumen: slip PDF/Excel/CSV (sudah), rekap BPJS, bukti potong PPh21 (baru — template PDF).

Flow tetap: `DRAFT → SUBMITTED_TO_CLIENT → CLIENT_APPROVED → FINANCE_PROCESSING → FINALIZED` (proyek) dan `DRAFT → FINALIZED` (internal).

## 7. Finance — Invoice, Faktur Pajak, Revenue, Penagihan, Cash Flow

**PRD v1.4:** `finance` sudah punya invoice, cash_flow_entries. **v2.0 tambahan faktur pajak:**

### 7.1 Faktur Pajak e-Faktur DJP

| Field | Kolom `invoices` baru | API |
|---|---|---|
| No faktur pajak | `tax_invoice_no` String50 | `PUT /finance/invoices/{id}/tax-invoice` |
| Status faktur | `tax_invoice_status` enum `belum_buat/draft/menunggu_approval/terkirim_djp/approved/ditolak/dibatalkan` | — |
| Tgl faktur | `tax_invoice_date` | — |
| NSFP DJP | `efaktur_nsr` | — |
| QR URL | `efaktur_qr_url` | — |
| Payload DJP | `efaktur_payload` JSON | — |

**Flow:**
```
Invoice.sent → Generate Faktur Draft (lokal PDF) → Kirim ke DJP (efaktur_api_url)
  → DJP response (NSFP + QR) → status approved → sync ke accounting jurnal PPN Keluaran
  → Jika efaktur_provider="" → mode simulasi (draft PDF lokal tanpa hit DJP)
```

Config: `backend/app/core/config.py: efaktur_provider, efaktur_api_url, efaktur_api_key, efaktur_npkp`. Audit log `finance.tax_invoice_generated/sent/approved`.

**Menampilkan di `Finance.tsx`:**
- List invoice + status `draft/terkirim/dibayar/dibatalkan` + faktur status badge.
- Generate invoice (otomatis saat `CLIENT_APPROVED` sudah ada) + Generate faktur pajak (baru).
- KPI: Revenue (YTD/MTD), Outstanding, Overdue + aging `GET /finance/invoices/aging`.
- Penagihan: prioritas collection dari `accounting/ai/predict_client_payments` (late_ratio + avg_delay).
- Cash In (dari `invoice_paid` + `cash_receipt`) vs Cash Out → Cash Flow chart (dari `cash_flow_entries` + `cash_flow_indirect`).

## 8. Dashboard Umum — 8 Widget Cross-Bundle + AI

**Route `GET /overview` (expand dari `dashboard/router.py:19` yang sekarang hanya leads/clients/JO/candidates).**

### Layout 3 kolom (Notion-style) — `frontend/src/pages/Dashboard.tsx`

| # | Widget | Sumber Data | Bundle |
|---|---|---|---|
| 1 | **Ringkasan Eksekutif — Today** | total klien, pipeline value, JO open vs filled vs overdue SLA, headcount internal/eksternal, payroll run status, revenue MTD | Foundation |
| 2 | **Sales & Pipeline** | Funnel per stage + win rate + top 5 klien overdue | sales_crm |
| 3 | **Recruitment & Talent** | JO per stage progress bar + talentpool funnel + interview minggu ini | recruitment |
| 4 | **People & Compliance** | Karyawan per proyek matrix + dokumen expiry ≤14 hari + BPJS/asuransi completeness % | people_ops |
| 5 | **Operations & Projects** | Placement aktif per klien + margin per kontrak (`profit-by-client`) | people_ops |
| 6 | **Payroll & Compliance** | Saltab bulan berjalan (gross/THP/employer cost) + BPJS & PPh21 total | payroll |
| 7 | **Finance & Cash Flow** | Invoice sent/paid/overdue + revenue/outstanding + cash in/out chart | finance |
| 8 | **Accounting Health** | Periode open/closed + memorial unposted + neraca tidak balance alert + laba rugi MTD | accounting |
| 9 | **AI Insight** (callout block) | `GET /accounting/ai/executive-summary` narasi + `GET /chat/digest` tasks (PR menunggu, JO ≤7 hari, kontrak ≤14 hari) | ai_addon (fallback deterministik jika tanpa LLM) |

**Role-aware:** karyawan (ESS) hanya lihat widget 1 ringkas + 4 personal; HR/Ops lihat 4/5/6; Finance lihat 7/8; Admin lihat semua. Chat widget: unread badge + shortcut `⌘K`.

### 9. Accounting — Accurate.id Lokal (tetap PRD v1.4 §8)

Tidak berubah dari PRD v1.4 §8.1-8.8, hanya dependensi bundle: `accounting` depends_on `finance` (bukan `sales_crm`).

## 10. Migrasi & Kompatibilitas

- `LEGACY_KEY_MAP` di `apps.py` menjaga test/seed lama (`hr_payroll` → `people_ops` dll) tetap lulus.
- DB: `TenantAppLicense` key lama tetap valid, UI `Apps.tsx` tampilkan nama bundle baru.
- Alembic migration baru: kolom `employees` (6 kolom BPJS+asuransi) + `invoices` (6 kolom faktur) — auto `create_all` di dev, Alembic di production.

## 11. Halaman & Alur Baru (ringkas)

```
Login → Dashboard Umum (9 widget)
  🎯 Sales CRM        : Pipeline (funnel) → Klien (prospect→aktif otomatis)
  🧲 Recruitment      : JO (stage + progress) → TalentPool (facet) → [Interview][Offering][Onboard]
  👥 People & Ops     : Karyawan → Dokumen/Kontrak → BPJS (no+status+kartu) → Asuransi (polis+status+kartu) → Absensi → Project (per klien) → TTE
  💰 Payroll          : Saltab (grid) → BPJS & PPh21 → Generate slip/rekap/bukti potong → Approval klien (token)
  💳 Finance          : Invoice (list) → Faktur Pajak (e-Faktur DJP) → Revenue/Outstanding/Overdue → Penagihan → Cash In/Out/Cash Flow → PR
  📊 Accounting       : Accurate.id lokal (CoA, jurnal, kas-bank, pembelian, aset, periode, laporan+AI)
  💬 Chat + ✨ AI Assistant : channel/DM + @AEOS + digest (foundation, selalu aktif)
```

## 12. Metrik v2.0 (tambahan)

- Auto-konversi prospek→klien aktif ≥95% tanpa manual.
- Interview schedule → onboard median ≤14 hari.
- Kelengkapan dokumen legal per karyawan ≥90%.
- Faktur pajak terbit ≤1 hari setelah invoice `sent` (integrasi DJP).
- Dashboard load <1s (agregat query indexed).

---

*Dokumen ini menggantikan §4 dan menambah §5-8 PRD v1.4. Kode `apps.py` & `config.py` sudah diupdate; dashboard/insurance/faktur menyusul irisan implementasi.*
