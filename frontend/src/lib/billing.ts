/**
 * Tipe & logika murni billing Opsi G (Fase 28 lanjutan). Sengaja dipisah dari
 * komponen supaya pemetaan status -> banner/label bisa dites tanpa DOM
 * (lihat billing.test.ts). Bentuk data mengikuti backend
 * `app/modules/billing/router.py` + `service.py`.
 */

import { ApiError } from "../api/client";

// ---------- Tipe API ----------

export type Tier = "tier1" | "tier2" | "tier3";
export type BillingPeriod = "monthly" | "annual";
export type SubscriptionStatus = "aktif" | "menunggak" | "dibatalkan";
export type BlockReason =
  | "subscription_past_due"
  | "no_subscription"
  | "auto_reload_failed"
  | "balance_exhausted";

export interface SubscriptionInfo {
  id: string;
  tier: Tier;
  status: SubscriptionStatus;
  billing_period: BillingPeriod;
  period_fee: number | null;
  discount_percent: number;
  current_period_end: string | null;
  past_due_since: string | null;
  auto_renew: boolean;
}

export interface BillingStatus {
  billing_bypass: boolean;
  subscription: SubscriptionInfo | null;
  access: "full" | "metered_blocked" | "none";
  block_reason: BlockReason | null;
  total_remaining: number;
  auto_reload: { enabled: boolean; failure_count: number; last_error: string | null };
  has_default_payment_method: boolean;
  renewal_enforcement: boolean;
}

export interface Plan {
  tier: Tier;
  monthly_fee: number;
  included_budget: number;
  annual: {
    available: boolean;
    fee: number | null;
    monthly_equivalent?: number;
    discount_percent: number | null;
  };
}

export interface PaymentConfig {
  provider: "sandbox" | "xendit" | null;
  xendit_public_key: string | null;
  supported_types: ("card" | "gopay")[];
}

export type PaymentMethodStatus = "pending_activation" | "active" | "failed" | "expired";

export interface PaymentMethod {
  id: string;
  type: "card" | "gopay";
  status: PaymentMethodStatus;
  card_brand: string | null;
  card_last4: string | null;
  card_exp_month: number | null;
  card_exp_year: number | null;
  ewallet_account_masked: string | null;
  failure_reason: string | null;
  is_default: boolean;
  label: string;
  created_at: string;
  activated_at: string | null;
}

export interface PaymentMethodCreated extends PaymentMethod {
  action: { kind: string; url: string } | null;
}

export interface BillingProfile {
  legal_name: string | null;
  npwp: string | null;
  address: string | null;
  billing_email: string | null;
  updated_at: string | null;
}

export interface Receipt {
  id: string;
  receipt_number: string;
  issued_at: string;
  total: number;
  description: string;
  source_type: "payment_intent" | "payment_charge";
  payment_method_label: string | null;
}

export interface BalanceSummary {
  cycle_remaining: number;
  cycle_included: number;
  credit_balance: number;
  state: "normal" | "warning" | "empty";
}

export interface Transaction {
  id: string;
  type: string;
  amount: number;
  ref_event: string;
  balance_after: number;
  created_at: string;
  receipt_id: string | null;
}

export interface AutoReloadSettings {
  enabled: boolean;
  threshold: number | null;
  amount: number;
  effective: boolean;
  reason: null | "disabled" | "no_payment_method" | "no_threshold";
  failure_count: number;
  last_error: string | null;
  next_attempt_at: string | null;
  in_flight: boolean;
}

export interface RetryRenewalResult {
  charge_id: string | null;
  status: "succeeded" | "failed" | "processing" | "unknown" | "invoice_created";
  checkout_url: string | null;
  failure_code: string | null;
  intent_id?: string;
}

// ---------- Label ----------

export const TIER_INFO: Record<Tier, { label: string; blurb: string }> = {
  tier1: { label: "Tier 1", blurb: "Untuk tenant baru — pemakaian ringan." },
  tier2: { label: "Tier 2", blurb: "Jatah bulanan lebih besar untuk tim aktif." },
  tier3: { label: "Tier 3", blurb: "Untuk operasi skala penuh, semua fitur." },
};

export function tierLabel(tier: string | null | undefined): string {
  if (!tier) return "-";
  return TIER_INFO[tier as Tier]?.label ?? tier;
}

export const PERIOD_LABEL: Record<BillingPeriod, string> = { monthly: "Bulanan", annual: "Tahunan" };

const TRANSACTION_LABEL: Record<string, string> = {
  debit_cycle: "Pemakaian (jatah bulanan)",
  debit_credit: "Pemakaian (saldo top up)",
  topup_manual: "Top up",
  topup_auto_reload: "Auto-reload",
  subscription_charge: "Pembayaran langganan",
  subscription_renewal: "Perpanjangan langganan",
};

export function transactionTypeLabel(type: string): string {
  return TRANSACTION_LABEL[type] ?? type;
}

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export const PM_STATUS_META: Record<PaymentMethodStatus, { label: string; tone: Tone }> = {
  pending_activation: { label: "Menunggu aktivasi", tone: "warning" },
  active: { label: "Aktif", tone: "success" },
  failed: { label: "Gagal", tone: "danger" },
  expired: { label: "Kedaluwarsa", tone: "neutral" },
};

export const SUBSCRIPTION_STATUS_META: Record<SubscriptionStatus, { label: string; tone: Tone }> = {
  aktif: { label: "Aktif", tone: "success" },
  menunggak: { label: "Menunggak", tone: "danger" },
  dibatalkan: { label: "Dibatalkan", tone: "neutral" },
};

export function autoReloadReasonLabel(reason: AutoReloadSettings["reason"]): string | null {
  switch (reason) {
    case "disabled":
      return "Auto-reload nonaktif.";
    case "no_payment_method":
      return "Belum ada metode bayar default yang aktif — auto-reload tidak akan berjalan.";
    case "no_threshold":
      return "Ambang batas belum diisi — auto-reload tidak akan berjalan.";
    default:
      return null;
  }
}

// ---------- Paket ----------

/** Toggle tahunan hanya ditampilkan bila minimal satu tier punya harga tahunan. */
export function hasAnnualOption(plans: readonly Plan[] | undefined): boolean {
  return Boolean(plans?.some((p) => p.annual.available));
}

/** Harga yang ditampilkan untuk periode terpilih. `null` = tier ini tidak
 * tersedia di periode tsb (tombol pilih dinonaktifkan). */
export function planPrice(
  plan: Plan,
  period: BillingPeriod
): { fee: number; suffix: string; monthlyEquivalent?: number; discountPercent?: number } | null {
  if (period === "monthly") return { fee: plan.monthly_fee, suffix: "/bulan" };
  if (!plan.annual.available || plan.annual.fee === null) return null;
  return {
    fee: plan.annual.fee,
    suffix: "/tahun",
    monthlyEquivalent: plan.annual.monthly_equivalent,
    discountPercent: plan.annual.discount_percent ?? undefined,
  };
}

// ---------- Banner status ----------

export type BannerCta = "retry_renewal" | "choose_plan" | "payment_methods" | "topup";

export interface BillingBanner {
  tone: "danger" | "warning" | "info";
  title: string;
  message: string;
  ctas: BannerCta[];
}

/** Pemetaan `GET /billing/status` -> banner. `null` bila tidak perlu banner. */
export function bannerForStatus(status: BillingStatus | undefined): BillingBanner | null {
  if (!status || status.billing_bypass) return null;
  if (status.access === "none") {
    if (status.block_reason === "subscription_past_due") {
      return {
        tone: "danger",
        title: "Langganan menunggak",
        message:
          "Akses ke seluruh modul dihentikan sampai tagihan perpanjangan dibayar. " +
          "Halaman Pembayaran dan kwitansi tetap bisa dibuka.",
        ctas: ["retry_renewal", "payment_methods"],
      };
    }
    return {
      tone: "warning",
      title: "Belum berlangganan",
      message: "Pilih paket untuk mulai memakai modul AEOS.",
      ctas: ["choose_plan"],
    };
  }
  if (status.access === "metered_blocked") {
    const lastError = status.auto_reload.last_error;
    if (status.block_reason === "auto_reload_failed") {
      return {
        tone: "warning",
        title: "Auto-reload gagal — fitur berbayar diblokir",
        message:
          `Saldo habis dan pengisian otomatis gagal${lastError ? ` (${lastError})` : ""}. ` +
          "Data tetap bisa dilihat, tetapi aksi bertarif (mis. AI) ditahan sampai saldo terisi.",
        ctas: ["payment_methods", "topup"],
      };
    }
    return {
      tone: "warning",
      title: "Saldo habis — fitur berbayar diblokir",
      message:
        "Data tetap bisa dilihat, tetapi aksi bertarif (mis. AI) ditahan sampai saldo ditambah." +
        (status.has_default_payment_method ? "" : " Tambahkan metode bayar agar auto-reload bisa berjalan."),
      ctas: status.has_default_payment_method ? ["topup"] : ["topup", "payment_methods"],
    };
  }
  const sub = status.subscription;
  if (sub && sub.status === "aktif" && sub.auto_renew && status.renewal_enforcement && !status.has_default_payment_method) {
    return {
      tone: "info",
      title: "Perpanjangan otomatis butuh metode bayar",
      message: "Tambahkan kartu atau GoPay agar langganan diperpanjang otomatis sebelum jatuh tempo.",
      ctas: ["payment_methods"],
    };
  }
  return null;
}

/** Perpanjangan bisa dibayar sekarang bila menunggak atau H-7 jatuh tempo
 * (cermin aturan 409 di `renewal.retry_renewal`). */
export function canRetryRenewal(sub: SubscriptionInfo | null | undefined, today: Date = new Date()): boolean {
  if (!sub) return false;
  if (sub.status === "menunggak") return true;
  if (sub.status !== "aktif" || !sub.current_period_end) return false;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(sub.current_period_end);
  if (!m) return false;
  const end = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const days = Math.round((end.getTime() - start.getTime()) / 86_400_000);
  return days <= 7;
}

export type RenewalOutcome =
  | { kind: "redirect"; url: string }
  | { kind: "success" | "pending" | "error"; message: string };

export function renewalOutcome(res: RetryRenewalResult): RenewalOutcome {
  if (res.checkout_url) return { kind: "redirect", url: res.checkout_url };
  switch (res.status) {
    case "succeeded":
      return { kind: "success", message: "Pembayaran perpanjangan berhasil. Akses dipulihkan." };
    case "processing":
    case "unknown":
      return { kind: "pending", message: "Pembayaran sedang diproses gateway. Status akan diperbarui otomatis." };
    case "invoice_created":
      return { kind: "pending", message: "Tagihan perpanjangan dibuat. Selesaikan pembayaran dari tautan tagihan." };
    default:
      return {
        kind: "error",
        message: `Pembayaran gagal${res.failure_code ? ` (${res.failure_code})` : ""}. Periksa metode bayar lalu coba lagi.`,
      };
  }
}

// ---------- Metode bayar ----------

/** 409 yang bisa diatasi dengan `force=true` (auto-reload dimatikan). 409
 * "charge sedang berjalan" TIDAK bisa dipaksa. */
export function isForceableDeleteConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && /auto-reload/i.test(error.message);
}

export const SANDBOX_CARD_TOKENS = [
  { value: "sbx-tok-ok", label: "Sukses langsung (VISA •••• 4242)" },
  { value: "sbx-tok-3ds", label: "Perlu otorisasi 3DS (redirect)" },
  { value: "sbx-tok-fail", label: "Gagal didaftarkan" },
  { value: "sbx-tok-decline", label: "Aktif, tapi charge ditolak" },
] as const;

/** Baca parameter kembali dari redirect aktivasi: `/billing?pm={id}&result=...`
 * (backend) atau `?pm_ref={reference_id}` (halaman sandbox tanpa id). */
export function parsePmReturn(search: string): { pmId: string | null; pmRef: string | null; result: "success" | "failed" | null } | null {
  const params = new URLSearchParams(search);
  const pmId = params.get("pm");
  const pmRef = params.get("pm_ref");
  if (!pmId && !pmRef) return null;
  const r = params.get("result");
  return { pmId, pmRef, result: r === "success" || r === "failed" ? r : null };
}

/** reference_id backend = `aeos-pm-{tenant}-{pm_id.hex[:12]}` -> cari metode
 * yang id-nya (tanpa strip) diawali sufiks itu. */
export function pmIdFromReference(referenceId: string, methods: readonly PaymentMethod[]): string | null {
  const suffix = referenceId.split("-").pop()?.toLowerCase();
  if (!suffix || suffix.length < 8) return null;
  const hit = methods.find((m) => m.id.replace(/-/g, "").toLowerCase().startsWith(suffix));
  return hit?.id ?? null;
}

export type PollState = "active" | "failed" | "pending" | "missing";

export function pmPollState(methods: readonly PaymentMethod[] | undefined, pmId: string | null): PollState {
  if (!methods || !pmId) return "missing";
  const pm = methods.find((m) => m.id === pmId);
  if (!pm) return "missing";
  if (pm.status === "active") return "active";
  if (pm.status === "failed" || pm.status === "expired") return "failed";
  return "pending";
}

// ---------- Profil penagihan ----------

/** NPWP opsional; bila diisi harus 15/16 digit (titik/strip boleh). */
export function validateNpwp(raw: string): string | null {
  const s = raw.trim();
  if (!s) return null;
  if (!/^[\d.\-\s]+$/.test(s)) return "NPWP hanya boleh berisi angka, titik, atau strip.";
  const digits = s.replace(/\D/g, "");
  if (digits.length !== 15 && digits.length !== 16) return "NPWP harus 15 atau 16 digit.";
  return null;
}

export function validateEmail(raw: string): string | null {
  const s = raw.trim();
  if (!s) return null;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s) ? null : "Format email tidak valid.";
}

/** sessionStorage: id metode yang sedang menunggu redirect otorisasi. Dipakai
 * halaman sandbox (yang hanya tahu reference_id) untuk kembali ke `?pm={id}`. */
export const PENDING_PM_KEY = "aeos_pending_pm";
