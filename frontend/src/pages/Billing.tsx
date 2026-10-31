import { useEffect, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CreditCard, Zap } from "lucide-react";
import { toast } from "sonner";
import { api, formatRupiah } from "../api/client";
import { CalloutBlock, PageHeader } from "../components/workspace";
import { Button, PillTabs } from "../components/ui";
import { AutoReloadSettingsCard } from "../components/billing/AutoReloadSettingsCard";
import { BillingProfileForm } from "../components/billing/BillingProfileForm";
import { ReceiptsTable, TransactionsTable } from "../components/billing/BillingHistory";
import { BillingStatusBanner, type BillingTab } from "../components/billing/BillingStatusBanner";
import { PaymentMethodsSection } from "../components/billing/PaymentMethodsSection";
import { PlanPicker } from "../components/billing/PlanPicker";
import { useBillingStatus, useInvalidateBilling } from "../components/billing/hooks";
import type { BalanceSummary } from "../lib/billing";

const TABS: BillingTab[] = ["tier", "topup", "methods", "history"];

function initialTab(state: unknown, search: URLSearchParams): BillingTab {
  // Kembali dari aktivasi metode bayar -> langsung ke tab Metode Bayar.
  if (search.get("pm") || search.get("pm_ref")) return "methods";
  const fromQuery = search.get("tab");
  if (fromQuery && (TABS as string[]).includes(fromQuery)) return fromQuery as BillingTab;
  // Widget saldo di topbar mengarahkan ke sini dengan state.tab="topup".
  const fromState = (state as { tab?: string } | null)?.tab;
  if (fromState && (TABS as string[]).includes(fromState)) return fromState as BillingTab;
  return "tier";
}

function BalanceCard({ balance }: { balance: BalanceSummary }) {
  const totalRemaining = balance.cycle_remaining + balance.credit_balance;
  const pct =
    balance.cycle_included > 0 ? Math.max(0, Math.round((totalRemaining / balance.cycle_included) * 100)) : null;
  // Kartu berwarna sesuai state, sama seperti indikator topbar (Layout.tsx).
  const colorClass = balance.state === "empty" ? "p-red" : balance.state === "warning" ? "p-orange" : "p-green";
  return (
    <div className={`card flex flex-wrap items-center gap-6 border ${colorClass}`}>
      <div className="flex items-center gap-3">
        <Zap className="h-8 w-8 shrink-0" aria-hidden="true" />
        <div>
          <p className="text-xs font-medium">Saldo Tersedia</p>
          <p className="text-2xl font-bold tabular-nums">{formatRupiah(totalRemaining)}</p>
          {pct !== null && <p className="text-xs font-medium">{pct}% dari kuota bulanan</p>}
        </div>
      </div>
      <div className="ml-auto flex flex-wrap gap-6 border-l pl-6" style={{ borderColor: "currentColor" }}>
        <div>
          <p className="text-xs font-medium">Sisa jatah bulan ini</p>
          <p className="text-sm font-semibold tabular-nums">
            {formatRupiah(balance.cycle_remaining)}
            <span className="font-normal"> / {formatRupiah(balance.cycle_included)}</span>
          </p>
        </div>
        <div>
          <p className="text-xs font-medium">Saldo top up</p>
          <p className="text-sm font-semibold tabular-nums">{formatRupiah(balance.credit_balance)}</p>
        </div>
      </div>
    </div>
  );
}

function TopupCard() {
  const [amount, setAmount] = useState("100000");
  const topup = useMutation({
    mutationFn: (value: number) => api.post<{ checkout_url: string | null }>("/billing/topup", { amount: value }),
    onSuccess: (res) => {
      if (res.checkout_url) window.location.href = res.checkout_url;
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Gagal membuat top up"),
  });
  return (
    <div className="card max-w-md space-y-3">
      <label htmlFor="topup_amount" className="block text-sm font-medium" style={{ color: "var(--text)" }}>
        Jumlah top up (Rp)
      </label>
      <input
        id="topup_amount"
        className="input w-full"
        type="number"
        min={10000}
        step={10000}
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />
      <Button
        className="w-full"
        loading={topup.isPending}
        disabled={Number(amount) <= 0}
        onClick={() => topup.mutate(Number(amount))}
      >
        Top Up Sekarang
      </Button>
    </div>
  );
}

export default function Billing() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState<BillingTab>(() => initialTab(location.state, searchParams));
  const [historyView, setHistoryView] = useState<"transactions" | "receipts">("transactions");
  const invalidate = useInvalidateBilling();

  const status = useBillingStatus();
  // Endpoint saldo/top up/riwayat/auto-reload ber-guard langganan aktif: saat
  // menunggak atau belum berlangganan jangan dipanggil (pasti 403).
  const locked = status.data?.access === "none";
  const balance = useQuery({
    queryKey: ["billing-balance"],
    queryFn: () => api.get<BalanceSummary>("/billing/balance-summary"),
    enabled: status.isSuccess && !locked,
    retry: false,
  });

  // Kembali dari halaman checkout (invoice) -> segarkan status sekali.
  const checkoutHandled = useRef(false);
  useEffect(() => {
    const checkout = searchParams.get("checkout");
    if (!checkout || checkoutHandled.current) return;
    checkoutHandled.current = true; // StrictMode menjalankan efek dua kali di dev
    if (checkout === "success") toast.success("Pembayaran diterima. Status akan diperbarui sebentar lagi.");
    else toast.error("Pembayaran tidak diselesaikan.");
    invalidate();
    const next = new URLSearchParams(searchParams);
    next.delete("checkout");
    setSearchParams(next, { replace: true });
    // Sengaja hanya sekali saat halaman dibuka.
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={CreditCard}
        title="Pembayaran"
        subtitle="Langganan, metode bayar, top up saldo, dan kwitansi."
      />

      <BillingStatusBanner status={status.data} onNavigate={setTab} />

      {balance.data && <BalanceCard balance={balance.data} />}

      <PillTabs
        tabs={[
          { key: "tier", label: "Paket" },
          { key: "topup", label: "Top Up & Auto-Reload" },
          { key: "methods", label: "Metode Bayar & Profil" },
          { key: "history", label: "Riwayat & Kwitansi" },
        ]}
        value={tab}
        onChange={(k) => setTab(k as BillingTab)}
      />

      {tab === "tier" && <PlanPicker status={status.data} />}

      {tab === "topup" &&
        (locked ? (
          <CalloutBlock tone="warning">
            Top up dan auto-reload hanya tersedia untuk langganan aktif. Selesaikan pembayaran langganan terlebih
            dahulu di tab Paket.
          </CalloutBlock>
        ) : (
          <div className="flex flex-wrap items-start gap-4">
            <TopupCard />
            <AutoReloadSettingsCard />
          </div>
        ))}

      {tab === "methods" && (
        <div className="space-y-4">
          <PaymentMethodsSection />
          <BillingProfileForm />
        </div>
      )}

      {tab === "history" && (
        <div className="space-y-3">
          {!locked && (
            <PillTabs
              tabs={[
                { key: "transactions", label: "Transaksi saldo" },
                { key: "receipts", label: "Kwitansi" },
              ]}
              value={historyView}
              onChange={(k) => setHistoryView(k as typeof historyView)}
            />
          )}
          {locked || historyView === "receipts" ? (
            <>
              {locked && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Riwayat transaksi saldo tersedia kembali setelah langganan aktif; kwitansi tetap bisa diunduh.
                </p>
              )}
              <ReceiptsTable />
            </>
          ) : (
            <TransactionsTable />
          )}
        </div>
      )}
    </div>
  );
}
