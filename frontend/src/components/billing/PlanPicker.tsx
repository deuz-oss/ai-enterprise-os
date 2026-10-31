import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, formatDate, formatRupiah } from "../../api/client";
import {
  canRetryRenewal,
  hasAnnualOption,
  PERIOD_LABEL,
  planPrice,
  SUBSCRIPTION_STATUS_META,
  TIER_INFO,
  tierLabel,
  type BillingPeriod,
  type BillingStatus,
  type Plan,
  type SubscriptionInfo,
  type Tier,
} from "../../lib/billing";
import { Badge, Button, PillTabs, QueryState } from "../ui";
import { useInvalidateBilling, useRetryRenewal } from "./hooks";

/** Ringkasan langganan aktif: status, periode, perpanjangan otomatis, bayar sekarang. */
function SubscriptionSummary({ sub }: { sub: SubscriptionInfo }) {
  const invalidate = useInvalidateBilling();
  const retry = useRetryRenewal();
  const toggle = useMutation({
    mutationFn: (autoRenew: boolean) => api.patch<SubscriptionInfo>("/billing/subscription", { auto_renew: autoRenew }),
    onSuccess: (res) => {
      toast.success(res.auto_renew ? "Perpanjangan otomatis diaktifkan" : "Perpanjangan otomatis dimatikan");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Gagal mengubah perpanjangan otomatis"),
  });
  const meta = SUBSCRIPTION_STATUS_META[sub.status];

  return (
    <div className="card flex flex-wrap items-center gap-x-6 gap-y-3">
      <div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Paket saat ini
        </p>
        <p className="flex items-center gap-2 text-base font-semibold" style={{ color: "var(--text)" }}>
          {tierLabel(sub.tier)} · {PERIOD_LABEL[sub.billing_period]}
          <Badge tone={meta?.tone ?? "neutral"}>{meta?.label ?? sub.status}</Badge>
        </p>
      </div>
      <div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Biaya per periode
        </p>
        <p className="text-sm font-medium tabular-nums" style={{ color: "var(--text)" }}>
          {formatRupiah(sub.period_fee)}
          {sub.discount_percent > 0 && (
            <span className="ml-1 text-xs" style={{ color: "var(--text-muted)" }}>
              (diskon {sub.discount_percent}%)
            </span>
          )}
        </p>
      </div>
      <div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Berakhir
        </p>
        <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
          {formatDate(sub.current_period_end)}
        </p>
      </div>
      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--text)" }}>
        <input
          type="checkbox"
          className="h-4 w-4"
          checked={sub.auto_renew}
          disabled={toggle.isPending}
          onChange={(e) => toggle.mutate(e.target.checked)}
        />
        Perpanjang otomatis
      </label>
      {canRetryRenewal(sub) && (
        <Button
          className="ml-auto"
          variant={sub.status === "menunggak" ? "danger" : "secondary"}
          loading={retry.isPending}
          onClick={() => retry.mutate(undefined)}
        >
          {sub.status === "menunggak" ? "Bayar tunggakan sekarang" : "Perpanjang sekarang"}
        </Button>
      )}
    </div>
  );
}

export function PlanPicker({ status }: { status: BillingStatus | undefined }) {
  const [period, setPeriod] = useState<BillingPeriod>("monthly");
  const plans = useQuery({
    queryKey: ["billing-plans"],
    queryFn: () => api.get<Plan[]>("/billing/plans"),
    staleTime: 5 * 60_000,
  });
  const subscribe = useMutation({
    mutationFn: (body: { tier: Tier; billing_period: BillingPeriod }) =>
      api.post<{ checkout_url: string | null }>("/billing/subscribe", body),
    onSuccess: (res) => {
      if (res.checkout_url) window.location.href = res.checkout_url;
      else toast.info("Tagihan langganan dibuat.");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Gagal membuat langganan"),
  });

  const showAnnual = hasAnnualOption(plans.data);
  // Bila diskon tahunan dicabut saat halaman terbuka, kembali ke bulanan.
  const effectivePeriod: BillingPeriod = showAnnual ? period : "monthly";
  const sub = status?.subscription ?? null;

  return (
    <div className="space-y-3">
      {sub && <SubscriptionSummary sub={sub} />}

      {showAnnual && (
        <div className="flex items-center gap-3">
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>
            Periode tagihan:
          </span>
          <PillTabs
            tabs={[
              { key: "monthly", label: PERIOD_LABEL.monthly },
              { key: "annual", label: PERIOD_LABEL.annual },
            ]}
            value={effectivePeriod}
            onChange={(k) => setPeriod(k as BillingPeriod)}
          />
        </div>
      )}

      <QueryState query={plans} isEmpty={plans.data?.length === 0}>
        <div className="grid gap-3 sm:grid-cols-3">
          {plans.data?.map((p) => {
            const price = planPrice(p, effectivePeriod);
            const info = TIER_INFO[p.tier];
            const isCurrent = sub?.tier === p.tier && sub.status !== "dibatalkan";
            return (
              <div key={p.tier} className="card flex flex-col gap-2">
                <p className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--text)" }}>
                  {info?.label ?? p.tier}
                  {isCurrent && <Badge tone="info">Paket aktif</Badge>}
                  {price?.discountPercent ? <Badge tone="success">Hemat {price.discountPercent}%</Badge> : null}
                </p>
                {price ? (
                  <p className="text-xl font-bold tabular-nums" style={{ color: "var(--text)" }}>
                    {formatRupiah(price.fee)}
                    <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
                      {price.suffix}
                    </span>
                  </p>
                ) : (
                  <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                    Belum tersedia untuk periode ini.
                  </p>
                )}
                {price?.monthlyEquivalent !== undefined && (
                  <p className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
                    setara {formatRupiah(price.monthlyEquivalent)}/bulan
                  </p>
                )}
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Jatah pemakaian {formatRupiah(p.included_budget)}/bulan. {info?.blurb}
                </p>
                <Button
                  className="mt-auto w-full"
                  variant={isCurrent ? "secondary" : "primary"}
                  disabled={!price || subscribe.isPending}
                  loading={subscribe.isPending && subscribe.variables?.tier === p.tier}
                  onClick={() => subscribe.mutate({ tier: p.tier, billing_period: effectivePeriod })}
                >
                  Pilih {info?.label ?? p.tier}
                </Button>
              </div>
            );
          })}
        </div>
      </QueryState>
    </div>
  );
}
