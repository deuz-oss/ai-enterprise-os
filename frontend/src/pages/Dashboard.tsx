import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../components/notion";
import { api } from "../api/client";

interface Overview {
  leads: {
    total: number;
    won: number;
    funnel: { stage: string; count: number }[];
  };
  clients: number;
  documents: number;
  job_orders: { open: number; filled: number };
  candidates: { total: number; by_status: Record<string, number> };
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

export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });

  if (isLoading || !data) return <p className="text-slate-500">Memuat...</p>;

  const stats = [
    { label: "Total Lead", value: data.leads.total, hint: `${data.leads.won} deal` },
    { label: "Klien Aktif", value: data.clients, hint: `${data.documents} dokumen legal` },
    { label: "Job Order Aktif", value: data.job_orders.open, hint: `${data.job_orders.filled} filled` },
    { label: "Kandidat", value: data.candidates.total, hint: `${data.candidates.by_status["placed"] ?? 0} placed` },
  ];

  return (
    <div className="space-y-6">
      <PageHeader emoji="🏠" title="Dashboard" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="card">
            <p className="text-sm text-slate-500">{s.label}</p>
            <p className="mt-1 text-3xl font-bold text-slate-800">{s.value}</p>
            <p className="mt-1 text-xs text-slate-400">{s.hint}</p>
          </div>
        ))}
      </div>
      <div className="card">
        <h2 className="font-semibold text-slate-700">Funnel Pre-sales</h2>
        <div className="mt-4 space-y-2">
          {data.leads.funnel.map((f) => {
            const max = Math.max(...data.leads.funnel.map((x) => x.count), 1);
            return (
              <div key={f.stage} className="flex items-center gap-3">
                <span className="w-24 text-sm text-slate-500">{STAGE_LABELS[f.stage] ?? f.stage}</span>
                <div className="h-6 flex-1 rounded bg-slate-100">
                  <div
                    className="h-6 rounded bg-indigo-500"
                    style={{ width: `${(f.count / max) * 100}%` }}
                  />
                </div>
                <span className="w-8 text-right text-sm font-medium text-slate-700">{f.count}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
