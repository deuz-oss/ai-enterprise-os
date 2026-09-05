import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Clock,
  FileCheck,
  Percent,
  Receipt,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { CalloutBlock, IconBadge, PageHeader, RowFrame, SeeAllLink } from "../components/workspace";

interface Overview {
  finance: {
    revenue_mtd: number;
    outstanding: number;
    overdue: number;
    invoices_total: number;
    faktur_belum: number;
  };
  operations: {
    profit_by_client: { client: string; revenue: number; expense: number; margin: number }[];
  };
  ai_insight: { hint: string };
}

interface InvoiceRow {
  id: string;
  invoice_no: string;
  client_id: string;
  total_due: number;
  status: string;
  due_date: string | null;
  tax_invoice_status: string | null;
  no_seri_faktur: string | null;
  efaktur_nsr: string | null;
}

interface ClientRow {
  id: string;
  name: string;
}

interface AgingRow {
  invoice_id: string;
  invoice_no: string;
  client_name: string;
  total_due: number;
  days_overdue: number;
  bucket: string;
}

interface CashFlowSummary {
  inflow: number;
  outflow: number;
  net: number;
}

interface AuditItem {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
}

interface UserOption {
  id: string;
  full_name: string;
}

const FAKTUR_LABELS: Record<string, { label: string; cls: string }> = {
  belum_buat: { label: "belum dibuat", cls: "pill p-gray" },
  draft: { label: "draft", cls: "pill p-blue" },
  menunggu_approval: { label: "menunggu approval", cls: "pill p-yellow" },
  terkirim_djp: { label: "terkirim DJP", cls: "pill p-indigo" },
  approved: { label: "approved", cls: "pill p-green" },
  ditolak: { label: "ditolak", cls: "pill p-red" },
  dibatalkan: { label: "dibatalkan", cls: "pill p-orange" },
  pengganti: { label: "pengganti", cls: "pill p-violet" },
};

const ACTION_LABELS: Record<string, string> = {
  "invoice.tax_invoice_set": "isi data e-Faktur",
  "invoice.tax_invoice_sent": "kirim e-Faktur ke DJP",
  "invoice.tax_invoice_cancelled": "batalkan e-Faktur",
  "invoice.tax_invoice_replaced": "ganti e-Faktur",
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/[._]/g, " ");
}

function actorName(users: UserOption[] | undefined, userId: string | null): string {
  if (!userId) return "Sistem";
  return users?.find((u) => u.id === userId)?.full_name ?? "Pengguna";
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "baru saja";
  if (min < 60) return `${min} menit lalu`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} jam lalu`;
  return `${Math.floor(hr / 24)} hari lalu`;
}

export default function RevenueCloudOverview() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
  });

  const overview = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });
  const invoices = useQuery({
    queryKey: ["invoices"],
    queryFn: () => api.get<InvoiceRow[]>("/finance/invoices"),
  });
  const clients = useQuery({ queryKey: ["clients"], queryFn: () => api.get<ClientRow[]>("/clients") });
  const aging = useQuery({
    queryKey: ["aging"],
    queryFn: () => api.get<AgingRow[]>("/finance/invoices/aging"),
  });
  const cashflowSummary = useQuery({
    queryKey: ["cashflow-summary", `${year}-${month}`],
    queryFn: () => api.get<CashFlowSummary>(`/finance/cashflow/summary?year=${year}&month=${month}`),
  });
  const users = useQuery({
    queryKey: ["users-for-interview"],
    queryFn: () => api.get<UserOption[]>("/auth/users"),
  });

  const canSeeActivity = me.data?.role === "admin" || me.data?.role === "management";
  const canSeeRates = ["admin", "finance", "management"].includes(me.data?.role ?? "");
  const auditInvoice = useQuery({
    queryKey: ["audit-activity-rev", "invoice"],
    queryFn: () => api.get<{ total: number; items: AuditItem[] }>("/audit/logs?entity_type=invoice&limit=5"),
    enabled: canSeeActivity,
    retry: false,
  });
  const activityFeed = useMemo(
    () =>
      [...(auditInvoice.data?.items ?? [])]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 3),
    [auditInvoice.data],
  );

  const clientName = (id: string) => clients.data?.find((c) => c.id === id)?.name ?? "-";

  const profitByClient = overview.data?.operations.profit_by_client ?? [];
  const avgMarginPct = useMemo(() => {
    const totalRevenue = profitByClient.reduce((s, r) => s + r.revenue, 0);
    const totalMargin = profitByClient.reduce((s, r) => s + r.margin, 0);
    return totalRevenue > 0 ? Math.round((totalMargin / totalRevenue) * 100) : 0;
  }, [profitByClient]);
  const topClient = useMemo(() => {
    return profitByClient
      .map((r) => ({ ...r, pct: r.revenue > 0 ? Math.round((r.margin / r.revenue) * 100) : 0 }))
      .sort((a, b) => b.pct - a.pct)[0];
  }, [profitByClient]);
  const marginPillCls = (pct: number) => (pct >= 15 ? "pill p-green" : pct >= 0 ? "pill p-yellow" : "pill p-red");

  const faktorBuilt = (invoices.data ?? []).filter(
    (i) => i.tax_invoice_status && i.tax_invoice_status !== "belum_buat",
  );
  const faktorPending = (invoices.data ?? []).filter(
    (i) => i.tax_invoice_status === "menunggu_approval" || i.tax_invoice_status === "terkirim_djp",
  );
  const invoicesNeedingAction = (invoices.data ?? [])
    .filter((i) => !i.tax_invoice_status || ["belum_buat", "draft", "menunggu_approval", "terkirim_djp"].includes(i.tax_invoice_status))
    .slice(0, 3);
  const recentInvoices = [...(invoices.data ?? [])]
    .sort((a, b) => (b.due_date ?? "").localeCompare(a.due_date ?? ""))
    .slice(0, 4);
  const oldestAging = [...(aging.data ?? [])].sort((a, b) => b.days_overdue - a.days_overdue).slice(0, 3);

  const inflow = cashflowSummary.data?.inflow ?? 0;
  const outflow = cashflowSummary.data?.outflow ?? 0;
  const cashflowMax = Math.max(inflow, outflow, 1);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          icon={Receipt}
          title="Finance"
          subtitle={`${overview.data?.finance.invoices_total ?? 0} invoice · ${faktorBuilt.length} e-Faktur dibuat · 13 kolom DJP, lawan NPWP tervalidasi.`}
        />
        <Link to="/finance" className="btn shrink-0">
          + Buat Invoice
        </Link>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Revenue MTD</span>
            <IconBadge icon={TrendingUp} tone="green" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>
            {formatRupiah(overview.data?.finance.revenue_mtd)}
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Outstanding</span>
            <IconBadge icon={Clock} tone="orange" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>
            {formatRupiah(overview.data?.finance.outstanding)}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
            {overview.data?.finance.overdue ?? 0} overdue
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Profit Margin</span>
            <IconBadge icon={Percent} tone="violet" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>{avgMarginPct}%</p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
            {topClient ? `tertinggi ${topClient.client} ${topClient.pct}%` : "belum ada data"}
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>e-Faktur DJP</span>
            <IconBadge icon={FileCheck} tone="accent" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>{faktorBuilt.length}</p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
            {faktorPending.length} pending
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex items-center lg:col-span-2">
          {overview.data?.ai_insight.hint && (
            <CalloutBlock icon={TrendingUp} tone="info">
              {overview.data.ai_insight.hint}
            </CalloutBlock>
          )}
        </div>

        {/* e-Faktur menunggu DJP */}
        <div className="card space-y-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={Clock} tone="orange" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>e-Faktur Menunggu DJP</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>{invoicesNeedingAction.length} perlu tindakan</p>
            </div>
          </div>
          <div className="space-y-1.5">
            {invoicesNeedingAction.map((i) => {
              const ft = FAKTUR_LABELS[i.tax_invoice_status ?? "belum_buat"] ?? FAKTUR_LABELS.belum_buat;
              return (
                <RowFrame key={i.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium font-mono text-xs" style={{ color: "var(--text)" }}>
                      {i.invoice_no}
                    </span>
                    <span className={`shrink-0 text-[10px] ${ft.cls}`}>{ft.label}</span>
                  </div>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>{clientName(i.client_id)}</p>
                </RowFrame>
              );
            })}
            {invoicesNeedingAction.length === 0 && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Tidak ada e-Faktur menunggu.</p>
            )}
          </div>
          <SeeAllLink to="/finance">Kelola di Finance →</SeeAllLink>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Finance & DJP e-Faktur */}
        <div className="card space-y-2 lg:col-span-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={Receipt} tone="accent" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Finance & DJP e-Faktur</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                13 kolom DJP · lawan NPWP validasi
              </p>
            </div>
          </div>
          <div className="space-y-1.5">
            {recentInvoices.map((i) => {
              const ft = FAKTUR_LABELS[i.tax_invoice_status ?? "belum_buat"] ?? FAKTUR_LABELS.belum_buat;
              return (
                <RowFrame key={i.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-mono text-xs font-medium" style={{ color: "var(--text)" }}>
                      {i.invoice_no}
                    </span>
                    <span className={`shrink-0 text-[10px] ${ft.cls}`}>{ft.label}</span>
                  </div>
                  <div className="mt-0.5 flex items-center justify-between text-xs" style={{ color: "var(--text-muted)" }}>
                    <span>
                      {clientName(i.client_id)}
                      {(i.no_seri_faktur || i.efaktur_nsr) ? ` · NSFP ${i.no_seri_faktur ?? i.efaktur_nsr}` : ""}
                    </span>
                    <span className="shrink-0 font-medium">{formatRupiah(i.total_due)}</span>
                  </div>
                </RowFrame>
              );
            })}
            {recentInvoices.length === 0 && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada invoice.</p>
            )}
          </div>
          <SeeAllLink to="/finance">Lihat semua invoice →</SeeAllLink>
        </div>

        {/* Client Profit Margin */}
        <div className="card space-y-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={TrendingUp} tone="violet" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Client Profit Margin</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>profit-by-client</p>
            </div>
          </div>
          <div className="space-y-1.5">
            {profitByClient.slice(0, 3).map((r) => {
              const pct = r.revenue > 0 ? Math.round((r.margin / r.revenue) * 100) : 0;
              return (
                <div key={r.client} className="flex items-center justify-between text-sm">
                  <span className="truncate font-medium" style={{ color: "var(--text)" }}>{r.client}</span>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>{formatRupiah(r.revenue)}</span>
                    <span className={marginPillCls(pct)}>{pct}%</span>
                  </div>
                </div>
              );
            })}
            {profitByClient.length === 0 && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada data profit klien.</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Cashflow MTD */}
        <div className="card space-y-3">
          <div className="flex items-center gap-2">
            <IconBadge icon={Wallet} tone="accent" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Cashflow</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {now.toLocaleDateString("id-ID", { month: "long", year: "numeric" })}
              </p>
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between text-sm">
              <span style={{ color: "var(--text-muted)" }}>Masuk</span>
              <span className="font-mono font-semibold text-emerald-600">+{formatRupiah(inflow)}</span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full" style={{ backgroundColor: "var(--hover)" }}>
              <div className="h-full rounded-full bg-emerald-500" style={{ width: `${(inflow / cashflowMax) * 100}%` }} />
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between text-sm">
              <span style={{ color: "var(--text-muted)" }}>Keluar</span>
              <span className="font-mono font-semibold" style={{ color: "var(--text)" }}>-{formatRupiah(outflow)}</span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full" style={{ backgroundColor: "var(--hover)" }}>
              <div className="h-full rounded-full" style={{ width: `${(outflow / cashflowMax) * 100}%`, backgroundColor: "var(--accent)" }} />
            </div>
          </div>
        </div>

        {/* Invoice overdue terlama */}
        <div className="card space-y-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={Clock} tone="orange" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Invoice Overdue Terlama</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>{aging.data?.length ?? 0} total</p>
            </div>
          </div>
          <div className="space-y-1.5">
            {oldestAging.map((a) => (
              <RowFrame key={a.invoice_id}>
                <div className="flex items-center justify-between text-sm">
                  <span className="truncate font-medium" style={{ color: "var(--text)" }}>{a.client_name}</span>
                  <span className="shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>{a.days_overdue} hari</span>
                </div>
                <p className="mt-0.5 font-mono text-xs" style={{ color: "var(--text-muted)" }}>{a.invoice_no}</p>
              </RowFrame>
            ))}
            {oldestAging.length === 0 && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>Tidak ada invoice overdue.</p>
            )}
          </div>
          <SeeAllLink to="/finance">Lihat semua →</SeeAllLink>
        </div>

        {/* Aktivitas terbaru */}
        {canSeeActivity && (
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Activity} tone="green" />
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Aktivitas Terbaru</h2>
            </div>
            <div className="space-y-1.5">
              {activityFeed.map((a) => (
                <RowFrame key={a.id}>
                  <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{actionLabel(a.action)}</p>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
                    oleh {actorName(users.data, a.user_id)} · {timeAgo(a.created_at)}
                  </p>
                </RowFrame>
              ))}
              {activityFeed.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada aktivitas.</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Akunting */}
        <div className="card space-y-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={BarChart3} tone="accent" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Akunting</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Jurnal, aset tetap, kas & bank, laporan + AI
              </p>
            </div>
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Bagan akun dinamis, tutup buku per periode, neraca, buku besar, dan asisten AI
            (checklist tutup buku, deteksi anomali, ringkasan eksekutif).
          </p>
          <SeeAllLink to="/accounting">Buka Akunting →</SeeAllLink>
          {canSeeRates && <SeeAllLink to="/rates">Tarif & Rate →</SeeAllLink>}
        </div>
      </div>
    </div>
  );
}
