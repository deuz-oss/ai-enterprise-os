import { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  FileText,
  Hourglass,
  Info,
  LayoutDashboard,
  type LucideIcon,
  Palmtree,
  Pin,
  PenLine,
  Receipt,
  Sparkles,
  Wallet,
} from "lucide-react";
import { PageHeader, CalloutBlock } from "../components/notion";
import { api, formatRupiah } from "../api/client";

interface Overview {
  leads: {
    total: number;
    won: number;
    by_stage: Record<string, number>;
    funnel: { stage: string; count: number }[];
  };
  clients: number;
  documents: number;
  job_orders: { open: number; filled: number };
  candidates: { total: number; by_status: Record<string, number> };
  people: {
    total_employees: number;
    active_employees: number;
    expiring_contracts_14d: number;
    bpjs_complete: number;
    insurance_complete: number;
  };
  payroll: Record<string, number>;
  finance: {
    revenue_mtd: number;
    outstanding: number;
    overdue: number;
    invoices_total: number;
    faktur_belum: number;
  };
  accounting: { period_closed: number; memorial_unposted: number };
  recruitment_talent: {
    job_orders_by_stage: Record<string, number>;
    interviews_this_week: number;
  };
  operations: {
    active_placements_by_client: { client: string; active_placements: number }[];
    profit_by_client: { client: string; revenue: number; expense: number; margin: number }[];
  };
  ai_insight: { hint: string };
}

interface DigestItem {
  type: string;
  detail: string;
  refs: string[];
}

interface Digest {
  date: string;
  items: DigestItem[];
}

interface ClientRow {
  id: string;
  name: string;
}

interface InvoiceRow {
  id: string;
  invoice_no: string;
  client_id: string;
  total_due: number;
  status: string;
  tax_invoice_status: string | null;
  no_seri_faktur: string | null;
}

const JO_STAGE_LABELS: Record<string, string> = {
  open: "Open",
  screening: "Screening",
  interview_klien: "Interview",
  offering: "Offering",
  filled: "Filled",
  closed: "Closed",
};
const JO_STAGE_ORDER = ["open", "screening", "interview_klien", "offering", "filled", "closed"];
const JO_STAGE_COLORS: Record<string, string> = {
  open: "#7c3aed",
  screening: "#8b5cf6",
  interview_klien: "#d97706",
  offering: "#059669",
  filled: "#0f172a",
  closed: "#94a3b8",
};

const CANDIDATE_STATUS_LABELS: Record<string, string> = {
  baru: "Baru",
  screening: "Screening",
  interview: "Interview",
  offered: "Offered",
  placed: "Placed",
  gagal: "Gagal",
  arsip: "Arsip",
};

const INVOICE_STATUS_PILL: Record<string, string> = {
  draft: "p-gray",
  terkirim: "p-yellow",
  dibayar: "p-green",
};

const FAKTUR_STATUS_LABEL: Record<string, string> = {
  belum_buat: "Faktur belum dibuat",
  draft: "Faktur draft",
  approved: "Faktur approved",
  ditolak: "Faktur ditolak DJP",
  dibatalkan: "Faktur dibatalkan",
  pengganti: "Faktur pengganti",
};

const DIGEST_ICON: Record<string, LucideIcon> = {
  approval_menunggu: PenLine,
  payroll_klien: Wallet,
  sla_job_order: Hourglass,
  kontrak_berakhir: FileText,
  invoice_overdue: Receipt,
  cuti_menunggu: Palmtree,
  pengingat: Pin,
  ringkasan: BarChart3,
};

function pct(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

/** Kartu KPI baris atas ala dashboard.html: label, angka besar, hint, progress bar tipis. */
function KpiCard({
  label,
  value,
  hint,
  barPct,
  barColor,
}: {
  label: string;
  value: string | number;
  hint?: string;
  barPct?: number;
  barColor?: string;
}) {
  return (
    <div className="card">
      <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--n-text-muted)" }}>
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
        {value}
      </p>
      {hint && (
        <p className="mt-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
          {hint}
        </p>
      )}
      {barPct !== undefined && (
        <div className="mt-3 h-1.5 rounded-full" style={{ backgroundColor: "var(--n-hover)" }}>
          <div
            className="h-full rounded-full"
            style={{ width: `${Math.min(Math.max(barPct, 0), 100)}%`, backgroundColor: barColor ?? "var(--accent)" }}
          />
        </div>
      )}
    </div>
  );
}

function SectionCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="card">
      <div className="mb-3">
        <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>
          {title}
        </h2>
        {subtitle && (
          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
            {subtitle}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}

/// Dashboard — ringkasan lintas modul, layout ala docs/design/mockups/dashboard.html
/// (data 100% dari /overview + /chat/digest + /finance/invoices yang sudah ada,
/// tanpa badge harga/SKU komersial — sesuai arahan prioritas trial internal).
export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });
  const { data: digest } = useQuery({
    queryKey: ["chat-digest"],
    queryFn: () => api.get<Digest>("/chat/digest"),
  });
  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const { data: invoices } = useQuery({
    queryKey: ["invoices"],
    queryFn: () => api.get<InvoiceRow[]>("/finance/invoices"),
  });

  if (isLoading || !data)
    return <p className="text-sm" style={{ color: "var(--n-text-muted)" }}>Memuat...</p>;

  const clientName = (id: string) => clients?.find((c) => c.id === id)?.name ?? "—";
  const recentInvoices = [...(invoices ?? [])].reverse().slice(0, 5);

  const revenueShare = pct(data.finance.revenue_mtd, data.finance.revenue_mtd + data.finance.outstanding);

  return (
    <div className="space-y-5">
      <PageHeader icon={LayoutDashboard} title="Dashboard" subtitle="Ringkasan operasional hari ini" />

      {/* Baris KPI */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Headcount Aktif"
          value={data.people.active_employees}
          hint={`dari ${data.people.total_employees} karyawan terdaftar`}
          barPct={pct(data.people.active_employees, data.people.total_employees)}
          barColor="#059669"
        />
        <KpiCard
          label="Job Order Terbuka"
          value={data.job_orders.open}
          hint={`${data.job_orders.filled} filled · ${data.candidates.total} kandidat`}
          barPct={pct(data.job_orders.filled, data.job_orders.open + data.job_orders.filled)}
          barColor="#7c3aed"
        />
        <KpiCard
          label="Revenue MTD"
          value={formatRupiah(data.finance.revenue_mtd)}
          hint={`${data.finance.invoices_total} invoice tercatat`}
          barPct={revenueShare}
          barColor="#d97706"
        />
        <KpiCard
          label="Outstanding & Faktur"
          value={formatRupiah(data.finance.outstanding)}
          hint={`${data.finance.overdue} overdue · ${data.finance.faktur_belum} faktur belum dibuat`}
          barPct={pct(data.finance.overdue, Math.max(data.finance.invoices_total, 1))}
          barColor="#dc2626"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Kolom kiri */}
        <div className="space-y-5 lg:col-span-2">
          <SectionCard title="Recruitment & AI Matching" subtitle="Progres tahap job order & status kandidat">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium" style={{ color: "var(--n-text)" }}>
                Tahap Job Order
              </span>
              <span style={{ color: "var(--n-text-muted)" }}>
                {data.recruitment_talent.interviews_this_week} interview minggu ini
              </span>
            </div>
            <div className="mt-2 flex h-2 overflow-hidden rounded-full" style={{ backgroundColor: "var(--n-hover)" }}>
              {JO_STAGE_ORDER.map((stage) => {
                const count = data.recruitment_talent.job_orders_by_stage[stage] ?? 0;
                if (!count) return null;
                return (
                  <div
                    key={stage}
                    style={{ flexGrow: count, backgroundColor: JO_STAGE_COLORS[stage] }}
                  />
                );
              })}
            </div>
            <div className="mt-1.5 flex flex-wrap justify-between gap-x-3 text-xs" style={{ color: "var(--n-text-muted)" }}>
              {JO_STAGE_ORDER.map((stage) => (
                <span key={stage}>
                  {data.recruitment_talent.job_orders_by_stage[stage] ?? 0} {JO_STAGE_LABELS[stage]}
                </span>
              ))}
            </div>

            <div className="mt-4 border-t pt-3" style={{ borderColor: "var(--n-border)" }}>
              <p className="mb-2 text-xs font-medium" style={{ color: "var(--n-text)" }}>
                Status Kandidat
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(data.candidates.by_status).map(([status, count]) => (
                  <span key={status} className="pill p-gray">
                    {CANDIDATE_STATUS_LABELS[status] ?? status}: {count}
                  </span>
                ))}
                {data.candidates.total === 0 && (
                  <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                    Belum ada kandidat.
                  </span>
                )}
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Finance & e-Faktur" subtitle="Invoice terbaru">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="th">Invoice</th>
                    <th className="th">Klien</th>
                    <th className="th text-right">Jumlah</th>
                    <th className="th">Status</th>
                    <th className="th">Faktur</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
                  {recentInvoices.map((inv) => (
                    <tr key={inv.id}>
                      <td className="td font-mono text-xs">{inv.invoice_no}</td>
                      <td className="td">{clientName(inv.client_id)}</td>
                      <td className="td text-right font-mono">{formatRupiah(inv.total_due)}</td>
                      <td className="td">
                        <span className={`pill ${INVOICE_STATUS_PILL[inv.status] ?? "p-gray"}`}>{inv.status}</span>
                      </td>
                      <td className="td text-xs" style={{ color: "var(--n-text-muted)" }}>
                        {FAKTUR_STATUS_LABEL[inv.tax_invoice_status ?? "belum_buat"] ?? "—"}
                      </td>
                    </tr>
                  ))}
                  {recentInvoices.length === 0 && (
                    <tr>
                      <td colSpan={5} className="td text-center" style={{ color: "var(--n-text-muted)" }}>
                        Belum ada invoice.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>

        {/* Kolom kanan */}
        <div className="space-y-5">
          <div
            className="rounded-xl p-4 text-white"
            style={{ background: "linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%)" }}
          >
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-white/70">
              <Sparkles className="h-3.5 w-3.5" /> AI Executive Digest
            </div>
            {digest && digest.items.length > 0 ? (
              <ul className="mt-2 space-y-1.5">
                {digest.items.map((item, idx) => {
                  const ItemIcon = DIGEST_ICON[item.type] ?? Info;
                  return (
                    <li key={idx} className="flex items-start gap-2 text-sm leading-relaxed">
                      <ItemIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{item.detail}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-2 text-sm leading-relaxed text-white/90">{data.ai_insight.hint}</p>
            )}
          </div>

          <SectionCard title="People & Compliance">
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--n-text)" }}>BPJS Lengkap</span>
                  <span className="font-mono font-medium" style={{ color: "var(--n-text)" }}>
                    {data.people.bpjs_complete}/{data.people.total_employees} ·{" "}
                    {pct(data.people.bpjs_complete, data.people.total_employees)}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 rounded-full" style={{ backgroundColor: "var(--n-hover)" }}>
                  <div
                    className="h-full rounded-full bg-emerald-500"
                    style={{ width: `${pct(data.people.bpjs_complete, data.people.total_employees)}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--n-text)" }}>Asuransi Lengkap</span>
                  <span className="font-mono font-medium" style={{ color: "var(--n-text)" }}>
                    {data.people.insurance_complete}/{data.people.total_employees} ·{" "}
                    {pct(data.people.insurance_complete, data.people.total_employees)}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 rounded-full" style={{ backgroundColor: "var(--n-hover)" }}>
                  <div
                    className="h-full rounded-full bg-amber-500"
                    style={{ width: `${pct(data.people.insurance_complete, data.people.total_employees)}%` }}
                  />
                </div>
              </div>
            </div>
            {data.people.expiring_contracts_14d > 0 && (
              <div className="mt-3">
                <CalloutBlock tone="warning">
                  <span className="font-semibold">Expiry ≤14 hari:</span>{" "}
                  {data.people.expiring_contracts_14d} kontrak perlu tindak lanjut.
                </CalloutBlock>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Client Profit Margin" subtitle="Laba per klien bulan berjalan">
            {data.operations.profit_by_client.length > 0 ? (
              <div className="space-y-2.5">
                {data.operations.profit_by_client.slice(0, 6).map((row) => {
                  const marginPct = row.revenue > 0 ? Math.round((row.margin / row.revenue) * 100) : 0;
                  return (
                    <div key={row.client} className="flex items-center justify-between">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium" style={{ color: "var(--n-text)" }}>
                          {row.client}
                        </p>
                        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                          {formatRupiah(row.revenue)}
                        </p>
                      </div>
                      <span className={`pill ${marginPct >= 15 ? "p-green" : marginPct >= 0 ? "p-yellow" : "p-red"}`}>
                        {marginPct}% margin
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                Belum ada data margin per klien.
              </p>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
