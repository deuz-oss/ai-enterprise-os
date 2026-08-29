# PRD v2.1 — Revisi Patch atas v2.0 (Internal-First Bundling)

**Merevisi:** `PRD-v2.0-Internal-First.md` (2026-08-30 Draft)
**Status:** Revisi — siap freeze setelah approval
**Penulis patch:** Audit traceability PRD v2.0 (2026-08-30)
**Ringkasan patch:** 6 isu P0 + 7 isu P1 ditutup tanpa ubah visi bundle. Perubahan bersifat aditif — tidak ada breaking rename bundle.

---

## Patch 1 — Mode Operasi: Global → Per-Tenant Override (P0)

**Masalah v2.0 §1:** `APP_MODE` global — internal & komersial tidak bisa coexistence 1 deployment.

**Revisi:**
| Level | Config | Efek |
|---|---|---|
| Global default | `APP_MODE=internal|commercial` di `.env` (`config.py:app_mode`) | Fallback jika tenant belum di-set |
| Per-tenant override | `tenants.billing_mode: "inherit"|"internal"|"commercial"` (kolom baru `tenants` + `GET|PATCH /platform/tenants/{id}/billing-mode` platform_admin) | `commercial` → enforce bundle walau global `internal`; `internal` → bypass walau global `commercial` |

Guard `security.py:require_licensed_app` cek urutan:
```
if tenant.billing_mode == "internal" → bypass
elif tenant.billing_mode == "commercial" → enforce
elif config.app_mode == "internal" → bypass
else → enforce
```
Tenant `default` seed `billing_mode="internal"` (internal-first). Tenant komersial baru `commercial`.

**Kode terdampak:** `backend/app/core/config.py`, `platform/models.py` (+migrasi), `platform/service.py` (`is_licensed` + `get_billing_mode`), `core/security.py`, `.env.example`.

---

## Patch 2 — Dependensi Bundle Dilonggarkan (P0)

**Masalah v2.0 §2.2:** `people_ops → recruitment → sales_crm` keras — perusahaan yang import karyawan manual tidak bisa beli People tanpa beli Sales/Recruitment.

**Revisi `backend/app/core/apps.py`:**
```python
# sebelum
people_ops depends_on=("recruitment",)
# sesudah
people_ops depends_on=()          # standalone — HR bisa tanpa recruitment
payroll    depends_on=("people_ops",)
finance    depends_on=("payroll",) # tetap, tapi guard finance tidak cek sales
accounting depends_on=("finance",)
recruitment depends_on=()         # standalone juga
sales_crm   depends_on=()
```
**Paket tetap valid** (Starter tetap `sales_crm`, Growth tetap `sales_crm+recruitment+people_ops`) — hanya `depends_on` teknis yang dilonggarkan agar **beli terpisah** tetap bisa. Auto-konversi `prospek→aktif` (§3) tetap butuh `sales_crm + recruitment` — jika `recruitment` tidak aktif, konversi manual via `Clients.tsx`.

**Matriks paket tetap:** Starter/Growth/Scale/Enterprise tidak berubah — hanya `BUNDLE_REGISTRY` di `apps.py` tetap sama.

---

## Patch 3 — Recruitment: Model InterviewSchedule & Offering (P0)

**Tambah ERD baru:**

```
InterviewSchedule (baru)
  id UUID PK
  tenant_id FK
  candidate_id FK candidates.id
  job_order_id FK job_orders.id
  interviewer_id FK users.id
  scheduled_at DateTime (wajib)
  location String(255) | meeting_url String(500)  ← salah satu wajib
  status Enum: scheduled | done | no_show | cancelled
  feedback Text | score Integer(1-5)
  created_by FK users.id, created_at
  Unique(tenant_id, candidate_id, job_order_id, scheduled_at)

Candidate.status enum tambah: offered
JobOrderStatus tetap: open→screening→interview→offering→filled/closed
```

**API baru:**
- `POST /recruitment/interviews` (recruiter/ops) → notif in-app + chat DM ke interviewer + email opsional (jika `smtp_host` set)
- `PATCH /recruitment/interviews/{id}` (done/no_show/cancel + feedback)
- `POST /recruitment/offers` → generate offering letter PDF (template branding tenant) → `status=offered` → kirim via `esign` (`sandbox` lokal / `privy` produksi) → notif kandidat

**Offering letter template:** HTML→PDF via `reportlab` (reuse `talentpool/render`) — branding `accent_color/footer/logo`.

---

## Patch 4 — People & Ops: Asuransi One-to-Many + BPJS Expiry (P0)

**Masalah:** `employees` single polis tidak cukup; kartu butuh expiry.

**Revisi model:**

```python
# employees — pertahankan 1 polis legacy untuk kompat, tapi tambah tabel baru
Employee (tambah kolom)
  bpjs_kesehatan_valid_until Date | null
  bpjs_ketenagakerjaan_valid_until Date | null
  # legacy single tetap untuk migrasi, tapi FE pakai tabel baru

EmployeeInsurance (baru, one-to-many)
  id UUID PK
  tenant_id FK
  employee_id FK employees.id (index)
  provider Enum InsuranceProvider (prudential/allianz/axa/manulife/bri_life/sinarmas/other)
  policy_no String(100) (unique per tenant)
  status Enum InsuranceStatus (aktif/nonaktif/menunggu)
  start_date Date | null
  valid_until Date | null   ← expiry, trigger alert ≤14 hari
  card_object_key String(500) | null   # upload kartu
  policy_object_key String(500) | null # upload polis PDF
  uploaded_at DateTime, uploaded_by FK users.id

HrDocumentType enum tambah: kartu_bpjs_kesehatan, kartu_bpjs_ketenagakerjaan (sudah di patch code)
```

**API baru:**
- `GET|POST /employees/{id}/insurances` + `GET|PATCH|DELETE /employees/{id}/insurances/{ins_id}`
- `POST /employees/{id}/insurances/{ins_id}/card` (JPG/PNG/PDF ≤5MB) + `POST .../policy` (PDF ≤10MB) + `GET .../card/download-url` + `GET .../policy/download-url`
- `POST /employees/{id}/bpjs-card` (kesehatan|ketenagakerjaan) — tambah `valid_until` param; `GET .../bpjs-card/download-url`
- Validasi MIME + audit `audit.log_event employee.insurance_uploaded / bpjs_card_uploaded` (sensitif)

**Dashboard widget §8-4** hitung `insurance_complete` dari `EmployeeInsurance where status=aktif` (bukan single kolom).

---

## Patch 5 — Finance: Faktur Pajak DJP Lengkap (P0)

**Masalah:** 6 kolom tidak cukup untuk validasi DJP.

**Revisi `invoices` — tambah/koreksi kolom:**

| Kolom | Tipe | Ket |
|---|---|---|
| `lawan_npwp` | String(20) | NPWP lawan transaksi (wajib DJP) |
| `lawan_nama` | String(255) | Nama lawan transaksi |
| `lawan_alamat` | String(500) | Alamat lawan |
| `dpp_amount` | Numeric(14,2) | Dasar Pengenaan Pajak |
| `ppn_amount` | Numeric(14,2) | Sudah ada `ppn_amount` — pakai ini |
| `kode_transaksi` | String(3) | DJP: 01 Normal, 04 DPP Nilai Lain, 09 PPN Dibebaskan — default 01 |
| `no_seri_faktur` | String(30) | Format DJP `010.001-24.12345678` — unique per tenant per tahun |
| `faktur_pengganti_ref` | UUID FK invoices.id | Jika faktur pengganti → ref faktur asal |
| `faktur_status_detail` | String(500) | Pesan error DJP detail |
| `efaktur_payload` | TEXT (bukan String2000) | JSON response DJP lengkap |
| `tax_invoice_no` | tetap String50 | Nomor faktur internal (bisa = no_seri) |
| `tax_invoice_status` | Enum tambah `dibatalkan` | already, tambah `pengganti` |

**Flow revisi:**
```
Invoice.sent (DPP & lawan lengkap?)
  → Generate Faktur Draft (PDF lokal, QR dummy)
  → Validasi DPP/PPN/kode_transaksi/no_seri unik
  → Kirim DJP (efaktur_api_url) — idempoten via no_seri+tenant
    → 200 → efaktur_nsr + qr_url, status approved, jurnal PPN Keluaran (accounting)
    → 4xx → status ditolak + faktur_status_detail, retryable
    → timeout → status menunggu_approval, job retry 3x
  → Faktur Batal: PUT /finance/invoices/{id}/tax-invoice/cancel → DJP cancel → status dibatalkan
  → Faktur Pengganti: POST .../tax-invoice/replace {pengganti_ref} → new invoice row link
  → jika efaktur_provider="" → mode simulasi (tanpa hit DJP, PDF lokal + qr dummy)
```

**API revisi:**
- `PUT /finance/invoices/{id}/tax-invoice` body: `lawan_npwp, lawan_nama, lawan_alamat, dpp_amount, kode_transaksi, no_seri_faktur, tax_invoice_date`
- `POST /finance/invoices/{id}/tax-invoice/send` (kirim DJP)
- `POST /finance/invoices/{id}/tax-invoice/cancel` + `POST .../replace`
- `GET /finance/invoices/{id}/tax-invoice/pdf` (PDF + QR)

**Config tetap** `efaktur_provider/api_url/api_key/npkp` — tambah `efaktur_retry_max=3`.

---

## Patch 6 — Sales Auto-Transisi Lengkap (P1)

**Revisi §3:**
- Trigger: `recruitment/service.py::create_placement` → jika `placements` pertama untuk `client_id` tersebut **dan** `client.status != aktif` → `client.status=aktif` + `client.activated_at=now` + `audit.log_event client.auto_activated {placement_id}`. Idempoten (cek `activated_at`).
- Revert: jika placement terakhir di-cancel (`DELETE /recruitment/placements/{id}`) dan tidak ada placement aktif lain untuk client → **tidak otomatis revert** — butuh manual di `Clients.tsx` (hindari flip-flop). Audit `client.deactivated_manual`.
- Reminder PKS expiry: `clients` PKS `end_date ≤14 hari` → widget People & Compliance + notif.

**Enum baru:** `ClientStatus: prospect | aktif | nonaktif` (kolom `clients.status` sudah ada — tambah constraint).

---

## Patch 7 — Payroll Bukti Potong PPh21 (P1)

**Tambah:**
- `payroll_runs` snapshot sudah ada `pph21` per run — tambah generator `GET /payroll/runs/{id}/bukti-potong/{employee_id}/pdf` (template PDF: `no_bukti = 1.1-YYYYMM-SEQ`, DPP, PPh21, NPWP).
- Nomor bukti potong sequence per tenant per tahun (`payroll_bukti_seq` table atau `func.count`).

---

## Patch 8 — Dashboard Spec Lengkap (P1)

**Revisi §8:**
- **Query & Index:** tambah index `employees(status)`, `invoices(due_date,status)`, `employment_contracts(end_date)`, `attendance_records(date)`, `payroll_runs(status,year,month)`. `GET /overview` cache 60s per tenant (Redis in-memory dict jika tanpa Redis) + `?period=YYYY-MM` param (default bulan berjalan).
- **Widget detail:**
  - 1 Ringkasan: pipeline value = `Σ leads.value` (kolom baru `leads.estimated_value` opsional, fallback count)
  - 2 Sales: funnel % + win rate = `won/total`, top 5 overdue `invoices where overdue`
  - 3 Recruitment: JO progress bar `filled/total`, talentpool funnel `CvIntake status`, interview minggu ini `InterviewSchedule where scheduled_at between Mon-Sun`
  - 4 People: matrix `placements group by client`, expiry 14d, BPJS/insurance completeness % = `active / total_employees`
  - 5 Operations: margin per kontrak `GET /accounting/reports/profit-by-client` (reuse)
  - 6 Payroll: saltab bulan berjalan `payroll_runs where year/month = now`, gross/THP/employer cost
  - 7 Finance: KPI + aging, cash in/out chart `cash_flow_entries where entry_date between`
  - 8 Accounting: period_closed count, memorial unposted, neraca balance `trial_balance` delta
  - 9 AI Insight: callout `executive-summary` + `digest` — fallback deterministik jika `ai_addon` tidak aktif
- **Role matrix:**

| Role | Widget 1 | 2 Sales | 3 Recruit | 4 People | 5 Ops | 6 Payroll | 7 Finance | 8 Acct | 9 AI |
|---|---|---|---|---|---|---|---|---|---|
| admin/management | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| hr/operations | ✅ ringkas | — | ✅ | ✅ | ✅ | ✅ | — | — | ✅ |
| finance | ✅ ringkas | — | — | — | — | ✅ | ✅ | ✅ | ✅ |
| karyawan (ESS) | ✅ personal | — | — | ✅ own | — | ✅ own slip | — | — | — |

Karyawan `GET /overview/personal` (baru) — hanya data `Employee.user_id` sendiri.

---

## Patch 9 — State Machines Eksplisit (P1)

**Kembalikan dari v1.4 yang hilang di v2.0:**

- **Lead:** `new → contacted → qualified → proposal → negotiation → won|lost`
- **JobOrder:** `open → screening → interview → offering → filled → closed` (reject → open)
- **Candidate/Talent:** `intake → review → finalized → offered → placed → nonaktif`
- **Invoice:** `draft → sent → paid | cancelled`; **Faktur:** `belum_buat → draft → menunggu_approval → terkirim_djp → approved | ditolak → dibatalkan | pengganti`
- Tiap transisi `audit.log_event` + notif.

---

## Patch 10 — Migrasi & UI (P1)

- **Alembic baru `r2_1_patch`:**
  - `tenants.billing_mode` (inherit internal commercial)
  - `interview_schedules` table
  - `employee_insurances` table + `employees.bpjs_*_valid_until`
  - `invoices` kolom `lawan_*`, `dpp_amount`, `kode_transaksi`, `no_seri_faktur`, `faktur_*`, `efaktur_payload TEXT`
  - `clients.status, activated_at`
  - `LEGACY_KEY_MAP` data migration: `TenantAppLicense` key lama → baru (hr_payroll→people_ops etc) — script idempoten
- **UI:**
  - `PlatformTenants.tsx`: field `Billing Mode` + `Bundle Licenses` (bukan app keys)
  - `Apps.tsx`: tampil `BUNDLE_REGISTRY` (Starter/Growth/Scale/Enterprise) + badge Trial
  - `Dashboard.tsx`: 3-kolom 9 widget + upsell card jika bundle tidak aktif
  - `Employees.tsx`: tab Asuransi (one-to-many) + BPJS kartu upload + expiry badge
  - `Finance.tsx`: kolom Faktur badge + tombol Generate/Kirim/Batal/Pengganti + PDF QR

---

## Patch 11 — Metrik Revisi (P1)

- Auto-konversi prospek→aktif diukur `clients where activated_at not null / total prospect won` ≥95% — query `audit`.
- Interview→onboard median diukur `InterviewSchedule.scheduled_at → Employee.join_date` ≤14 hari — `GET /recruitment/metrics`.
- Kelengkapan dokumen legal `employee_documents completeness` ≥90% — `GET /employees/completeness`.
- Faktur ≤1 hari diukur `invoices.issued_date → tax_invoice_date` — `GET /finance/metrics`.
- Dashboard p95 <1s — tambah `EXPLAIN ANALYZE` di CI.

---

## Keputusan Freeze

- Patch ini **tidak ubah bundle keys** — kode `apps.py` baru tetap valid; hanya `depends_on` people_ops yang longgar (1 line change).
- Setelah approve, update `PRD-v2.0-Internal-First.md` → `PRD-v2.1` (copy patch ke body) + buat Alembic `r2_1_patch` + implement `InterviewSchedule` & `EmployeeInsurance` & `Faktur DJP` stub.

*Setuju freeze? Balas "setuju" → aku langsung update PRD-v2.0 → v2.1 + patch `apps.py` depends_on + buat migrasi stub.*
