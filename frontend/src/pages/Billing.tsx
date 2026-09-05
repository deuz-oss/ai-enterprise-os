import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CreditCard, Info } from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { CalloutBlock, PageHeader } from "../components/workspace";

interface BalanceSummary {
  cycle_remaining: number;
  cycle_included: number;
  credit_balance: number;
  state: "normal" | "warning" | "empty";
}

interface Transaction {
  id: string;
  type: string;
  amount: number;
  ref_event: string;
  balance_after: number;
  created_at: string;
}

const TIERS: { key: string; label: string; fee: number; blurb: string }[] = [
  { key: "tier1", label: "Tier 1", fee: 500_000, blurb: "Untuk tenant baru — pemakaian ringan." },
  { key: "tier2", label: "Tier 2", fee: 2_000_000, blurb: "Jatah bulanan lebih besar untuk tim aktif." },
  { key: "tier3", label: "Tier 3", fee: 5_000_000, blurb: "Untuk operasi skala penuh, semua fitur." },
];

export default function Billing() {
  const [tab, setTab] = useState<"tier" | "topup" | "history">("tier");
  const [topupAmount, setTopupAmount] = useState("100000");
  const [error, setError] = useState<string | null>(null);

  const balance = useQuery({
    queryKey: ["billing-balance"],
    queryFn: () => api.get<BalanceSummary>("/billing/balance-summary"),
    retry: false,
  });
  const transactions = useQuery({
    queryKey: ["billing-transactions"],
    queryFn: () => api.get<Transaction[]>("/billing/transactions"),
    enabled: tab === "history",
  });

  const subscribe = useMutation({
    mutationFn: (tier: string) => api.post<{ checkout_url: string | null }>("/billing/subscribe", { tier }),
    onSuccess: (res) => {
      setError(null);
      if (res.checkout_url) window.location.href = res.checkout_url;
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal membuat langganan"),
  });
  const topup = useMutation({
    mutationFn: (amount: number) => api.post<{ checkout_url: string | null }>("/billing/topup", { amount }),
    onSuccess: (res) => {
      setError(null);
      if (res.checkout_url) window.location.href = res.checkout_url;
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal membuat top up"),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        icon={CreditCard}
        title="Pembayaran"
        subtitle="Langganan, top up saldo, dan riwayat transaksi kredit."
      />

      {balance.data && (
        <div className="card flex flex-wrap items-center gap-6">
          <div>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Sisa jatah bulan ini
            </p>
            <p className="text-lg font-semibold" style={{ color: "var(--text)" }}>
              {formatRupiah(balance.data.cycle_remaining)}
              <span className="text-sm font-normal" style={{ color: "var(--text-muted)" }}>
                {" "}
                / {formatRupiah(balance.data.cycle_included)}
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Saldo top up
            </p>
            <p className="text-lg font-semibold" style={{ color: "var(--text)" }}>
              {formatRupiah(balance.data.credit_balance)}
            </p>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        {(
          [
            ["tier", "Pilih Paket"],
            ["topup", "Top Up"],
            ["history", "Riwayat"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className="rounded px-3 py-1.5 text-sm transition-colors"
            style={{
              border: "1px solid var(--border)",
              backgroundColor: tab === k ? "var(--hover)" : "transparent",
              color: tab === k ? "var(--text)" : "var(--text-muted)",
              fontWeight: tab === k ? 500 : 400,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <CalloutBlock tone="danger">{error}</CalloutBlock>}

      {tab === "tier" && (
        <div className="grid gap-3 sm:grid-cols-3">
          {TIERS.map((t) => (
            <div key={t.key} className="card space-y-2">
              <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>
                {t.label}
              </p>
              <p className="text-xl font-bold" style={{ color: "var(--text)" }}>
                {formatRupiah(t.fee)}
                <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
                  /bulan
                </span>
              </p>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {t.blurb}
              </p>
              <button
                className="btn w-full"
                disabled={subscribe.isPending}
                onClick={() => subscribe.mutate(t.key)}
              >
                Pilih {t.label}
              </button>
            </div>
          ))}
        </div>
      )}

      {tab === "topup" && (
        <div className="card max-w-sm space-y-3">
          <label className="block text-sm font-medium" style={{ color: "var(--text)" }}>
            Jumlah top up (Rp)
          </label>
          <input
            className="input w-full"
            type="number"
            min={10000}
            step={10000}
            value={topupAmount}
            onChange={(e) => setTopupAmount(e.target.value)}
          />
          <button
            className="btn w-full"
            disabled={topup.isPending || Number(topupAmount) <= 0}
            onClick={() => topup.mutate(Number(topupAmount))}
          >
            Top Up Sekarang
          </button>
          <CalloutBlock icon={Info} tone="info">
            Auto-reload saldo (kartu/GoPay tersimpan) belum tersedia — top up saat ini manual
            per transaksi. Pembayaran QRIS/Virtual Account juga hanya mendukung top up manual.
          </CalloutBlock>
        </div>
      )}

      {tab === "history" && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left" style={{ color: "var(--text-muted)" }}>
                <th className="th">Waktu</th>
                <th className="th">Kejadian</th>
                <th className="th text-right">Jumlah</th>
                <th className="th text-right">Sisa Setelah</th>
              </tr>
            </thead>
            <tbody>
              {(transactions.data ?? []).map((t) => (
                <tr key={t.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="td">{new Date(t.created_at).toLocaleString("id-ID")}</td>
                  <td className="td">{t.ref_event}</td>
                  <td
                    className="td text-right"
                    style={{ color: t.amount < 0 ? "var(--text)" : "#047857" }}
                  >
                    {t.amount >= 0 ? "+" : ""}
                    {formatRupiah(t.amount)}
                  </td>
                  <td className="td text-right">{formatRupiah(t.balance_after)}</td>
                </tr>
              ))}
              {(transactions.data ?? []).length === 0 && (
                <tr>
                  <td className="td text-center" colSpan={4} style={{ color: "var(--text-muted)" }}>
                    Belum ada transaksi.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
