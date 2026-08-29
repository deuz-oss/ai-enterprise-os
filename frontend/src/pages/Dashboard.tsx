import { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../components/notion";
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

const STAGE_LABELS: Record<string, string> = {
  lead: "Lead",
  kontak: "Kontak",
  presentasi: "Presentasi",
  penawaran: "Penawaran",
  negosiasi: "Negosiasi",
  deal: "Deal",
  gagal: "Gagal",
};

const STAGE_DOT: Record<string, string> = {
  lead: "#9f9f9f",
  kontak: "#2383e2",
  presentasi: "#5b5bd6",
  penawaran: "#9065b0",
  negosiasi: "#cb912f",
  deal: "#0f7b6c",
  gagal: "#e03e3e",
};

const JO_STAGE_LABELS: Record<string, string> = {
  open: "Open",
  screening: "Screening",
  interview_klien: "Interview",
  offering: "Offering",
  filled: "Filled",
  closed: "Closed",
};
const JO_STAGE_ORDER = ["open", "screening", "interview_klien", "offering", "filled", "closed"];

const DIGEST_ICON: Record<string, string> = {
  approval_menunggu: "🖊️",
  payroll_klien: "💼",
  sla_job_order: "⏳",
  kontrak_berakhir: "📄",
  invoice_overdue: "🧾",
  cuti_menunggu: "🌴",
  pengingat: "📌",
  ringkasan: "📊",
};

function pct(part: number, total: number): string {
  if (!total) return "-";
  return `${Math.round((part / total) * 100)}%`;
}

/** Widget kartu Dashboard Umum — kerangka konsisten label/isi/sumber SKU. */
function Widget({
  title,
  sku,
  children,
}: {
  title: string;
  sku?: string;
  children: ReactNode;
}) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>{title}</h2>
        {sku && (
          <span className="pill p-gray text-[10px] uppercase tracking-wide">{sku}</span>
        )}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div>
      <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>{label}</p>
      <p className="text-xl font-bold" style={{ color: "var(--n-text)" }}>{value}</p>
      {hint && <p className="text-[11px]" style={{ color: "var(--n-text-muted)" }}>{hint}</p>}
    </div>
  );
}

/// Dashboard — PRD v3.0 §8: 8+1 widget cross-bundle, 3 kolom desktop / 1 kolom mobile.
export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });
  const { data: digest } = useQuery({
    queryKey: ["chat-digest"],
    queryFn: () => api.get<Digest>("/chat/digest"),
  });

  if (isLoading || !data)
    return <p className="text-sm" style={{ color: "var(--n-text-muted)" }}>Memuat...</p>;

  const winRate = data.leads.total > 0 ? Math.round((data.leads.won / data.leads.total) * 100) : 0;
  const payrollTotal = Object.values(data.payroll).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-4">
      <PageHeader emoji="🏠" title="Dashboard" />

      {/* Widget 1 — Ringkasan Eksekutif (Foundation) */}
      <div className="card">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Ringkasan Eksekutif Hari Ini</h2>
          <span className="pill p-gray text-[10px] uppercase tracking-wide">Foundation</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Klien Aktif" value={data.clients} hint={`${data.documents} dokumen legal`} />
          <Stat label="Pipeline" value={data.leads.total} hint={`${data.leads.won} deal (${winRate}% win rate)`} />
          <Stat
            label="Job Order"
            value={data.job_orders.open}
            hint={`open · ${data.job_orders.filled} filled`}
          />
          <Stat label="Headcount Aktif" value={data.people.active_employees} hint={`dari ${data.people.total_employees} karyawan`} />
          <Stat label="Payroll Run" value={payrollTotal} hint={`${data.payroll.finalized ?? 0} final bulan ini`} />
          <Stat label="Revenue MTD" value={formatRupiah(data.finance.revenue_mtd)} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Widget 2 — Sales & Pipeline (Talent Cloud) */}
        <Widget title="Sales & Pipeline" sku="Talent Cloud">
          <div className="space-y-1.5">
            {data.leads.funnel.map((f) => {
              const max = Math.max(...data.leads.funnel.map((x) => x.count), 1);
              return (
                <div key={f.stage} className="flex items-center gap-2">
                  <span className="w-16 text-xs" style={{ color: "var(--n-text-muted)" }}>
                    {STAGE_LABELS[f.stage] ?? f.stage}
                  </span>
                  <div className="h-4 flex-1 rounded" style={{ backgroundColor: "var(--n-hover)" }}>
                    <div
                      className="h-4 rounded"
                      style={{
                        width: `${Math.max((f.count / max) * 100, f.count > 0 ? 8 : 0)}%`,
                        backgroundColor: f.count > 0 ? STAGE_DOT[f.stage] ?? "var(--accent)" : "transparent",
                      }}
                    />
                  </div>
                  <span className="w-5 text-right text-xs font-medium" style={{ color: "var(--n-text)" }}>
                    {f.count}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--n-text-muted)" }}>
            Win rate: {winRate}% · {data.job_orders.open} JO terbuka
          </p>
        </Widget>

        {/* Widget 3 — Recruitment & Talent (Talent Cloud) */}
        <Widget title="Recruitment & Talent" sku="Talent Cloud">
          <div className="space-y-1.5">
            {JO_STAGE_ORDER.map((stage) => {
              const count = data.recruitment_talent.job_orders_by_stage[stage] ?? 0;
              const max = Math.max(...Object.values(data.recruitment_talent.job_orders_by_stage), 1);
              return (
                <div key={stage} className="flex items-center gap-2">
                  <span className="w-16 text-xs" style={{ color: "var(--n-text-muted)" }}>
                    {JO_STAGE_LABELS[stage]}
                  </span>
                  <div className="h-4 flex-1 rounded" style={{ backgroundColor: "var(--n-hover)" }}>
                    <div
                      className="h-4 rounded"
                      style={{
                        width: `${Math.max((count / max) * 100, count > 0 ? 8 : 0)}%`,
                        backgroundColor: count > 0 ? "var(--accent)" : "transparent",
                      }}
                    />
                  </div>
                  <span className="w-5 text-right text-xs font-medium" style={{ color: "var(--n-text)" }}>
                    {count}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-xs" style={{ color: "var(--n-text-muted)" }}>
            {data.recruitment_talent.interviews_this_week} interview terjadwal minggu ini
          </p>
        </Widget>

        {/* Widget 4 — People & Compliance (Workforce Cloud) */}
        <Widget title="People & Compliance" sku="Workforce Cloud">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Karyawan Aktif" value={data.people.active_employees} />
            <Stat
              label="Kontrak ≤14 hari"
              value={data.people.expiring_contracts_14d}
              hint={data.people.expiring_contracts_14d > 0 ? "perlu tindak lanjut" : undefined}
            />
            <Stat
              label="BPJS Lengkap"
              value={pct(data.people.bpjs_complete, data.people.total_employees)}
              hint={`${data.people.bpjs_complete}/${data.people.total_employees}`}
            />
            <Stat
              label="Asuransi Lengkap"
              value={pct(data.people.insurance_complete, data.people.total_employees)}
              hint={`${data.people.insurance_complete}/${data.people.total_employees}`}
            />
          </div>
        </Widget>

        {/* Widget 5 — Operations & Projects (Workforce Cloud) */}
        <Widget title="Operations & Projects" sku="Workforce Cloud">
          {data.operations.active_placements_by_client.length > 0 ? (
            <ul className="space-y-1">
              {data.operations.active_placements_by_client.slice(0, 6).map((row) => {
                const profit = data.operations.profit_by_client.find((p) => p.client === row.client);
                return (
                  <li key={row.client} className="flex items-center justify-between text-xs">
                    <span style={{ color: "var(--n-text)" }}>{row.client}</span>
                    <span className="text-right" style={{ color: "var(--n-text-muted)" }}>
                      {row.active_placements} placement
                      {profit && (
                        <span className={profit.margin >= 0 ? "ml-2 text-emerald-600" : "ml-2 text-rose-600"}>
                          margin {formatRupiah(profit.margin)}
                        </span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
              Belum ada placement aktif per klien.
            </p>
          )}
        </Widget>

        {/* Widget 6 — Payroll & Compliance (Workforce Cloud) */}
        <Widget title="Payroll & Compliance" sku="Workforce Cloud">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Draft" value={data.payroll.draft ?? 0} />
            <Stat label="Diajukan" value={data.payroll.submitted ?? 0} />
            <Stat label="Disetujui" value={data.payroll.approved ?? 0} />
            <Stat label="Final" value={data.payroll.finalized ?? 0} />
          </div>
        </Widget>

        {/* Widget 7 — Finance & Cashflow (Revenue Cloud) */}
        <Widget title="Finance & Cashflow" sku="Revenue Cloud">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Revenue MTD" value={formatRupiah(data.finance.revenue_mtd)} />
            <Stat label="Outstanding" value={formatRupiah(data.finance.outstanding)} />
            <Stat
              label="Overdue"
              value={data.finance.overdue}
              hint={data.finance.overdue > 0 ? "invoice lewat jatuh tempo" : undefined}
            />
            <Stat
              label="Faktur Belum Dibuat"
              value={data.finance.faktur_belum}
              hint={`dari ${data.finance.invoices_total} invoice`}
            />
          </div>
        </Widget>

        {/* Widget 8 — Accounting Health (Govern Cloud) */}
        <Widget title="Accounting Health" sku="Govern Cloud">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Periode Tercatat" value={data.accounting.period_closed} />
            <Stat
              label="Jurnal Memorial"
              value={data.accounting.memorial_unposted}
              hint={data.accounting.memorial_unposted > 0 ? "belum posted" : "semua posted"}
            />
          </div>
        </Widget>

        {/* Widget 9 — AI Insight (fallback deterministik: GET /chat/digest) */}
        <Widget title="AI Insight" sku="AI Add-on">
          {digest && digest.items.length > 0 ? (
            <ul className="space-y-1.5">
              {digest.items.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2 text-xs" style={{ color: "var(--n-text)" }}>
                  <span>{DIGEST_ICON[item.type] ?? "•"}</span>
                  <span>{item.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>{data.ai_insight.hint}</p>
          )}
        </Widget>
      </div>
    </div>
  );
}
