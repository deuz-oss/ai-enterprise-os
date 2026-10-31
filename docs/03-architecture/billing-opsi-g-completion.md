# Rencana Penyelesaian Billing Opsi G (Fase 28 lanjutan)

> Status: **DISETUJUI (2026-10-31); backend F0–F6 diimplementasikan.**
> Semua keputusan terbuka K1–K19 memakai "usulan default" di §15. F7
> (frontend tenant `Billing.tsx`) selesai 2026-10-31; perluasan
> `PlatformTenants.tsx` belum. Revisi Alembic `4b32d019ebc2` (bukan
> `46ebfc27d235` seperti tertulis di bawah; head sudah maju). Penyimpangan
> kecil dari rencana: kolom tambahan `payment_intents.checkout_url` (invoice
> renewal pending dibuka ulang, bukan diterbitkan dobel); kode error memakai
> header `X-Error-Code`; pengecualian blokir AI berbasis prefiks `feature`
> `ai_interview*` (penolakan di titik pembuatan undangan belum dibuat);
> pengingat renewal hanya saat invoice terbit (bukan H-7/H-3/H-1).
> Rujukan produk: PRD §4.4 (Opsi G), §4.4.5, Fase 28 item 5–7, §15 backlog
> #1–#3. Ditulis 2026-10-30 berdasarkan kode di `main` (HEAD `2293edb`,
> head Alembic `46ebfc27d235`).

Cakupan:

- (a) Auto-reload sungguhan: token kartu/GoPay di Xendit, charge otomatis
  Rp100.000 saat saldo di bawah ambang, tanpa batas bulanan.
- (b) Kelola metode bayar tenant: tambah, hapus, set default.
- (c) Kwitansi resmi PDF untuk setiap pembayaran yang berhasil (kewajiban
  Aeos sebagai penjual SaaS, terpisah dari e-Faktur klien).
- (d) Langganan tahunan dengan diskon dari setting/env (besarannya belum
  diputuskan).
- (e) Aturan gagal bayar: renewal gagal membuat akses berhenti total;
  auto-reload gagal hanya memblokir fitur metered.

**Batasan keras (berlaku di semua bagian):** Aeos **tidak pernah** menerima,
menyimpan, mencatat di log, atau meneruskan PAN/nomor kartu atau CVV. Yang
disimpan hanya ID/token dari Xendit, ditambah metadata tampilan yang aman
(brand, 4 digit terakhir, bulan/tahun kedaluwarsa, nomor e-wallet tersamar)
**bila Xendit mengembalikannya**. Semua alur harus bisa dites dengan adapter
sandbox/fake tanpa kredensial asli.

---

## 1. Kondisi saat ini

### 1.1 Yang sudah ada

| Area | Lokasi | Catatan |
|---|---|---|
| Model langganan | `backend/app/modules/billing/models.py:41-66` (`TenantSubscription`) | `tier`, `monthly_fee`, `included_budget`, `cycle_start_day`, `auto_renew` (**tidak dipakai di mana pun**), `status` aktif/menunggak/dibatalkan. Status `past_due`/"menunggak" **tidak pernah diset** oleh kode mana pun. |
| Siklus jatah | `models.py:69-93` (`TenantBudgetCycle`) | Siklus bulanan, `remaining` dihitung dari kolom lain. |
| Saldo top-up + preferensi auto-reload | `models.py:96-114` (`TenantCreditAccount`) | Kolom `auto_reload_enabled/threshold/amount` sudah ada, tetapi hanya berupa preferensi. |
| Ledger | `models.py:117-146` (`CreditTransaction`, enum `topup_auto_reload` sudah ada, tetapi belum dipakai) | `amount` disimpan sebagai `Numeric(14,2)`, tetapi dipetakan ke `float` di Python. |
| Intent checkout | `models.py:149-190` (`PaymentIntent`, unique `provider_invoice_id`) | Tabel ini **sengaja tanpa RLS** (`alembic/versions/e1f2a3b4c5d6_fase28_payment_intents.py`) dan masuk `EXCLUDED_TABLES` di `tests/test_rls_coverage.py`. |
| Adapter gateway | `backend/app/core/payment/base.py` (kontrak `create_invoice`, `get_status`), `sandbox.py`, `xendit.py` (hanya `POST/GET /v2/invoices`, Basic auth, `httpx` tanpa SDK) | |
| Factory + verifikasi webhook | `billing/payment_service.py:35-56` | `X-Callback-Token` dibandingkan dengan `XENDIT_WEBHOOK_TOKEN` memakai `hmac.compare_digest`. |
| Checkout subscribe/top-up | `payment_service.py:58-89`, `router.py:69-94` | `external_id = aeos-{type}-{tenant_id}-{hex8}`. |
| Aktivasi langganan | `payment_service.py:92-144` | Ganti tier langsung tanpa prorata. Siklus pertama 30 hari. |
| Rekonsiliasi webhook | `payment_service.py:147-194`, `router.py:138-154` | Idempoten hanya lewat cek `status == paid` (lihat gap G7). |
| Debit metered | `billing/service.py:128-207` (`record_credit_transaction`), `:210-233` (`charge_metered_event` → 402) | Urutan potong: jatah siklus → saldo top-up. |
| Guard langganan | `core/security.py:190-222` (`require_active_subscription`) | Bypass untuk billing_mode internal (`:168-187`), plus safety-net `close_cycle_for_tenant` inline. |
| Tutup siklus | `billing/cycle_close.py:47-111`, cron `POST /platform/internal/run-cycle-charge` (`platform/router.py:177-187`) | **Membuka siklus baru dengan jatah penuh tanpa menagih biaya langganan** (lihat gap G1). |
| Panel platform | `platform/router.py:202-239` (billing-summary), `:246-272` (override tier) | |
| Audit | `modules/audit/service.py:25` `log_event(db, action, entity_type, entity_id, detail, actor, tenant_id)` | |
| PDF | `reportlab` sudah menjadi dependency (`backend/pyproject.toml`). Renderer generik ada di `modules/presales/rendering.py:16` (`render_document_pdf`), dan contoh tabel ada di `finance/service.py:982` (`tax_invoice_pdf`). | Tidak perlu dependency baru. |
| Storage | `core/storage.py` (`new_object_key`, `put_object`, `get_object`, `presigned_get_url`) | Dipakai lokal (`data/uploads`) maupun S3/MinIO. |
| Notifikasi | `modules/notifications/service.py:131` `notify(...)`, `:162` `notify_hr_users`, email via SMTP | |
| Uang | `core/money.py` (`to_decimal`, `round_rupiah`, `format_rupiah`) | |
| Frontend | `frontend/src/pages/Billing.tsx` | Tier di-hardcode (`:31-35`), callout "baru pengaturan" (`:281-286`), `DataTable` riwayat (`:290-299`). |
| Test | `backend/tests/test_billing.py` (11 test), `test_billing_payment.py` (7 test, pola patch `payment_provider="sandbox"` + token webhook) | |

Titik pemanggil metered real-time (fail-closed 402):

- `recruitment/service.py:1486` `recruitment.match_executed` Rp2.000
- `finance/service.py:187` `finance.invoice_issued` Rp5.000
- `finance/service.py:930` `invoice.tax_invoice_sent` Rp8.000

Titik pemanggil metered pasca-fakta (tidak pernah ditolak):

- `core/ai_usage.py:120-145`: debit `ai_usage` dengan `allow_negative=True`
  setelah panggilan LLM selesai. Dipanggil dari `core/llm.py`
  (`chat_completion`, `vision_completion`, `embed_texts`).
- `cycle_close.py:90-105`: snapshot talent/employee aktif.

### 1.2 Gap (termasuk temuan di luar daftar a–e)

| # | Gap | Dampak |
|---|---|---|
| G1 | **Renewal tidak pernah menagih.** `close_cycle_for_tenant` membuka siklus baru dengan `included_budget` penuh tanpa pembayaran apa pun. `auto_renew` tidak dibaca. | Aturan (e) "renewal gagal" saat ini **tidak punya titik pemicu**. Renewal yang menagih harus dibangun dulu. Tenant aktif sekarang mendapat jatah bulanan gratis setelah bulan pertama, jadi peluncuran renewal punya risiko bisnis (§13 F6). |
| G2 | Tidak ada model metode bayar, customer Xendit, atau tokenisasi. | (a), (b) |
| G3 | Auto-reload hanya preferensi (`service.py:95-125`). | (a) |
| G4 | Tidak ada kwitansi, nomor urut, atau identitas penjual/pembeli. `Tenant` (`platform/models.py:23-36`) tidak punya NPWP/alamat. | (c) |
| G5 | Tidak ada `billing_period`, `current_period_end`, atau diskon. | (d) |
| G6 | Tidak ada state "metered diblokir". Debit AI memakai `allow_negative=True`, sehingga AI **tidak pernah** diblokir meskipun saldo minus. | (e) |
| G7 | **Race di `reconcile_payment`:** dua webhook yang datang bersamaan sama-sama membaca `pending`, sehingga langganan bisa aktif dua kali atau top-up terkredit dua kali. Cek di `payment_service.py:161` tidak memakai lock atau compare-and-set. | Bug yang sudah ada. Diperbaiki di F0. |
| G8 | Webhook tidak menyimpan event (tanpa dedup per event id dan tanpa jejak payload). | Idempotensi dan forensik |
| G9 | `record_credit_transaction` selalu menulis kredit sebagai `topup_manual` (`service.py:187-189`). | Ledger auto-reload tidak bisa dibedakan. |
| G10 | URL checkout sandbox `/sandbox/billing/{id}/pay` (`core/payment/sandbox.py:27`) **tidak punya handler** di backend maupun route frontend. | Dev/demo sandbox buntu di checkout. |
| G11 | `_activate_subscription` hanya membatalkan baris `active`. Begitu `past_due` dipakai, baris menunggak lama tidak ikut dibatalkan. | Muncul begitu (e) diimplementasikan. |
| G12 | Router `billing` utama memakai guard `require_active_subscription`. Tenant yang aksesnya berhenti tidak bisa melihat kwitansi, mengelola metode bayar, atau membayar tunggakan. | (e) wajib memecah router. |
| G13 | Nilai uang memakai `float`. | Kwitansi wajib presisi. Kode baru memakai `Decimal` (`core/money.py`). |

---

## 2. Keputusan desain inti (ringkas)

1. **Renewal dikendalikan Aeos, bukan Xendit Recurring/Subscriptions API.**
   Renewal dijalankan oleh cron kita, yang men-charge metode bayar
   tersimpan lewat Payment Request API, atau menerbitkan invoice bila tenant
   tidak punya metode tersimpan. Alasan: siklus jatah, tutup siklus, dan
   override platform sudah berjalan di sisi kita. Dua sumber kebenaran
   jadwal (Xendit + DB) rawan divergen, dan PRD hanya menyebut Subscriptions
   API sebagai alasan memilih Xendit, bukan kewajiban. *(Keputusan terbuka
   K10 bila pemilik produk tetap ingin Xendit Recurring.)*
2. **Auto-reload memakai pola outbox + compare-and-set** di
   `TenantCreditAccount` sebagai kunci in-flight. Pola ini portabel untuk
   SQLite dan PostgreSQL karena tidak memakai partial unique index, selaras
   dengan alasan di docstring `TenantSubscription`.
3. **Diskon tahunan di env, bukan DB.** Ini konsisten dengan
   `TIER_MONTHLY_FEE_IDR` yang juga konstanta kode. Perubahan harga lewat
   deploy sehingga punya jejak git, dan v1 tidak perlu UI harga platform.
   Nilai diskon **di-snapshot** ke intent/langganan sehingga perubahan env
   tidak mengubah kontrak yang sudah dibayar.
4. **Tabel tenant baru tetap memakai RLS FORCE.** Webhook menurunkan tenant
   dari `reference_id` yang kita buat sendiri (`aeos-…-{tenant_id}-…`)
   setelah token callback terverifikasi, lalu `set_tenant()` sebelum lookup
   baris. Pengecualian RLS baru hanya untuk tabel platform-level tanpa
   `tenant_id`. `payment_intents` dibiarkan seperti sekarang.
5. **Kwitansi dibuat sekali** di transaksi yang sama dengan efek
   pembayaran: nomor dan snapshot data dikunci saat itu. PDF dirender
   deterministik dari snapshot saat pertama diminta, lalu disimpan
   (immutable).

---

## 3. Model data

Konvensi: UUID PK `default=uuid4`, `DateTime(timezone=True)`, enum
`native_enum=False`, uang `Numeric(14,2)` dengan `Mapped[Decimal]` untuk
model baru. Semua tabel bisnis tenant mewarisi `TenantMixin`.

### 3.1 Tabel baru

#### `tenant_billing_profiles` — `TenantBillingProfile(TenantMixin, Base)`

Identitas pembeli untuk kwitansi dan customer Xendit.

| Kolom | Tipe | Catatan |
|---|---|---|
| id | UUID PK | |
| legal_name | String(255) NOT NULL | Default dari `Tenant.name` saat dibuat |
| npwp | String(22) NULL | Format 15 atau 16 digit (NPWP 16 digit/NIK), validasi di schema |
| address | Text NULL | |
| billing_email | String(255) NULL | Tujuan email kwitansi/pengingat |
| provider_customer_id | String(120) NULL | ID customer Xendit (dibuat lazy) |
| created_at / updated_at | DateTime | |

Constraint: `UniqueConstraint("tenant_id", name="uq_billing_profile_tenant")`.

#### `tenant_payment_methods` — `TenantPaymentMethod(TenantMixin, Base)`

| Kolom | Tipe | Catatan |
|---|---|---|
| id | UUID PK | |
| provider | String(20) NOT NULL | `xendit` / `sandbox` |
| provider_payment_method_id | String(120) NOT NULL | ID payment method/token Xendit |
| reference_id | String(160) NOT NULL | `aeos-pm-{tenant_id}-{hex12}` |
| type | Enum `card` / `gopay` (String 20) | Bisa diperluas (mis. `ovo`, `dana`) bila Xendit mendukung tokenisasi |
| status | Enum `pending_activation` / `active` / `failed` / `expired` / `removed` | |
| card_brand | String(30) NULL | Hanya bila dikembalikan Xendit |
| card_last4 | String(4) NULL | |
| card_exp_month / card_exp_year | SmallInteger NULL | |
| ewallet_account_masked | String(40) NULL | Mis. `0812****789` (sudah tersamar dari Xendit, tidak disamarkan sendiri) |
| failure_reason | String(200) NULL | Kode error vendor, tanpa data kartu |
| created_by | UUID NULL | User pembuat |
| created_at, activated_at, removed_at | DateTime | |

Constraint:

- `UniqueConstraint("provider", "provider_payment_method_id", name="uq_payment_method_provider_id")`
- `UniqueConstraint("reference_id", name="uq_payment_method_reference")`
- `Index("ix_payment_method_tenant_status", "tenant_id", "status")`

**Tidak ada kolom PAN, CVV, BIN lengkap, atau nama pemegang kartu.** Test
regresi (lihat §11) memeriksa skema ini.

#### `payment_charges` — `PaymentCharge(TenantMixin, Base)`

Charge merchant-initiated memakai metode tersimpan, dipakai untuk
auto-reload **dan** renewal.

| Kolom | Tipe | Catatan |
|---|---|---|
| id | UUID PK | |
| purpose | Enum `auto_reload` / `renewal` | |
| payment_method_id | FK `tenant_payment_methods.id` | |
| subscription_id | FK `tenant_subscriptions.id` NULL | Untuk renewal |
| amount | Numeric(14,2) | |
| idempotency_key | String(160) NOT NULL | Dikirim sebagai header `idempotency-key` dan `reference_id` ke Xendit |
| provider_charge_id | String(120) NULL | Terisi setelah respons Xendit |
| status | Enum `pending` / `processing` / `requires_action` / `succeeded` / `failed` / `unknown` | `unknown` berarti timeout/5xx, wajib direkonsiliasi sebelum mencoba lagi |
| attempt_no | SmallInteger | Urutan percobaan dalam satu rangkaian retry |
| failure_code / failure_message | String NULL | |
| next_retry_at | DateTime NULL | |
| created_at, completed_at | DateTime | |

Constraint:

- `UniqueConstraint("idempotency_key", name="uq_payment_charge_idem")`
- `UniqueConstraint("provider_charge_id", name="uq_payment_charge_provider")` (NULL boleh banyak di kedua dialek)
- `Index("ix_payment_charge_tenant_status", "tenant_id", "status")`

Format `idempotency_key`:

- auto-reload: `aeos-ar-{tenant_id}-{charge_uuid}`. Satu charge UUID per
  pemicu; retry percobaan **berikutnya** membuat baris baru dengan
  `attempt_no+1`, sedangkan pengiriman ulang percobaan yang sama memakai
  key yang sama.
- renewal: `aeos-rn-{tenant_id}-{subscription_id}-{period_end:%Y%m%d}-{attempt_no}`

#### `billing_receipts` — `BillingReceipt(TenantMixin, Base)`

| Kolom | Tipe | Catatan |
|---|---|---|
| id | UUID PK | |
| receipt_number | String(40) NOT NULL | Mis. `AEOS/KW/2026/000123` |
| receipt_year | SmallInteger | |
| sequence_no | Integer | |
| source_type | Enum `payment_intent` / `payment_charge` | |
| payment_intent_id | FK NULL | |
| payment_charge_id | FK NULL | |
| issued_at | DateTime | Waktu pelunasan (paid_at dari gateway bila ada) |
| seller_snapshot_json | Text | Nama, NPWP, alamat, status PKP Aeos **saat terbit** |
| buyer_snapshot_json | Text | legal_name, NPWP, alamat, email tenant saat terbit |
| lines_json | Text | `[{description, qty, unit_price, amount}]` |
| subtotal / dpp / ppn_rate / ppn_amount / total | Numeric | `ppn_*` = 0 bila tidak berlaku (K5) |
| payment_method_label | String(80) | Mis. "Kartu VISA •••• 4242", "GoPay", "Invoice Xendit (VA BCA)" |
| provider_reference | String(120) | Invoice/charge id gateway |
| pdf_object_key | String(500) NULL | Terisi saat render pertama, lalu tidak pernah diubah |
| pdf_sha256 | String(64) NULL | Integritas |
| created_at | DateTime | |

Constraint:

- `UniqueConstraint("receipt_number", name="uq_receipt_number")`
- `UniqueConstraint("receipt_year", "sequence_no", name="uq_receipt_year_seq")`
- `UniqueConstraint("payment_intent_id", name="uq_receipt_intent")`
- `UniqueConstraint("payment_charge_id", name="uq_receipt_charge")` (satu pembayaran, satu kwitansi)
- `Index("ix_receipt_tenant_issued", "tenant_id", "issued_at")`

#### `billing_receipt_sequences` — **platform-level, tanpa TenantMixin**

| Kolom | Tipe |
|---|---|
| year | SmallInteger PK |
| last_number | Integer NOT NULL default 0 |

Alasan platform-level: penjualnya satu (Aeos). Penomoran kwitansi harus
berurutan **lintas semua pembeli**, jadi tidak boleh per tenant. Tabel ini
tidak berisi data bisnis tenant. Tanpa `tenant_id` berarti tidak tersentuh
filter ORM maupun RLS, dan **tidak perlu** masuk `EXCLUDED_TABLES` karena
test RLS hanya memeriksa tabel ber-`tenant_id`.

Alokasi nomor bersifat atomik di kedua dialek:

```sql
UPDATE billing_receipt_sequences SET last_number = last_number + 1
WHERE year = :y RETURNING last_number
```

PostgreSQL mendukung `RETURNING`, begitu pula SQLite ≥ 3.35. Bila baris
tahun belum ada, insert `(year, 0)` dengan menangkap `IntegrityError`, lalu
ulangi update. Pola `count()+1` seperti `finance/service.py:574`
(`_next_pr_number`) **tidak boleh dipakai** karena rawan race.

#### `payment_webhook_events` — **platform-level, tanpa TenantMixin**

| Kolom | Tipe | Catatan |
|---|---|---|
| id | UUID PK | |
| provider | String(20) | |
| dedup_key | String(200) NOT NULL | Header `webhook-id` bila ada, kalau tidak `{event_type}:{object_id}:{status}` |
| event_type | String(80) | `invoice.paid`, `payment.succeeded`, `payment_method.activated`, dan seterusnya (hasil normalisasi adapter) |
| object_id | String(120) | |
| tenant_id | UUID NULL (bukan FK TenantMixin) | Diisi setelah resolusi, hanya untuk forensik |
| payload_sha256 | String(64) | |
| payload_json | Text | Payload mentah. Aman karena Xendit tidak mengirim PAN; tetap disaring adapter (buang field `card_number`/`cvv` bila suatu saat muncul) |
| status | Enum `received` / `processed` / `ignored` / `failed` | |
| error | String(300) NULL | |
| received_at, processed_at | DateTime | |

Constraint: `UniqueConstraint("provider", "dedup_key", name="uq_webhook_event_dedup")`.

Alasan platform-level: event diterima **sebelum** tenant diketahui, dan
sebagian event mungkin tidak pernah terpetakan ke tenant (event dari
dashboard, tes Xendit). `tenant_id` nullable seperti `audit_logs`. Kalau
tabel ini diberi `TenantMixin`, ia wajib masuk `EXCLUDED_TABLES`. Lebih
jujur menjadikannya tabel sistem tanpa mixin. Akses hanya dari webhook dan
endpoint `/platform/*`.

### 3.2 Perubahan tabel yang ada

**`tenant_subscriptions`**

| Kolom baru | Tipe | Default/backfill |
|---|---|---|
| billing_period | Enum `monthly` / `annual` (String 20) NOT NULL | `monthly` |
| period_fee | Numeric(14,2) NOT NULL | Backfill = `monthly_fee`. Nominal yang benar-benar ditagih per periode tagih (tahunan = 12 × bulanan × (1 − diskon)) |
| discount_percent | Numeric(5,2) NOT NULL | `0` |
| current_period_end | Date NULL | Backfill = `period_end` siklus terbuka. NULL hanya untuk baris legacy/override (lihat §8) |
| past_due_since | DateTime NULL | |
| renewal_attempt_count | SmallInteger NOT NULL | `0` |
| next_renewal_attempt_at | DateTime NULL | |

`monthly_fee` dan `included_budget` tetap ada. Jatah siklus **tetap bulanan**
untuk paket tahunan: PRD menyebut jatah reset tiap bulan, sedangkan tahunan
hanya mengubah frekuensi tagih. Status baru: tidak ada. Pakai `past_due`
("menunggak") untuk renewal gagal (lihat §8).

**`tenant_credit_accounts`**

| Kolom baru | Tipe | Catatan |
|---|---|---|
| default_payment_method_id | FK `tenant_payment_methods.id` NULL | **Pointer tunggal** menggantikan flag `is_default` per baris, sehingga tidak butuh partial unique |
| auto_reload_in_flight_charge_id | UUID NULL | Kunci compare-and-set (lihat §6) |
| auto_reload_failure_count | SmallInteger NOT NULL default 0 | |
| auto_reload_next_attempt_at | DateTime NULL | |
| auto_reload_last_error | String(200) NULL | |
| metered_blocked_at | DateTime NULL | Non-NULL berarti fitur metered diblokir |
| metered_block_reason | String(40) NULL | `auto_reload_failed` / `no_payment_method` / `balance_exhausted` |

`auto_reload_amount` tetap default 100.000. Validasi baru: amount tetap
100.000, tidak bisa diubah tenant, bila K3 diputuskan begitu. Kolom
`monthly_reload_cap` dari PRD §4.4.4 **tidak dibuat** karena PRD §4.4.1
memutuskan tanpa cap.

**`payment_intents`**

| Kolom baru | Tipe | Catatan |
|---|---|---|
| billing_period | String(20) NULL | Untuk `type=subscription` / `renewal` |
| discount_percent | Numeric(5,2) NULL | Snapshot |
| subscription_id | FK NULL | Untuk `type=renewal` |

Enum `PaymentIntentType` ditambah `renewal`. Kolomnya `String(20)`
non-native, jadi tidak perlu DDL enum.

**`credit_transactions`**

- `receipt_id` FK `billing_receipts.id` NULL. Diisi di transaksi yang sama
  saat baris kredit dibuat, untuk link "Unduh kwitansi" di riwayat.

### 3.3 Enum ledger

`CreditTransactionType.topup_auto_reload` sudah ada. Tambahkan
`subscription_renewal` agar renewal terbedakan dari aktivasi awal
(opsional, karena `subscription_charge` bisa dipakai ulang dengan
`ref_event` berbeda; pilih salah satu saat implementasi).

---

## 4. Migrasi Alembic

- **Satu revisi**: `fase28_lanjutan_billing_opsi_g`. `down_revision` =
  head saat implementasi (per hari ini `46ebfc27d235`; cek ulang
  `alembic heads` sebelum menulis). Buat dengan
  `alembic revision --autogenerate -m "fase28 lanjutan billing opsi g"`,
  lalu edit manual untuk backfill dan RLS.
- Isi:
  1. `create_table`: `tenant_billing_profiles`, `tenant_payment_methods`,
     `payment_charges`, `billing_receipts`, `billing_receipt_sequences`,
     `payment_webhook_events` beserta semua unique/index di §3.1. Urutan
     pembuatan mengikuti FK.
  2. `add_column` di `tenant_subscriptions`, `tenant_credit_accounts`,
     `payment_intents`, `credit_transactions` lewat
     **`op.batch_alter_table`**. SQLite tidak mendukung `ALTER ADD COLUMN`
     dengan FK constraint. Polanya sudah dipakai di
     `0adce2836804_fase20_esign_requests_agreement_id.py`.
  3. Backfill (SQL portabel, tanpa fungsi spesifik dialek):
     `billing_period='monthly'`, `period_fee=monthly_fee`,
     `discount_percent=0`, `renewal_attempt_count=0`.
     `current_period_end` diisi dari `MAX(period_end)` siklus terbuka per
     subscription lewat subquery berkorelasi, yang jalan di kedua dialek.
     Kolom NOT NULL ditambahkan dengan `server_default`, lalu
     `server_default` dibiarkan atau di-drop sesuai hasil autogenerate agar
     `test_migrations.py` tidak drift. **Model harus mendeklarasikan
     `server_default` yang sama** bila dibiarkan.
  4. Khusus PostgreSQL (`_is_pg()` guard, pola
     `f2a3b4c5d6e7_extend_rls_coverage_2.py`): `ENABLE` + `FORCE ROW LEVEL
     SECURITY` dan policy `tenant_isolation` untuk
     `tenant_billing_profiles`, `tenant_payment_methods`,
     `payment_charges`, `billing_receipts`. **Tidak** untuk dua tabel
     platform-level.
  5. `downgrade()`: kebalikan lengkap (drop policy, kolom via batch, lalu
     tabel).
- `alembic/env.py`: tidak perlu import baru bila semua model tetap di
  `app/modules/billing/models.py`. Bila ditaruh di file baru (mis.
  `billing/receipts_models.py`), import wajib ditambahkan.
- `tests/test_migrations.py` harus hijau, dan `tests/test_rls_coverage.py`
  juga (bila dijalankan dengan Postgres).
- Catatan SQLite vs PostgreSQL:
  - `UPDATE … RETURNING` butuh SQLite ≥ 3.35. Python 3.12 di Windows/Linux
    membawa versi lebih baru, tetapi tambahkan assert versi di test.
  - `SELECT … FOR UPDATE` diabaikan SQLite. Karena itu semua kunci memakai
    **compare-and-set** (`UPDATE … WHERE kolom IS NULL`, cek `rowcount`)
    yang benar di kedua dialek.
  - Unique dengan NULL: banyak NULL diizinkan di kedua dialek, sehingga
    aman untuk `provider_charge_id`, `payment_intent_id`, dan
    `payment_charge_id`.

---

## 5. Adapter pembayaran

### 5.1 Kontrak baru (`core/payment/base.py`)

Dataclass baru (frozen):

- `CustomerResult(provider_customer_id)`
- `PaymentMethodResult(provider_payment_method_id, status, type,
  actions: list[Action], card_brand, card_last4, card_exp_month,
  card_exp_year, ewallet_account_masked, raw_safe)`, dengan
  `Action(kind: "redirect" | "otp" | "deeplink", url)`
- `ChargeResult(provider_charge_id, status, failure_code, actions, paid_at)`.
  Status hasil normalisasi: `succeeded` / `pending` / `requires_action` /
  `failed`.
- `WebhookEvent(dedup_key, event_type, object_id, reference_id, status,
  amount, paid_at, payment_channel_label, display: dict, raw_safe)`

Method baru di `PaymentAdapter`:

| Method | Fungsi |
|---|---|
| `ensure_customer(*, reference_id, email, name) -> CustomerResult` | Buat customer bila belum ada. `reference_id = aeos-cust-{tenant_id}` (idempoten di sisi Xendit karena reference_id unik) |
| `create_payment_method(*, customer_id, type, reference_id, card_token_id: str \| None, success_return_url, failure_return_url) -> PaymentMethodResult` | Kartu: menerima **token** dari Xendit.js, tidak pernah data kartu. GoPay: memulai account linking |
| `get_payment_method(provider_payment_method_id) -> PaymentMethodResult` | Rekonsiliasi |
| `expire_payment_method(provider_payment_method_id) -> None` | Hapus/nonaktifkan di Xendit |
| `charge_saved_method(*, provider_payment_method_id, customer_id, amount: Decimal, reference_id, idempotency_key, description) -> ChargeResult` | MIT (merchant-initiated) |
| `get_charge_by_reference(reference_id) -> ChargeResult \| None` | Untuk status `unknown` setelah timeout |
| `parse_webhook(headers, payload) -> WebhookEvent` | Normalisasi semua jenis callback (invoice lama + payment + payment_method) |

`create_invoice` dan `get_status` tetap seperti sekarang.

### 5.2 `XenditAdapter`: asumsi API yang WAJIB diverifikasi

Asumsi berikut berdasarkan dokumentasi publik Xendit dan **belum
diverifikasi terhadap akun Aeos**. Implementer wajib mengecek dokumentasi
terbaru dan menjalankannya di mode test Xendit sebelum menulis kode:

1. **Customer**: `POST /customers` (header `API-VERSION` mungkin perlu)
   dengan `reference_id`, `type=BUSINESS`, `business_detail`, `email`.
   Payment method e-wallet linked butuh `customer_id`.
2. **Payment Methods API v2**: `POST /v2/payment_methods` dengan
   `type=CARD` + `reusability=MULTIPLE_USE` + `card.token_id`?, atau
   `type=EWALLET` + `ewallet.channel_code=GOPAY` +
   `channel_properties.success_return_url/failure_return_url`.
   - Status respons `REQUIRES_ACTION` beserta `actions[]` (URL linking
     GoPay / URL 3DS kartu), `ACTIVE`, `EXPIRED`, `FAILED`.
   - Expire: `POST /v2/payment_methods/{id}/expire`.
   - **Perlu dicek**: apakah Xendit kini mengarahkan merchant baru ke
     **Payments API v3 / Payment Tokens** (`/v3/payment_tokens`,
     `/v3/payment_requests`) dan menandai v2 legacy. Bila ya, adapter
     memakai v3. Kontrak §5.1 sengaja netral sehingga modul billing tidak
     berubah.
3. **Tokenisasi kartu di browser**: Xendit.js / Cards Session / komponen
   hosted dengan **public key** (`XENDIT_PUBLIC_KEY`). PAN dan CVV dikirim
   browser langsung ke Xendit; backend hanya menerima `token_id`. Hal ini
   menjaga Aeos di cakupan PCI DSS SAQ A. **Perlu dicek**: flow mana yang
   aktif di akun (Cards Session vs `Xendit.card.createToken`), dan apakah
   verifikasi 3DS terjadi saat pembuatan token (`should_authenticate`) atau
   saat pembuatan payment method.
4. **Charge MIT**: `POST /payment_requests` dengan `payment_method_id`,
   `amount`, `currency=IDR`, `reference_id`, header `idempotency-key`.
   Status `SUCCEEDED` / `PENDING` / `REQUIRES_ACTION` / `FAILED`.
   **Perlu dicek**:
   (i) apakah charge kartu tersimpan bisa dijalankan sebagai MIT tanpa 3DS
   ulang (flag seperti `initiator=MERCHANT` / `card.cvn` tidak wajib);
   (ii) apakah GoPay linked account mengizinkan debit tanpa interaksi
   pengguna untuk nominal Rp100rb–Rp5jt+ (batas limit GoPay tokenized);
   (iii) `GET /payment_requests?reference_id=` untuk rekonsiliasi.
5. **Webhook**: event `payment.succeeded`, `payment.failed`,
   `payment_method.activated`, `payment_method.expired`, ditambah callback
   invoice lama (tanpa field `event`). Semuanya diverifikasi dengan header
   `X-Callback-Token` yang sama. **Perlu dicek**: apakah ada header
   `webhook-id` untuk dedup, dan apakah URL callback per produk diatur
   terpisah di dashboard.
6. **Annual**: invoice biasa (`/v2/invoices`) cukup untuk pembayaran awal
   tahunan; tidak butuh API khusus.

Semua kegagalan jaringan tetap dipetakan ke 502 seperti sekarang. **Pengecualian
untuk charge**: timeout/5xx **tidak** di-raise sebagai 502 ke pemanggil
cron, tetapi dikembalikan sebagai status internal `unknown` supaya bisa
direkonsiliasi. Timeout charge dipersingkat (mis. 20 detik, connect 5
detik) karena bisa dipanggil sinkron dari jalur reaktif (§6.2).

Logging: jangan pernah log payload mentah request pembuatan payment method.
Log hanya ID dan status. Field `raw_safe` dibangun dengan allowlist field,
bukan blocklist.

### 5.3 `SandboxPaymentAdapter` / fake untuk test

Diperluas, tetap tanpa jaringan dan deterministik lewat "token ajaib"
seperti pola sandbox esign:

| Input | Perilaku |
|---|---|
| `card_token_id="sbx-tok-ok"` | Payment method `active` langsung, brand `VISA`, last4 `4242`, exp 12/2030 |
| `card_token_id="sbx-tok-3ds"` | `requires_action` + action redirect `/billing/sandbox/payment-methods/{id}/authorize` |
| `card_token_id="sbx-tok-fail"` | `failed` |
| `type=gopay` | `pending_activation` + action redirect ke halaman sandbox linking |
| Charge dengan PM yang dibuat dari `sbx-tok-decline` | `failed` (`failure_code="CARD_DECLINED"`) |
| Charge dengan PM dari `sbx-tok-pending` | `pending`, selesai lewat endpoint simulasi webhook |
| Charge dengan PM dari `sbx-tok-timeout` | Melempar `TimeoutError` tiruan, sehingga status `unknown` |
| Pengiriman ulang dengan `idempotency_key` yang sama | Mengembalikan hasil yang sama, tanpa charge ganda (dict modul-level per proses) |

Endpoint simulasi (router terpisah, hanya terdaftar/aktif bila
`PAYMENT_PROVIDER=sandbox` **dan** `APP_ENV != production`; selain itu 404):

- `POST /billing/sandbox/invoices/{provider_invoice_id}/pay`: memperbaiki
  G10. Mensimulasikan webhook invoice paid melalui jalur `handle_webhook`
  yang sama (bukan shortcut ke service).
- `POST /billing/sandbox/payment-methods/{id}/activate` dan `…/fail`
- `POST /billing/sandbox/charges/{id}/succeed` dan `…/fail`

Frontend membutuhkan route `/sandbox/billing/:invoiceId/pay`, berupa
halaman tombol "Bayar (simulasi)" yang memanggil endpoint di atas.

Untuk unit test, adapter bisa juga di-monkeypatch langsung
(`patch("app.modules.billing.payment_service.get_adapter", return_value=FakeAdapter(...))`)
agar skenario kegagalan spesifik tidak bergantung pada token ajaib.

---

## 6. Alur auto-reload (a)

### 6.1 Pemicu

Pemeriksaan dijalankan di `record_credit_transaction` setelah debit
diterapkan (semua jalur: real-time, AI pasca-fakta, cycle-close), melalui
fungsi baru `maybe_enqueue_auto_reload(db, account, cycle)`. Kondisi:

```
account.auto_reload_enabled
AND default_payment_method aktif
AND (cycle_remaining + balance) < auto_reload_threshold   # K2: basis ambang
AND account.auto_reload_in_flight_charge_id IS NULL
AND (auto_reload_next_attempt_at IS NULL OR <= now)       # backoff
AND tenant bukan billing bypass
```

Bila terpenuhi, buat baris `payment_charges(purpose=auto_reload,
status=pending)`, lalu lakukan compare-and-set:

```sql
UPDATE tenant_credit_accounts
SET auto_reload_in_flight_charge_id = :charge_id
WHERE id = :acc AND auto_reload_in_flight_charge_id IS NULL
```

Bila `rowcount == 0`, request lain sudah memegang kunci: hapus baris
pending (atau jangan flush) dan berhenti. Semua ini terjadi di transaksi
yang sama dengan debit (outbox): debit yang di-rollback ikut membatalkan
pemicu.

Bila threshold NULL atau auto-reload mati: tidak ada pemicu, tetapi bila
saldo habis tetap diterapkan blokir metered (§8.3).

### 6.2 Eksekusi

Ada dua jalur. Keduanya memanggil satu fungsi
`execute_auto_reload_charge(db, charge_id)`.

1. **Proaktif (asinkron)**: cron `POST /platform/internal/run-auto-reload`
   memproses semua `payment_charges` berstatus `pending`, atau `unknown`
   yang perlu direkonsiliasi, dan `next_retry_at <= now`. Interval
   disarankan 1–5 menit (K11). Polanya sama dengan `run-cycle-charge`:
   iterasi `tenants`, lalu `set_tenant()` per tenant sebelum menyentuh
   tabel ber-RLS.
2. **Reaktif (sinkron, terbatas)**: di `charge_metered_event`, ketika
   `InsufficientCreditError` terjadi dan auto-reload memenuhi syarat,
   jalankan **satu** percobaan sinkron (timeout pendek). Bila hasilnya
   `succeeded` di respons langsung, kredit saldo dan ulangi debit sekali.
   Bila `pending`/`requires_action`/`unknown`, kembalikan 402 dengan
   `detail` "Auto-reload sedang diproses, coba lagi sebentar". Bila
   `failed`, masuk §6.4. Jalur ini memenuhi urutan PRD §4.4.4
   (siklus → saldo → auto-reload → blokir) tanpa menunggu cron.
   **Debit AI pasca-fakta tidak memakai jalur reaktif** karena
   `ai_usage.py` berjalan di sesi terpisah setelah respons; jalur ini hanya
   enqueue.

Langkah `execute_auto_reload_charge`:

1. Atomik: `UPDATE payment_charges SET status='processing' WHERE id=:id AND status IN ('pending','unknown')`.
   Bila rowcount 0, eksekutor lain sudah memprosesnya; berhenti. Commit
   **sebelum** panggilan HTTP supaya tidak ada transaksi DB terbuka selama
   memanggil Xendit.
2. Bila status sebelumnya `unknown`, panggil `get_charge_by_reference`
   dulu. Hanya bila Xendit menyatakan tidak ada charge, kirim ulang
   **dengan idempotency_key yang sama**.
3. Panggil `charge_saved_method(...)`.
4. Petakan hasil di transaksi baru:
   - `succeeded`: `apply_auto_reload_success` (§6.3).
   - `pending` / `requires_action`: status disimpan, menunggu webhook.
     `requires_action` pada MIT berarti PM perlu autentikasi ulang;
     perlakukan sebagai gagal untuk keperluan blokir (K12), lalu kirim
     notifikasi "verifikasi ulang metode bayar".
   - `failed`: §6.4.
   - exception timeout/5xx: status `unknown`, `next_retry_at = now + 2
     menit`. Kunci in-flight **tetap dipegang**.

### 6.3 Sukses

Di satu transaksi, dipicu dari respons sinkron atau webhook
`payment.succeeded`; keduanya idempoten lewat compare-and-set status:

1. `UPDATE payment_charges SET status='succeeded', completed_at=now WHERE id=:id AND status <> 'succeeded'`.
   Bila rowcount 0, sudah diterapkan; selesai.
2. Kredit saldo lewat `record_credit_transaction(..., tx_type=topup_auto_reload, ref_entity_type="payment_charge")`
   (perbaikan G9: parameter `tx_type` baru, default tetap `topup_manual`).
3. Terbitkan kwitansi (§9) dan isi `credit_transactions.receipt_id`.
4. Reset akun: `auto_reload_in_flight_charge_id=NULL`,
   `failure_count=0`, `next_attempt_at=NULL`, `last_error=NULL`, **dan**
   `metered_blocked_at=NULL` / `metered_block_reason=NULL` (pemulihan).
5. Audit `billing.auto_reload_succeeded`.
6. Bila setelah kredit saldo masih di bawah threshold (pemakaian sangat
   deras), pemicu berikutnya diperiksa ulang. Tanpa cap bulanan sesuai
   PRD; kunci in-flight memastikan paling banyak satu charge berjalan per
   tenant.

### 6.4 Gagal, retry, dan backoff

- Status `failed` ditulis bersama `failure_code`, lalu
  `auto_reload_failure_count += 1` dan kunci in-flight dilepas.
- Backoff (usulan, K6): percobaan ke-2 setelah 15 menit, ke-3 setelah 1
  jam, ke-4 setelah 6 jam, lalu berhenti otomatis (tetap bisa dipicu
  manual lewat "Coba lagi" atau dengan mengganti metode bayar). Kode gagal
  permanen (`CARD_DECLINED`/`EXPIRED_CARD`/`INSUFFICIENT_BALANCE` GoPay?;
  daftar diverifikasi ke Xendit) tidak di-retry otomatis.
- **Blokir metered segera** pada kegagalan pertama, bila total sisa ≤ 0:
  `metered_blocked_at=now`, `reason=auto_reload_failed`. Bila saldo masih
  positif (pemicu ambang), belum ada blokir; blokir baru terjadi saat saldo
  benar-benar habis.
- Notifikasi in-app + email ke user `BILLING_MANAGE_ROLES` dan admin
  tenant.
- Audit `billing.auto_reload_failed` (`detail`: failure_code, attempt_no;
  **tanpa** data kartu).

### 6.5 Pemulihan

Blokir metered dicabut (`metered_blocked_at=NULL`) oleh salah satu dari:
auto-reload sukses, top-up manual via invoice sukses (`reconcile_payment`
tipe topup), atau override platform. Pencabutan berlaku seketika karena
gate membaca kolom ini per request.

---

## 7. Idempotensi webhook

Alur `POST /billing/webhook/xendit` baru:

1. Verifikasi `X-Callback-Token` (yang sudah ada). Gagal berarti 401,
   tanpa menyentuh DB.
2. `adapter.parse_webhook(headers, payload)` menghasilkan `WebhookEvent`.
3. Insert `payment_webhook_events(provider, dedup_key, …, status=received)`.
   Bila terjadi `IntegrityError` pada `uq_webhook_event_dedup`, event
   duplikat: kembalikan `200 {"status": "duplicate"}` tanpa efek.
   Ini dicommit di transaksi terpisah sebagai jejak penerimaan.
4. Resolusi tenant dari `reference_id`/`external_id` dengan pola
   `aeos-{kind}-{tenant_uuid}-…`. Parser ketat (regex + validasi UUID +
   tenant ada). Lalu `tenant_context(tenant_id)`.
   - Invoice lama memakai `PaymentIntent` lookup tanpa RLS seperti
     sekarang (tetap kompatibel dengan intent yang sudah terbit).
5. Dispatch per `event_type` di **satu transaksi DB** bersama update
   `payment_webhook_events.status=processed`. Bila ada exception, rollback
   efek; event ditandai `failed` + `error` (transaksi terpisah) dan
   kembalikan **5xx** agar Xendit mengirim ulang. Pengiriman ulang lolos
   dedup karena baris berstatus `failed` boleh diproses ulang
   (`ON CONFLICT` dicek: bila status `failed`, proses lagi).
6. Efek bisnis memakai compare-and-set status sebagai lapis kedua:
   - `reconcile_payment` (perbaikan G7):
     `UPDATE payment_intents SET status='paid', paid_at=… WHERE id=:id AND status='pending'`.
     Hanya bila rowcount 1 efek dijalankan (aktivasi/top-up/renewal +
     kwitansi).
   - Charge: lihat §6.3.
   - Payment method: `pending_activation → active` hanya dari
     `pending_activation`. `active → expired` boleh. Status `removed`
     tidak pernah dihidupkan lagi.
7. **Event tidak berurutan**: transisi status monoton. Status terminal
   (`paid`, `succeeded`, `removed`) tidak ditimpa event lebih lama
   (mis. `EXPIRED` invoice setelah `PAID` diabaikan dan dicatat
   `ignored`). Bila `payment.failed` datang setelah `succeeded`, abaikan
   dan catat di log peringatan. Bila `succeeded` datang setelah `failed`
   (jarang, tetapi mungkin karena retry vendor), terapkan sukses
   (uang benar-benar masuk) dan catat audit `billing.charge_late_success`.
8. Webhook untuk objek yang tidak dikenal: `ignored`, respons 200 (agar
   tidak di-retry tanpa akhir).

---

## 8. Aturan gagal bayar (e)

### 8.1 State machine langganan

```
            bayar awal (invoice)                 renewal sukses
  (tidak ada) ───────────────► AKTIF ◄──────────────────────────┐
                                 │                              │
                  current_period_end lewat                      │
                  & charge/invoice renewal gagal                │
                                 ▼                              │
                             MENUNGGAK ── bayar tunggakan ──────┘
                           (past_due_since)    (invoice renewal / retry PM)
                                 │
                  lewat batas penagihan (K4)
                                 ▼
                            DIBATALKAN  ── subscribe baru ──► AKTIF (baris baru)
```

- Masuk `MENUNGGAK` **langsung** saat percobaan renewal pertama gagal,
  atau saat invoice renewal tidak dibayar sampai `current_period_end`.
  PRD: "berhenti total". Grace period default **0 hari**, dapat diubah via
  env `BILLING_RENEWAL_GRACE_DAYS` (default `0`), menunggu keputusan K4.
- Retry renewal otomatis selama `MENUNGGAK` (bila ada PM): H+1, H+3, H+7
  (usulan K6). Setiap percobaan memakai idempotency key berbeda
  (`attempt_no`).
- `DIBATALKAN` otomatis setelah N hari menunggak (usulan 30, K4). Data
  tenant **tidak dihapus**. Kebijakan retensi data di luar cakupan
  dokumen ini.
- Saat membayar tunggakan, `current_period_end` diperpanjang dari
  **tanggal jatuh tempo lama**, bukan tanggal bayar, supaya tidak ada
  periode gratis (K13). Siklus jatah baru dibuka saat itu juga.
- `_activate_subscription` diperbaiki (G11): batalkan baris berstatus
  `active` **atau** `past_due`.

### 8.2 Penegakan renewal: "akses berhenti total"

- `has_active_subscription` (`billing/service.py:18-31`) tetap menjadi satu
  titik kebenaran, dengan tambahan pengecekan DB murni (tanpa HTTP):
  `status == active AND (current_period_end IS NULL OR today <= current_period_end + grace_days + processing_days)`.
  `processing_days` (usulan 1) memberi jeda bagi cron renewal agar tenant
  tidak terkunci hanya karena cron telat. `current_period_end IS NULL`
  berarti baris legacy/override platform (tidak dikunci).
- Karena `require_active_subscription()` dipakai di 40+ router, semua
  modul bisnis otomatis tertutup (403, `detail` baru: "Langganan menunggak.
  Selesaikan pembayaran di halaman Pembayaran.") dengan kode error stabil
  di header/body `{"code": "subscription_past_due"}` agar frontend bisa
  membedakannya dari "belum berlangganan".
- Safety-net di guard **tidak** memanggil Xendit (request tidak boleh
  menunggu gateway). Guard hanya menandai status `past_due` bila tanggal
  sudah lewat dan cron belum memproses.
- Router billing dipecah (G12):
  - `billing_account_router` (guard `get_current_user` +
    `require_tenant_user()`, **tanpa** `require_active_subscription`):
    status, paket, subscribe, metode bayar, kwitansi, profil, retry
    renewal. Tenant menunggak tetap bisa membayar.
  - `router` yang ada (guard aktif): balance-summary, topup, transaksi,
    pengaturan auto-reload.
  - `subscribe_router` yang ada dilebur ke `billing_account_router`.
- Login **tidak** diblokir (beda dari tenant `ditangguhkan` di
  `auth/router.py:116-127`). Tenant harus bisa login untuk membayar.

### 8.3 Penegakan auto-reload gagal: "hanya metered diblokir"

Fungsi baru `assert_metered_allowed(db, tenant_id)` di `billing/service.py`.
Hasilnya 402 dengan `{"code": "metered_blocked", "reason": …}` bila
`metered_blocked_at IS NOT NULL` **atau** total sisa ≤ 0. Bypass untuk
billing internal.

Daftar fitur metered (inventaris per hari ini):

| Event | Lokasi | Penegakan |
|---|---|---|
| `recruitment.match_executed` | `recruitment/service.py:1486` | Sudah fail-closed lewat `charge_metered_event`. Tambah `assert_metered_allowed` di awal fungsi sebelum kerja berat |
| `finance.invoice_issued` | `finance/service.py:187` | Sama |
| `invoice.tax_invoice_sent` | `finance/service.py:930` | Sama (cek **sebelum** submit DJP sungguhan) |
| `ai_usage` (semua panggilan LLM) | `core/llm.py` `chat_completion` / `vision_completion` / `embed_texts` | **Baru**: pre-check di awal fungsi memakai sesi terpisah (pola `ai_usage.py`) dan tenant dari `get_tenant()`. Ini satu-satunya cara memblokir AI karena debit pasca-fakta tidak bisa menolak |
| `cycle_close.talent_active` / `employee_active` | `cycle_close.py` | **Tidak diblokir** (biaya periodik, `allow_negative`) |

Pengecualian AI yang perlu diputuskan (K7): pipeline yang dipicu pihak
ketiga dan bukan user tenant, misalnya kandidat yang sedang AI Interview
(agen suara, scoring pasca-interview). Memblokirnya di tengah sesi
merusak pengalaman kandidat. Usulan: sesi yang sudah dimulai boleh selesai
(allowlist `feature` tertentu), sedangkan sesi baru ditolak di titik
pembuatan undangan.

Data dan fitur non-metered tetap jalan karena `require_active_subscription`
tidak membaca `metered_blocked_at`.

### 8.4 Renewal: alur penagihan

Cron baru `POST /platform/internal/run-renewals` (harian, mis. 01:00 WIB):

1. Untuk langganan `active` dengan `auto_renew=True` dan
   `current_period_end - H7 <= today` **tanpa** PM default: terbitkan
   invoice renewal (`PaymentIntent type=renewal`, idempoten per
   `(subscription_id, period_end)` lewat cek intent pending yang ada),
   lalu kirim notifikasi H-7, H-3, H-1.
2. Untuk langganan dengan PM default pada `current_period_end <= today`:
   buat `payment_charges(purpose=renewal)` lalu eksekusi seperti §6.2.
   Sukses: `current_period_end += 1 bulan / 1 tahun`, kwitansi, ledger
   `subscription_renewal`, audit. Gagal: `MENUNGGAK` + notifikasi + jadwal
   retry.
3. `auto_renew=False`: pada `current_period_end` langsung `DIBATALKAN`
   (berhenti normal, bukan gagal bayar).
4. Harga renewal: `period_fee` dihitung ulang dari **harga dan diskon
   saat ini** (env) atau dari snapshot lama? Ini K14. Usulan: harga saat
   ini, dengan notifikasi H-30 bila berubah.

`cycle_close.close_cycle_for_tenant` tidak lagi membuka siklus baru bila
`today > current_period_end` (langganan belum diperpanjang). Siklus baru
dibuka oleh renewal sukses.

**Feature flag peluncuran**: env `BILLING_RENEWAL_ENFORCEMENT` (default
`false`). Saat `false`, renewal hanya menerbitkan invoice dan notifikasi;
penegakan `current_period_end` di guard dimatikan. Ini memberi waktu untuk
komunikasi ke tenant existing yang selama ini tidak pernah ditagih
renewal (G1).

---

## 9. Kwitansi PDF (c)

- **Kapan dibuat**: di transaksi yang sama dengan efek pembayaran yang
  berhasil, yaitu aktivasi langganan, top-up invoice, renewal (invoice
  atau charge), dan auto-reload. Override tier oleh platform admin
  (`platform/router.py:246`) **tidak** menerbitkan kwitansi karena tidak
  ada uang yang masuk lewat sistem (K15: perlu kwitansi manual?).
- **Penomoran**: `AEOS/KW/{YYYY}/{seq:06d}`, berurutan dan unik **per
  tahun kalender, lintas tenant** (§3.1). Tahun diambil dari `issued_at`
  dalam zona waktu `Asia/Jakarta`. Nomor tidak pernah dipakai ulang; bila
  transaksi rollback setelah alokasi, nomor ikut rollback karena
  `UPDATE … RETURNING` berada di transaksi yang sama, sehingga tidak ada
  lubang. Format final mengikuti K5/K8.
- **Isi wajib** (dari snapshot, bukan data live):
  - Judul "KWITANSI" + nomor + tanggal.
  - Penjual, dari env baru: `AEOS_SELLER_NAME`, `AEOS_SELLER_NPWP`,
    `AEOS_SELLER_ADDRESS`, `AEOS_SELLER_EMAIL`, `AEOS_SELLER_IS_PKP`
    (bool). Bila `NAME`/`NPWP` kosong saat `PAYMENT_PROVIDER=xendit`,
    startup memberi warning dan penerbitan kwitansi gagal tertutup.
    Kwitansi tetap dibuat tetapi ditandai "DRAFT – identitas penjual belum
    dikonfigurasi"? Atau tolak? Ini K8. Di test/sandbox boleh placeholder.
  - Pembeli: `TenantBillingProfile` (legal_name, NPWP, alamat). Bila
    profil belum diisi, pakai `Tenant.name`, dan UI meminta melengkapi
    profil sebelum pembayaran pertama.
  - Rincian baris: deskripsi ("Langganan Tier 2 – Tahunan
    01/11/2026–31/10/2027", "Auto-reload saldo kredit"), qty, harga, diskon
    (bila tahunan), subtotal.
  - PPN: hanya bila `AEOS_SELLER_IS_PKP=true`. Tarif dari env
    `BILLING_PPN_RATE`, dengan DPP sesuai aturan yang berlaku (mis. DPP
    11/12 × harga jual dengan tarif 12% per PMK 131/2024; **wajib
    dikonfirmasi konsultan pajak**). Apakah harga tier sudah termasuk PPN
    adalah K5.
  - Metode bayar (label aman) dan referensi gateway.
  - Terbilang rupiah (opsional, lazim di kwitansi Indonesia).
  - Catatan: "Kwitansi ini bukan Faktur Pajak" bila Aeos PKP (e-Faktur
    keluaran Aeos sendiri adalah proses terpisah, K5).
  - **Bea meterai**: kwitansi dengan nilai **> Rp5.000.000** terutang bea
    meterai Rp10.000 (UU 10/2020). Paket tahunan tier mana pun dan
    tier 3 + PPN akan melewati batas ini. Perlu keputusan e-meterai
    (K9). v1 bisa menulis "Bea meterai dibayar secara elektronik/terpisah"
    hanya bila memang dibayar.
- **Rendering**: fungsi baru `billing/receipts.py::render_receipt_pdf(receipt) -> bytes`
  memakai idiom reportlab yang sudah ada (import lazy, `BytesIO`, `escape`;
  lihat `presales/rendering.py` dan tabel di `finance/service.py:982`).
  Layout tabel butuh `Table`, sehingga tidak cukup memakai
  `render_document_pdf` apa adanya. Tidak ada dependency baru.
- **Immutable**: render pertama memanggil `put_object` dengan key
  `billing/receipts/{tenant_id}/{receipt_number_slug}.pdf`, lalu mengisi
  `pdf_object_key` dan `pdf_sha256` lewat compare-and-set
  (`WHERE pdf_object_key IS NULL`). Request berikutnya selalu menyajikan
  objek tersimpan. Tidak ada endpoint edit/hapus. Koreksi dilakukan lewat
  nota/kwitansi pembatalan baru (K16), bukan mengubah yang lama.
- **Penyajian**: `GET /billing/receipts/{id}/pdf` mengembalikan
  `StreamingResponse` dengan `Content-Disposition: attachment` (pola
  unduhan PDF yang sudah ada di modul lain). Presigned URL tidak dipakai
  agar guard tenant tetap berlaku.
- **Email**: bila SMTP aktif, kirim PDF ke `billing_email` setelah
  pembayaran (best-effort, di luar transaksi) memakai
  `send_raw_email_with_attachment`.

---

## 10. Endpoint

Prefix `/api/v1`. "Manage" = `require_roles(*BILLING_MANAGE_ROLES)`
(finance, management; admin otomatis lolos). Guard router:
**A** = `billing_account_router` (tenant user, tanpa syarat langganan
aktif), **S** = `router` yang ada (langganan aktif).

### 10.1 Tenant

| Method & path | Guard | Request | Response ringkas |
|---|---|---|---|
| `GET /billing/status` | A | – | `{subscription: {tier, status, billing_period, current_period_end, past_due_since, auto_renew} \| null, access: "full" \| "metered_blocked" \| "none", block_reason, auto_reload: {enabled, last_error, failure_count}, has_default_payment_method}`. Untuk banner. Ringan, tanpa HTTP gateway |
| `GET /billing/plans` | A | – | `[{tier, monthly_fee, included_budget, annual: {available, fee, discount_percent} }]`. Menggantikan `TIERS` hardcode di frontend |
| `POST /billing/subscribe` (diubah) | A + Manage | `{tier, billing_period: "monthly" \| "annual" = "monthly"}` | `{intent_id, checkout_url}`. 422 bila `annual` dan diskon tahunan belum dikonfigurasi |
| `PATCH /billing/subscription` | A + Manage | `{auto_renew?: bool}` | Status langganan. Upgrade/downgrade tetap lewat `/subscribe` (K17 untuk prorata tahunan) |
| `POST /billing/subscription/retry-renewal` | A + Manage | `{payment_method_id?}` | `{charge_id, status}` atau `{checkout_url}` (invoice tunggakan) |
| `GET /billing/payment-config` | A | – | `{provider, xendit_public_key \| null, supported_types: ["card","gopay"]}` |
| `GET /billing/payment-methods` | A + Manage | – | `[{id, type, status, card_brand, card_last4, card_exp_month, card_exp_year, ewallet_account_masked, is_default, created_at}]` |
| `POST /billing/payment-methods` | A + Manage | `{type: "card", card_token_id}` atau `{type: "gopay"}`. **Schema menolak field tak dikenal** (`extra="forbid"`) sehingga `card_number`/`cvv` otomatis 422 | `{id, status, action: {kind, url} \| null}`. Frontend me-redirect ke `action.url` untuk 3DS/linking |
| `POST /billing/payment-methods/{id}/default` | A + Manage | – | Daftar terbaru. Hanya PM `active` |
| `DELETE /billing/payment-methods/{id}` | A + Manage | – | 204. `expire` di Xendit, status `removed`. Bila PM default dan auto-reload aktif: 409 kecuali ada PM lain atau `?force=true` (yang mematikan auto-reload). Bila charge in-flight memakai PM ini: 409 |
| `GET /billing/profile` / `PUT /billing/profile` | A (+ Manage untuk PUT) | `{legal_name, npwp?, address?, billing_email?}` | Profil |
| `GET /billing/receipts?limit&offset` | A + Manage | – | `[{id, receipt_number, issued_at, total, description, source_type}]` |
| `GET /billing/receipts/{id}/pdf` | A + Manage | – | `application/pdf` |
| `GET /billing/transactions` (diubah) | S | – | Ditambah `receipt_id` (nullable) per baris |
| `GET/PUT /billing/auto-reload-settings` (diubah) | S | `{enabled, threshold}`. `amount` diabaikan atau ditolak bila K3 = tetap 100rb | Ditambah `{effective: bool, reason}`. `effective=false` bila tidak ada PM default aktif. `enabled=true` tanpa PM default: 422 |
| `POST /billing/topup` | S | (tetap) | (tetap) |

Router sandbox (hanya sandbox + non-production): lihat §5.3.

### 10.2 Platform (`require_platform_admin()`)

| Method & path | Fungsi |
|---|---|
| `POST /platform/internal/run-auto-reload` | Cron eksekusi/rekonsiliasi charge auto-reload |
| `POST /platform/internal/run-renewals` | Cron renewal + pengingat + pembatalan menunggak |
| `GET /platform/tenants/{id}/billing-summary` (diubah) | Ditambah `billing_period`, `current_period_end`, `subscription_status` (termasuk menunggak), `metered_blocked`, `block_reason`, `default_payment_method` (label aman), `last_payment_failure` |
| `PATCH /platform/tenants/{id}/subscription` (diubah) | Terima `billing_period` opsional dan `current_period_end` opsional untuk intervensi support. Tetap tanpa kwitansi |
| `POST /platform/tenants/{id}/billing/unblock-metered` | Cabut blokir metered manual (audit wajib) |
| `GET /platform/billing/webhook-events?status=failed` | Investigasi event gagal |

**Tidak ada endpoint konfigurasi diskon.** Diskon tahunan memakai env
`BILLING_ANNUAL_DISCOUNT_PERCENT` (lihat §2 butir 3 dan §12).

---

## 11. Setting/env baru (`core/config.py`)

Semua field string masuk daftar validator `_empty_to_none`.

| Env | Default | Arti |
|---|---|---|
| `XENDIT_PUBLIC_KEY` | None | Public key untuk tokenisasi di browser |
| `BILLING_ANNUAL_DISCOUNT_PERCENT` | **None** | **None berarti paket tahunan tidak ditawarkan** (`/plans` mengembalikan `annual.available=false`, `/subscribe annual` 422). Nilai valid `0 ≤ x < 100` (Decimal). `0` berarti tahunan tersedia tanpa diskon, sebagai pilihan sadar |
| `BILLING_RENEWAL_ENFORCEMENT` | `false` | Feature flag §8.4 |
| `BILLING_RENEWAL_GRACE_DAYS` | `0` | K4 |
| `BILLING_RENEWAL_PROCESSING_DAYS` | `1` | Toleransi cron |
| `BILLING_PAST_DUE_CANCEL_DAYS` | `30` | K4 |
| `BILLING_AUTO_RELOAD_DEFAULT_THRESHOLD` | None | K2. None berarti tenant wajib mengisi ambang saat mengaktifkan |
| `AEOS_SELLER_NAME/NPWP/ADDRESS/EMAIL` | None | Identitas penjual di kwitansi |
| `AEOS_SELLER_IS_PKP` | `false` | |
| `BILLING_PPN_RATE` | None | Hanya dipakai bila PKP. **Tidak** di-hardcode |

Kenapa default diskon `None`, bukan `0`: dengan `0`, UI akan menampilkan
opsi "Tahunan" yang mengunci tenant 12 bulan tanpa manfaat apa pun, dan
pemilik produk bisa tidak sadar bahwa opsi itu sudah tayang. `None`
membuat fitur gagal tertutup sampai angka diputuskan. Validasi di
`field_validator` menolak nilai negatif atau ≥ 100 saat startup.

Rumus: `annual_fee = round_rupiah(monthly_fee × 12 × (1 − d/100))`,
memakai `Decimal` dan pembulatan ke rupiah penuh lewat `core/money.py`.
Nilai di-snapshot ke `PaymentIntent.discount_percent` lalu ke
`TenantSubscription.discount_percent/period_fee` saat aktivasi.

---

## 12. Audit log

Semua lewat `audit.service.log_event` dengan `entity_type` yang relevan.
`detail` **tidak pernah** berisi token, PAN, atau payload mentah.

| action | Kapan |
|---|---|
| `billing.payment_method_added` | PM dibuat (status awal) |
| `billing.payment_method_activated` / `billing.payment_method_failed` / `billing.payment_method_expired` | Hasil webhook/aktivasi |
| `billing.payment_method_removed` | DELETE |
| `billing.payment_method_default_changed` | Set default (detail: id lama → baru) |
| `billing.auto_reload_settings_changed` | PUT pengaturan (nilai lama → baru) |
| `billing.auto_reload_triggered` | Baris charge dibuat |
| `billing.auto_reload_succeeded` / `billing.auto_reload_failed` | Hasil |
| `billing.metered_blocked` / `billing.metered_unblocked` | Perubahan state blokir (detail: reason, pemicu) |
| `billing.subscription_checkout_created` | `/subscribe` (tier, periode, diskon) |
| `billing.subscription_activated` / `billing.subscription_renewed` | |
| `billing.subscription_renewal_failed` | |
| `billing.subscription_past_due` / `billing.subscription_cancelled` | Transisi state |
| `billing.subscription_auto_renew_changed` | |
| `billing.receipt_issued` | Nomor kwitansi dialokasikan |
| `billing.receipt_downloaded` | Opsional (volume rendah, berguna untuk sengketa) |
| `billing.billing_profile_updated` | |
| `billing.webhook_failed` | Event gagal diproses |
| `billing.charge_late_success` | §7 butir 7 |
| `platform.subscription_overridden` / `platform.metered_unblocked` | Aksi platform admin |

---

## 13. Rencana test

Semua test memakai SQLite in-memory (`conftest.py`), dengan
`PAYMENT_PROVIDER=sandbox` di-patch atau `get_adapter` di-monkeypatch ke
`FakeAdapter`. Tidak ada kredensial asli. File baru:
`tests/test_billing_payment_methods.py`, `test_billing_auto_reload.py`,
`test_billing_receipts.py`, `test_billing_annual.py`,
`test_billing_renewal.py`, `test_billing_webhook_idempotency.py`.

**Metode bayar**

1. Tambah kartu `sbx-tok-ok` menghasilkan `active`, metadata tampilan
   terisi, dan PM pertama otomatis jadi default.
2. Tambah kartu `sbx-tok-3ds` menghasilkan `requires_action` + `action.url`.
   Simulasi activate lewat webhook membuat status `active`.
3. Tambah GoPay menghasilkan `pending_activation`. Webhook
   `payment_method.activated` membuat status `active` dengan nomor
   tersamar.
4. POST dengan field `card_number`/`cvv` menghasilkan 422 (`extra=forbid`).
5. Regresi skema: tidak ada kolom bernama mirip `pan|card_number|cvv|cvc`
   di `Base.metadata` (inspeksi semua tabel).
6. Hapus PM default saat auto-reload aktif tanpa PM lain menghasilkan 409.
   Dengan `force=true`, auto-reload mati dan `expire_payment_method`
   terpanggil.
7. Set default ke PM `pending`/`removed` menghasilkan 422.
8. Isolasi tenant: tenant B tidak bisa melihat, menghapus, atau set default
   PM tenant A (404).
9. Role `operations` mendapat 403. `finance` dan admin lolos.

**Auto-reload**

10. Debit metered membuat saldo turun di bawah ambang, sehingga satu
    `payment_charges` pending terbentuk dan kunci in-flight terisi.
11. Dua debit beruntun selagi in-flight hanya menghasilkan satu charge
    (compare-and-set).
12. Cron `run-auto-reload` dengan fake `succeeded` menghasilkan ledger
    `topup_auto_reload` +100.000, kwitansi terbit, kunci dilepas, dan
    `failure_count=0`.
13. Jalur reaktif: saldo 0, `charge_metered_event` membuat charge sinkron
    sukses, debit berhasil (bukan 402), dan ada dua baris ledger.
14. Jalur reaktif gagal menghasilkan 402 `metered_blocked`, lalu
    `metered_blocked_at` terisi dan `next_retry_at` sesuai backoff.
15. Timeout (`sbx-tok-timeout`) menghasilkan status `unknown`. Cron
    berikutnya memanggil `get_charge_by_reference` dulu dan tidak membuat
    charge ganda (fake menghitung panggilan `charge_saved_method` = 1).
16. Kirim ulang dengan idempotency key sama tidak mengkredit dua kali.
17. Webhook `payment.succeeded` lalu respons sinkron sukses (dua jalur
    menerapkan sukses) hanya menghasilkan satu kredit.
18. Top-up manual sukses saat diblokir mencabut blokir, dan
    `assert_metered_allowed` lolos.
19. AI pre-check: `chat_completion` saat diblokir menghasilkan 402 sebelum
    HTTP ke provider LLM (mock `httpx` tidak terpanggil).
20. Tenant billing bypass (internal) tidak pernah memicu auto-reload dan
    tidak pernah diblokir.
21. `enabled=true` tanpa PM default menghasilkan 422. `effective` bernilai
    false saat PM dihapus.
22. Tanpa cap: 5 siklus pemicu-sukses berturut-turut semuanya tereksekusi
    (tidak ada batas bulanan).

**Webhook**

23. Token salah menghasilkan 401 tanpa baris event.
24. Event duplikat (dedup_key sama) menghasilkan 200 `duplicate` dan efek
    tunggal.
25. Race G7: dua pemanggilan `reconcile_payment` untuk intent yang sama
    (disimulasikan dengan dua sesi) hanya menghasilkan satu aktivasi atau
    satu kredit.
26. `EXPIRED` setelah `PAID` diabaikan. `failed` setelah `succeeded`
    diabaikan.
27. Exception di handler menghasilkan 500, event `failed`, dan tidak ada
    efek parsial. Pengiriman ulang diproses sukses.
28. `reference_id` dengan tenant tidak dikenal menghasilkan 200 `ignored`.

**Kwitansi**

29. Aktivasi langganan via webhook menerbitkan satu kwitansi dengan nomor
    `AEOS/KW/{tahun}/000001`, dan pembayaran berikutnya `000002` meskipun
    tenant berbeda (urut global).
30. Penomoran per tahun: dengan waktu dipatch ke 31 Des lalu 1 Jan, nomor
    kembali ke `000001` di tahun baru.
31. Unique per pembayaran: webhook diulang tidak menerbitkan kwitansi
    kedua.
32. Unduh PDF pertama mengisi `pdf_object_key` + `sha256`. Unduhan kedua
    memberi byte identik dan tidak me-render ulang (mock renderer
    terpanggil 1×).
33. Snapshot: ubah profil tenant setelah terbit, PDF tetap memuat data
    lama.
34. PPN: `AEOS_SELLER_IS_PKP=false` menghasilkan `ppn_amount=0`. Dengan
    PKP + rate, nilai DPP/PPN sesuai rumus (`Decimal`, tanpa selisih
    float).
35. Tenant B mendapat 404 untuk kwitansi tenant A.
36. Isi PDF (via `pypdf` yang sudah jadi dependency) memuat nomor, nama
    penjual, nama pembeli, dan total.

**Tahunan**

37. `BILLING_ANNUAL_DISCOUNT_PERCENT` tidak diset: `/plans`
    `annual.available=false` dan `/subscribe annual` 422.
38. Diset `d` (mis. 15, angka hanya contoh test): `fee = 12 × monthly ×
    0.85`, snapshot di intent. Setelah webhook, subscription
    `billing_period=annual`, `current_period_end` = +1 tahun, dan siklus
    jatah tetap bulanan.
39. Env diubah setelah bayar tidak mengubah `period_fee` langganan
    berjalan.
40. Validasi env: `-1` dan `100` ditolak saat load settings.

**Renewal & gagal bayar**

41. Flag enforcement mati: lewat `current_period_end` akses tetap jalan,
    dan invoice renewal terbit.
42. Flag nyala dan renewal charge gagal: status `menunggak`, endpoint
    bisnis 403 `subscription_past_due`, sementara `/billing/status`,
    `/billing/payment-methods`, `/billing/receipts`, dan `/billing/subscribe`
    tetap 200.
43. Retry renewal sukses: status `aktif`, `current_period_end` diperpanjang
    dari jatuh tempo lama, siklus baru dibuka, kwitansi terbit.
44. Menunggak lebih dari `PAST_DUE_CANCEL_DAYS`: status `dibatalkan`.
    Subscribe baru membatalkan baris menunggak (G11).
45. `auto_renew=False`: pada jatuh tempo status `dibatalkan` tanpa charge.
46. Guard tanpa cron: tanggal lewat + `processing_days` membuat guard
    menolak walaupun cron tidak jalan, dan tidak ada panggilan HTTP dari
    guard.
47. Metered diblokir **tidak** memblokir endpoint non-metered (mis. list
    karyawan 200).
48. `close_cycle_for_tenant` tidak membuka siklus baru bila langganan
    belum diperpanjang.

**Migrasi**

49. `test_migrations.py` hijau. Backfill: subscription lama mendapat
    `billing_period=monthly`, `period_fee=monthly_fee`, dan
    `current_period_end` = period_end siklus terbuka (test upgrade dari
    revisi sebelumnya dengan data contoh).
50. `test_rls_coverage.py` (Postgres) hijau tanpa menambah
    `EXCLUDED_TABLES`.

---

## 14. Perubahan frontend (untuk agent frontend)

- **Kontrak API**: tipe baru di `Billing.tsx` atau file `api/billing.ts`
  sesuai §10. Hapus `TIERS` hardcode (`Billing.tsx:31-35`) dan ganti
  dengan `GET /billing/plans`.
- **Toggle Bulanan/Tahunan** di tab "Pilih Paket" (`PillTabs`/segmented):
  tampil hanya bila `annual.available`. Kartu menampilkan harga per tahun,
  ekuivalen per bulan, dan label "hemat X%". Kirim `billing_period` ke
  `/subscribe`. Teks: jatah saldo tetap reset bulanan.
- **Tab baru "Metode Bayar"**: daftar PM (ikon brand, •••• last4,
  kedaluwarsa, badge Default/Menunggu aktivasi/Kedaluwarsa), tombol
  "Jadikan default", "Hapus" (dialog konfirmasi; tangani 409 dengan
  pesan). Tambah kartu memakai Xendit.js (muat skrip dari `js.xendit.co`
  hanya di halaman ini; perbarui CSP bila nanti ada). Input kartu dikirim
  ke Xendit dari browser, lalu POST `{type:"card", card_token_id}`. Tambah
  GoPay: POST, lalu redirect ke `action.url`. Halaman kembali
  `/billing?pm={id}` melakukan polling status. Callout wajib (PRD
  §4.4.5): auto-reload hanya untuk kartu/GoPay tersimpan; QRIS/VA harus
  top-up manual.
- **Auto-reload**: ganti callout "baru pengaturan" (`Billing.tsx:281-286`)
  dengan status nyata (`effective`, error terakhir). Nonaktifkan toggle
  bila belum ada PM default (dengan link ke tab Metode Bayar). Field
  nominal menjadi read-only Rp100.000 bila K3 = tetap.
- **Riwayat** (`DataTable`, `Billing.tsx:290-299`): kolom aksi "Kwitansi"
  (ikon unduh) bila `receipt_id` ada. Unduh blob via `api` client (perlu
  helper unduhan dengan header Authorization; cek helper yang sudah ada di
  halaman lain yang mengunduh PDF). Opsional tab "Kwitansi" sendiri dari
  `GET /billing/receipts`.
- **Profil penagihan**: form kecil (nama legal, NPWP, alamat, email
  tagihan). Diminta sebelum checkout pertama bila kosong.
- **Banner gagal bayar** global di `Layout` (di bawah topbar), dari
  `GET /billing/status`:
  - `access="none"` (menunggak): banner merah "Langganan menunggak sejak
    {tgl} — akses dihentikan" dengan CTA ke /billing. Interceptor 403
    `code=subscription_past_due` mengarahkan ke /billing, bukan halaman
    error generik.
  - `access="metered_blocked"`: banner oranye "Auto-reload gagal: fitur
    berbayar (AI, pencocokan kandidat, terbit invoice/faktur) diblokir.
    Data tetap bisa diakses." dengan CTA Top Up atau Perbarui metode
    bayar. Tangani 402 `code=metered_blocked` di aksi terkait dengan toast
    yang sama.
- **Sandbox**: route `/sandbox/billing/:invoiceId/pay` (G10) dan halaman
  otorisasi PM sandbox. Hanya bermakna saat provider sandbox.
- **PlatformTenants.tsx**: panel Billing ditambah periode, jatuh tempo,
  status menunggak, metered blocked + tombol "Cabut blokir", PM default
  (label aman), dan kegagalan terakhir.
- Verifikasi: `cd frontend && npm run build` + Vitest untuk logika toggle
  harga dan pemetaan banner.

---

## 15. Keputusan terbuka (butuh jawaban pemilik produk sebelum implementasi)

| # | Keputusan | Usulan default bila tidak dijawab |
|---|---|---|
| K1 | **Besaran diskon tahunan.** | Env `None`, sehingga paket tahunan tidak tayang |
| K2 | **Ambang auto-reload default** dan basisnya: total sisa (jatah siklus + saldo top-up) atau hanya saldo top-up? Bisa diubah tenant? | Basis total sisa, diisi tenant (wajib saat mengaktifkan), tanpa default global |
| K3 | Nominal reload: **tetap Rp100.000** (PRD) atau boleh diubah tenant (UI sekarang mengizinkan)? | Tetap Rp100.000, field read-only |
| K4 | **Grace period renewal** (PRD: "berhenti total" tanpa menyebut grace) dan berapa hari menunggak sebelum otomatis dibatalkan | Grace 0 hari, toleransi proses cron 1 hari, batal otomatis setelah 30 hari |
| K5 | **Status PKP Aeos dan PPN di kwitansi**: harga tier sudah termasuk PPN atau belum? Tarif/DPP yang dipakai? Apakah Aeos juga menerbitkan e-Faktur keluaran sendiri (di luar cakupan dokumen ini)? | Non-PKP (tanpa PPN) sampai dikonfirmasi konsultan pajak |
| K6 | **Kebijakan retry**: jadwal backoff auto-reload & renewal, dan daftar kode gagal permanen | Auto-reload +15 menit / +1 jam / +6 jam lalu berhenti. Renewal H+1/H+3/H+7 |
| K7 | **Pengecualian blokir AI** untuk alur pihak ketiga (AI Interview kandidat yang sedang berjalan, scoring pasca-interview) | Sesi berjalan boleh selesai, sesi/undangan baru ditolak |
| K8 | Format nomor kwitansi dan perilaku bila identitas penjual belum dikonfigurasi di produksi (tolak pembayaran vs kwitansi draft) | `AEOS/KW/YYYY/NNNNNN`. Produksi gagal start-check (warning keras) dan kwitansi ditunda sampai env diisi |
| K9 | **Bea meterai** untuk kwitansi > Rp5 juta (semua paket tahunan, tier 3 + PPN): pakai e-meterai (integrasi baru, berbayar) atau proses manual? | v1 manual di luar sistem, dan kwitansi mencantumkan catatan |
| K10 | Renewal dikelola cron Aeos (usulan) atau Xendit Recurring/Subscriptions API (disebut di PRD §4.4.5)? | Cron Aeos |
| K11 | Interval cron auto-reload/renewal dan siapa yang mengoperasikan (Task Scheduler/cron produksi) | Auto-reload tiap 2 menit, renewal harian 01:00 WIB |
| K12 | Charge MIT yang meminta `requires_action` (3DS ulang): langsung blokir + minta verifikasi ulang, atau tunggu? | Perlakukan sebagai gagal + notifikasi verifikasi ulang |
| K13 | Bayar tunggakan: periode baru dihitung dari jatuh tempo lama (tanpa hari gratis) atau dari tanggal bayar? | Dari jatuh tempo lama |
| K14 | Harga renewal: harga dan diskon terkini atau snapshot saat pertama berlangganan? | Harga terkini + pemberitahuan H-30 bila berubah |
| K15 | Override tier oleh platform admin (pembayaran di luar sistem) perlu kwitansi manual? | Tidak, di luar sistem |
| K16 | Refund/pembatalan: perlu dokumen pembatalan kwitansi di v1? | Di luar cakupan v1 (tidak ada refund self-service) |
| K17 | **Upgrade/downgrade di tengah paket tahunan**: cutover tanpa prorata (aturan sekarang) membuat sisa bulan hangus. Prorata ke saldo, larang sampai renewal, atau tetap cutover? | Upgrade: sisa nilai dikreditkan ke saldo top-up. Downgrade: hanya saat renewal |
| K18 | Peluncuran penegakan renewal ke tenant existing yang selama ini tidak pernah ditagih renewal (G1): tanggal mulai dan komunikasi | Flag `BILLING_RENEWAL_ENFORCEMENT=false` sampai ada pengumuman H-30 |
| K19 | Metode tersimpan selain kartu/GoPay (OVO/DANA/ShopeePay linked)? | Kartu + GoPay saja (sesuai PRD) |

Asumsi teknis yang perlu diverifikasi terhadap akun Xendit (bukan
keputusan produk) ada di §5.2: versi API (v2 Payment Methods vs v3 Payment
Tokens), flow tokenisasi kartu, MIT tanpa 3DS, limit debit GoPay
tokenized, dan header id webhook.

---

## 16. Urutan implementasi bertahap

Setiap fase berdiri sendiri, punya test, dan lolos `make lint` + `make test`
+ `npm run build` sebelum commit. Migrasi tunggal masuk di F1 (semua
kolom/tabel sekaligus) agar hanya ada satu revisi.

| Fase | Isi | Bergantung |
|---|---|---|
| **F0 — Perkuat yang ada** | Compare-and-set di `reconcile_payment` (G7). Parameter `tx_type` di `record_credit_transaction` (G9). Router + halaman sandbox pay (G10). Fix `_activate_subscription` untuk `past_due` (G11). Test 25 dan 28 | – |
| **F1 — Skema** | Satu migrasi §4, model §3, settings §11 (validator diskon). `payment_webhook_events` + webhook dispatcher §7 (invoice lama dialihkan lewat dispatcher). Test 23–28, 49–50 | F0 |
| **F2 — Adapter & metode bayar** | Kontrak §5.1, sandbox/fake §5.3, `XenditAdapter` baru (setelah verifikasi §5.2 di mode test Xendit), profil penagihan, endpoint PM + `payment-config`. Test 1–9 | F1 |
| **F3 — Kwitansi** | Sequence, `BillingReceipt`, renderer reportlab, endpoint list/unduh, penerbitan di aktivasi & top-up yang sudah ada, `receipt_id` di transaksi. Test 29–36. *(Bisa paralel dengan F2.)* | F1, K5, K8 |
| **F4 — Auto-reload & blokir metered** | §6 + §8.3: enqueue, compare-and-set, eksekutor, cron, jalur reaktif, `assert_metered_allowed` di 3 titik + pre-check `core/llm.py`, notifikasi, `/billing/status`. Test 10–22, 47 | F2, F3, K2, K3, K6, K7 |
| **F5 — Tahunan** | `/plans`, `billing_period` di subscribe, snapshot diskon, `current_period_end` tahunan. Test 37–40 | F1, F3 |
| **F6 — Renewal & gagal bayar** | Pecah router (G12), state machine §8.1, cron renewal §8.4, guard `current_period_end`, `cycle_close` mengikuti masa bayar, retry-renewal, flag enforcement. Test 41–46, 48 | F2–F5, K4, K10, K13, K14, K18 |
| **F7 — Frontend & platform** | §14 seluruhnya + perluasan billing-summary platform §10.2 | Bisa bertahap mengikuti F2–F6 |
| **F8 — Dokumen** | Perbarui PRD §15 #1–#3, Fase 28 item 5–6, FEATURE_ROADMAP, CHANGELOG, `.env.example` (env baru), runbook cron | Setiap fase |

Risiko utama yang perlu dipantau saat implementasi:

1. Jangan buka transaksi DB selama panggilan HTTP ke Xendit (§6.2 langkah
   1).
2. Jangan pernah membuat idempotency key baru untuk mencoba ulang charge
   yang hasilnya `unknown`; rekonsiliasi dulu.
3. Aktifkan penegakan renewal hanya lewat flag, dan hanya setelah
   komunikasi ke tenant existing (G1, K18).
