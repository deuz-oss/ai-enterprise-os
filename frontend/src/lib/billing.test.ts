import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api/client";
import {
  autoReloadReasonLabel,
  bannerForStatus,
  canRetryRenewal,
  hasAnnualOption,
  isForceableDeleteConflict,
  parsePmReturn,
  planPrice,
  pmIdFromReference,
  pmPollState,
  renewalOutcome,
  tierLabel,
  transactionTypeLabel,
  validateEmail,
  validateNpwp,
  type BillingStatus,
  type PaymentMethod,
  type Plan,
  type SubscriptionInfo,
} from "./billing";

const sub = (over: Partial<SubscriptionInfo> = {}): SubscriptionInfo => ({
  id: "s1",
  tier: "tier1",
  status: "aktif",
  billing_period: "monthly",
  period_fee: 500000,
  discount_percent: 0,
  current_period_end: "2026-12-01",
  past_due_since: null,
  auto_renew: true,
  ...over,
});

const status = (over: Partial<BillingStatus> = {}): BillingStatus => ({
  billing_bypass: false,
  subscription: sub(),
  access: "full",
  block_reason: null,
  total_remaining: 100000,
  auto_reload: { enabled: false, failure_count: 0, last_error: null },
  has_default_payment_method: true,
  renewal_enforcement: true,
  ...over,
});

const pm = (over: Partial<PaymentMethod> = {}): PaymentMethod => ({
  id: "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
  type: "card",
  status: "active",
  card_brand: "VISA",
  card_last4: "4242",
  card_exp_month: 12,
  card_exp_year: 2030,
  ewallet_account_masked: null,
  failure_reason: null,
  is_default: true,
  label: "VISA •••• 4242",
  created_at: "2026-10-01T00:00:00Z",
  activated_at: "2026-10-01T00:00:00Z",
  ...over,
});

describe("bannerForStatus", () => {
  it("tanpa data atau billing_bypass -> tanpa banner", () => {
    expect(bannerForStatus(undefined)).toBeNull();
    expect(bannerForStatus(status({ billing_bypass: true, access: "none", block_reason: "no_subscription" }))).toBeNull();
  });

  it("akses penuh + metode default -> tanpa banner", () => {
    expect(bannerForStatus(status())).toBeNull();
  });

  it("menunggak -> danger dengan CTA bayar sekarang", () => {
    const b = bannerForStatus(
      status({ access: "none", block_reason: "subscription_past_due", subscription: sub({ status: "menunggak" }) })
    );
    expect(b?.tone).toBe("danger");
    expect(b?.ctas[0]).toBe("retry_renewal");
    expect(b?.message).toMatch(/dihentikan/);
  });

  it("belum berlangganan -> CTA pilih paket", () => {
    const b = bannerForStatus(status({ access: "none", block_reason: "no_subscription", subscription: null }));
    expect(b?.tone).toBe("warning");
    expect(b?.ctas).toEqual(["choose_plan"]);
  });

  it("metered_blocked auto_reload_failed -> data tetap bisa dilihat, sertakan last_error", () => {
    const b = bannerForStatus(
      status({
        access: "metered_blocked",
        block_reason: "auto_reload_failed",
        auto_reload: { enabled: true, failure_count: 3, last_error: "CARD_DECLINED" },
      })
    );
    expect(b?.ctas).toEqual(["payment_methods", "topup"]);
    expect(b?.message).toContain("CARD_DECLINED");
    expect(b?.message).toMatch(/tetap bisa dilihat/);
  });

  it("saldo habis tanpa metode default -> tambah CTA metode bayar", () => {
    expect(
      bannerForStatus(status({ access: "metered_blocked", block_reason: "balance_exhausted", has_default_payment_method: false }))
        ?.ctas
    ).toEqual(["topup", "payment_methods"]);
    expect(bannerForStatus(status({ access: "metered_blocked", block_reason: "balance_exhausted" }))?.ctas).toEqual([
      "topup",
    ]);
  });

  it("auto_renew aktif tanpa metode default saat enforcement -> info", () => {
    expect(bannerForStatus(status({ has_default_payment_method: false }))?.tone).toBe("info");
    expect(bannerForStatus(status({ has_default_payment_method: false, renewal_enforcement: false }))).toBeNull();
  });
});

describe("canRetryRenewal (cermin 409 backend)", () => {
  const today = new Date(2026, 10, 20); // 20 Nov 2026
  it("menunggak selalu boleh", () => {
    expect(canRetryRenewal(sub({ status: "menunggak", current_period_end: "2027-01-01" }), today)).toBe(true);
  });
  it("aktif: hanya mulai H-7", () => {
    expect(canRetryRenewal(sub({ current_period_end: "2026-11-27" }), today)).toBe(true);
    expect(canRetryRenewal(sub({ current_period_end: "2026-11-28" }), today)).toBe(false);
  });
  it("tanpa langganan / dibatalkan -> tidak", () => {
    expect(canRetryRenewal(null, today)).toBe(false);
    expect(canRetryRenewal(sub({ status: "dibatalkan" }), today)).toBe(false);
  });
});

describe("renewalOutcome", () => {
  const base = { charge_id: null, checkout_url: null, failure_code: null } as const;
  it("checkout_url -> redirect", () => {
    expect(renewalOutcome({ ...base, status: "invoice_created", checkout_url: "/sandbox/billing/x/pay" })).toEqual({
      kind: "redirect",
      url: "/sandbox/billing/x/pay",
    });
  });
  it("status lain dipetakan", () => {
    expect(renewalOutcome({ ...base, status: "succeeded" }).kind).toBe("success");
    expect(renewalOutcome({ ...base, status: "processing" }).kind).toBe("pending");
    expect(renewalOutcome({ ...base, status: "unknown" }).kind).toBe("pending");
    const failed = renewalOutcome({ ...base, status: "failed", failure_code: "CARD_DECLINED" });
    expect(failed.kind).toBe("error");
    expect("message" in failed && failed.message).toContain("CARD_DECLINED");
  });
});

describe("paket", () => {
  const monthlyOnly: Plan = {
    tier: "tier1",
    monthly_fee: 500000,
    included_budget: 500000,
    annual: { available: false, fee: null, discount_percent: null },
  };
  const withAnnual: Plan = {
    tier: "tier2",
    monthly_fee: 2000000,
    included_budget: 2000000,
    annual: { available: true, fee: 20400000, monthly_equivalent: 1700000, discount_percent: 15 },
  };

  it("toggle tahunan hanya bila ada tier annual.available", () => {
    expect(hasAnnualOption(undefined)).toBe(false);
    expect(hasAnnualOption([monthlyOnly])).toBe(false);
    expect(hasAnnualOption([monthlyOnly, withAnnual])).toBe(true);
  });

  it("planPrice per periode", () => {
    expect(planPrice(monthlyOnly, "monthly")).toEqual({ fee: 500000, suffix: "/bulan" });
    expect(planPrice(monthlyOnly, "annual")).toBeNull();
    expect(planPrice(withAnnual, "annual")).toEqual({
      fee: 20400000,
      suffix: "/tahun",
      monthlyEquivalent: 1700000,
      discountPercent: 15,
    });
  });
});

describe("label", () => {
  it("tier & jenis transaksi; nilai tak dikenal dikembalikan apa adanya", () => {
    expect(tierLabel("tier3")).toBe("Tier 3");
    expect(tierLabel("tierX")).toBe("tierX");
    expect(tierLabel(null)).toBe("-");
    expect(transactionTypeLabel("topup_auto_reload")).toBe("Auto-reload");
    expect(transactionTypeLabel("subscription_renewal")).toBe("Perpanjangan langganan");
    expect(transactionTypeLabel("baru")).toBe("baru");
  });
  it("alasan auto-reload", () => {
    expect(autoReloadReasonLabel(null)).toBeNull();
    expect(autoReloadReasonLabel("no_payment_method")).toMatch(/metode bayar/);
    expect(autoReloadReasonLabel("no_threshold")).toMatch(/Ambang/);
  });
});

describe("metode bayar", () => {
  it("hanya 409 auto-reload yang bisa dihapus paksa", () => {
    expect(isForceableDeleteConflict(new ApiError(409, "Metode bayar ini dipakai auto-reload. Tambah ..."))).toBe(true);
    expect(isForceableDeleteConflict(new ApiError(409, "Metode bayar sedang dipakai untuk charge yang berjalan"))).toBe(
      false
    );
    expect(isForceableDeleteConflict(new ApiError(422, "auto-reload"))).toBe(false);
    expect(isForceableDeleteConflict(new Error("auto-reload"))).toBe(false);
  });

  it("parsePmReturn", () => {
    expect(parsePmReturn("?tab=history")).toBeNull();
    expect(parsePmReturn("?pm=abc&result=success")).toEqual({ pmId: "abc", pmRef: null, result: "success" });
    expect(parsePmReturn("?pm_ref=aeos-pm-t-0f1e2d3c4b5a&result=aneh")).toEqual({
      pmId: null,
      pmRef: "aeos-pm-t-0f1e2d3c4b5a",
      result: null,
    });
  });

  it("pmIdFromReference mencocokkan sufiks hex 12 karakter", () => {
    const tenant = "11111111-2222-3333-4444-555555555555";
    const methods = [pm({ id: "aaaaaaaa-0000-0000-0000-000000000000" }), pm()];
    expect(pmIdFromReference(`aeos-pm-${tenant}-0f1e2d3c4b5a`, methods)).toBe(pm().id);
    expect(pmIdFromReference(`aeos-pm-${tenant}-ffffffffffff`, methods)).toBeNull();
    expect(pmIdFromReference("x", methods)).toBeNull();
  });

  it("pmPollState", () => {
    expect(pmPollState(undefined, "x")).toBe("missing");
    expect(pmPollState([pm()], null)).toBe("missing");
    expect(pmPollState([pm({ status: "pending_activation" })], pm().id)).toBe("pending");
    expect(pmPollState([pm()], pm().id)).toBe("active");
    expect(pmPollState([pm({ status: "failed" })], pm().id)).toBe("failed");
    expect(pmPollState([pm({ status: "expired" })], pm().id)).toBe("failed");
  });
});

describe("validasi profil penagihan", () => {
  it("NPWP opsional, 15/16 digit dengan titik/strip", () => {
    expect(validateNpwp("")).toBeNull();
    expect(validateNpwp("01.234.567.8-901.000")).toBeNull(); // 15 digit
    expect(validateNpwp("1234567890123456")).toBeNull(); // 16 digit (NIK)
    expect(validateNpwp("12345")).toMatch(/15 atau 16/);
    expect(validateNpwp("12a45")).toMatch(/angka/);
  });
  it("email opsional", () => {
    expect(validateEmail("")).toBeNull();
    expect(validateEmail("tagihan@pt.co.id")).toBeNull();
    expect(validateEmail("bukan email")).not.toBeNull();
  });
});

describe("ApiError.code dari header X-Error-Code", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubEnv(pathname: string, resp: { status: number; code: string | null; detail: string }) {
    const assign = vi.fn();
    vi.stubGlobal("localStorage", { getItem: () => "tok", setItem: vi.fn(), removeItem: vi.fn() });
    vi.stubGlobal("window", { location: { pathname, search: "", assign, replace: vi.fn() } });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: resp.status,
        statusText: "x",
        headers: { get: (h: string) => (h.toLowerCase() === "x-error-code" ? resp.code : null) },
        json: async () => ({ detail: resp.detail }),
      }))
    );
    return assign;
  }

  it("402 metered_blocked: detail jadi pesan, kode tersedia, tanpa redirect", async () => {
    const assign = stubEnv("/talent-pool", { status: 402, code: "metered_blocked", detail: "Saldo habis." });
    const err = await api.post("/ai/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("metered_blocked");
    expect((err as ApiError).message).toBe("Saldo habis.");
    expect(assign).not.toHaveBeenCalled();
  });

  it("403 subscription_past_due di luar /billing -> arahkan ke /billing", async () => {
    const assign = stubEnv("/finance", { status: 403, code: "subscription_past_due", detail: "Menunggak" });
    await api.get("/finance/x").catch(() => undefined);
    expect(assign).toHaveBeenCalledWith("/billing");
  });

  it("403 subscription_past_due di /billing -> tidak redirect (cegah loop)", async () => {
    const assign = stubEnv("/billing", { status: 403, code: "subscription_past_due", detail: "Menunggak" });
    await api.get("/billing/balance-summary").catch(() => undefined);
    expect(assign).not.toHaveBeenCalled();
  });
});
