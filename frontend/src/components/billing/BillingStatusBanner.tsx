import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import { formatDate, formatDateTime } from "../../api/client";
import { bannerForStatus, type BannerCta, type BillingStatus } from "../../lib/billing";
import { Button } from "../ui";
import { useRetryRenewal } from "./hooks";

export type BillingTab = "tier" | "topup" | "methods" | "history";

const CTA_LABEL: Record<BannerCta, string> = {
  retry_renewal: "Bayar sekarang",
  choose_plan: "Pilih paket",
  payment_methods: "Cek metode bayar",
  topup: "Top up saldo",
};

const TONE_CLASS: Record<"danger" | "warning" | "info", string> = {
  danger: "bg-red-50 border-red-300 text-red-700 dark:bg-red-500/10 dark:border-red-500/40 dark:text-red-300",
  warning:
    "bg-amber-50 border-amber-300 text-amber-700 dark:bg-amber-500/10 dark:border-amber-500/40 dark:text-amber-300",
  info: "bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-300",
};

/** Banner gagal bayar dari `GET /billing/status` (menunggak / metered_blocked /
 * belum berlangganan). Logika pemetaan ada di `lib/billing.ts::bannerForStatus`. */
export function BillingStatusBanner({
  status,
  onNavigate,
}: {
  status: BillingStatus | undefined;
  onNavigate: (tab: BillingTab) => void;
}) {
  const retry = useRetryRenewal();
  const banner = bannerForStatus(status);
  if (!banner) return null;
  const Icon = banner.tone === "danger" ? AlertOctagon : banner.tone === "warning" ? AlertTriangle : Info;
  const pastDueSince = status?.subscription?.past_due_since;
  const periodEnd = status?.subscription?.current_period_end;

  function runCta(cta: BannerCta) {
    if (cta === "retry_renewal") retry.mutate(undefined);
    else if (cta === "choose_plan") onNavigate("tier");
    else if (cta === "payment_methods") onNavigate("methods");
    else onNavigate("topup");
  }

  return (
    <div
      role={banner.tone === "info" ? "status" : "alert"}
      className={`flex flex-wrap items-start gap-3 rounded-lg border px-4 py-3 ${TONE_CLASS[banner.tone]}`}
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-semibold">{banner.title}</p>
        <p className="text-sm" style={{ color: "var(--text)" }}>
          {banner.message}
        </p>
        {status?.block_reason === "subscription_past_due" && (pastDueSince || periodEnd) && (
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {pastDueSince ? `Menunggak sejak ${formatDateTime(pastDueSince)}` : null}
            {pastDueSince && periodEnd ? " · " : null}
            {periodEnd ? `Masa langganan berakhir ${formatDate(periodEnd)}` : null}
          </p>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {banner.ctas.map((cta, i) => (
          <Button
            key={cta}
            size="sm"
            variant={i === 0 ? (banner.tone === "danger" ? "danger" : "primary") : "secondary"}
            loading={cta === "retry_renewal" && retry.isPending}
            onClick={() => runCta(cta)}
          >
            {CTA_LABEL[cta]}
          </Button>
        ))}
      </div>
    </div>
  );
}
