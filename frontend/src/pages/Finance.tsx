import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";

interface ClientRow {
  id: string;
  name: string;
}

interface InvoiceRow {
  id: string;
  invoice_no: string;
  client_id: string;
  year: number;
  month: number;
  payroll_total: number;
  fee_amount: number;
  ppn_amount: number;
  pph23_amount: number;
  total_due: number;
  status: string;
  due_date: string | null;
}

interface AgingRow {
  invoice_id: string;
  invoice_no: string;
  client_name: string;
  total_due: number;
  days_overdue: number;
  bucket: string;
}

interface CashFlowRow {
  id: string;
  direction: string;
  category: string;
  amount: number;
  entry_date: string;
}

interface MonthlyFlow {
  year: number;
  month: number;
  inflow: number;
  outflow: number;
  net: number;
}

interface ForecastResult {
  history: MonthlyFlow[];
  projection: MonthlyFlow[];
  pending_receivables: number;
  outlook: string;
  summary: string;
  risks: string[];
  recommendations: string[];
  model: string;
}

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  draft: { label: "draft", cls: "bg-slate-100 text-slate-600" },
  terkirim: { label: "terkirim", cls: "bg-amber-100 text-amber-700" },
  dibayar: { label: "dibayar", cls: "bg-emerald-100 text-emerald-700" },
  dibatalkan: { label: "dibatalkan", cls: "bg-rose-100 text-rose-700" },
};

export default function Finance() {
  const qc = useQueryClient();
  const [showGenerate, setShowGenerate] = useState(false);
  const [cfYear, setCfYear] = useState(2026);
  const [forecast, setForecast] = useState<ForecastResult | null>(null);

  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const { data: invoices } = useQuery({
    queryKey: ["invoices"],
    queryFn: () => api.get<InvoiceRow[]>("/finance/invoices"),
  });
  const { data: aging } = useQuery({
    queryKey: ["aging"],
    queryFn: () => api.get<AgingRow[]>("/finance/invoices/aging"),
  });
  const { data: cashflow } = useQuery({
    queryKey: ["cashflow", cfYear],
    queryFn: () => api.get<CashFlowRow[]>(`/finance/cashflow?year=${cfYear}`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["aging"] });
  };

  const generateInvoice = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post("/finance/invoices/generate", body),
    onSuccess: () => {
      setShowGenerate(false);
      invalidate();
    },
  });
  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/finance/invoices/${id}`, { status }),
    onSuccess: invalidate,
  });
  const addCashflow = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/finance/cashflow", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cashflow"] }),
  });
  const runForecast = useMutation({
    mutationFn: (monthsAhead: number) =>
      api.post<ForecastResult>("/ai/finance/forecast", {
        months_ahead: monthsAhead,
      }),
    onSuccess: (data) => setForecast(data),
  });

  function handleGenerate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    generateInvoice.mutate({
      client_id: form.get("client_id"),
      year: Number(form.get("year")),
      month: Number(form.get("month")),
      fee_amount: Number(form.get("fee_amount") || 0),
    });
  }

  function handleCashflow(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    addCashflow.mutate({
      direction: form.get("direction"),
      category: form.get("category"),
      amount: Number(form.get("amount") || 0),
      entry_date: form.get("entry_date") || null,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Finance</h1>
        <button className="btn" onClick={() => setShowGenerate(!showGenerate)}>
          {showGenerate ? "Tutup" : "+ Generate Invoice"}
        </button>
      </div>

      {showGenerate && (
        <form onSubmit={handleGenerate} className="card grid grid-cols-1 gap-3 sm:grid-cols-4">
          <select name="client_id" required className="input">
            {(clients ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <input name="month" type="number" min={1} max={12} required placeholder="Bulan payrol" className="input" />
          <input name="year" type="number" required placeholder="Tahun payrol" className="input" />
          <input name="fee_amount" type="number" placeholder="Fee management (Rp)" className="input" />
          <button type="submit" disabled={generateInvoice.isPending} className="btn sm:col-span-4">
            Buat Invoice dari Payrol
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">No. Invoice</th>
              <th className="th">Periode</th>
              <th className="th">Payrol</th>
              <th className="th">PPN</th>
              <th className="th">Total</th>
              <th className="th">Jatuh Tempo</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(invoices ?? []).map((i) => {
              const st = STATUS_LABELS[i.status] ?? STATUS_LABELS.draft;
              return (
                <tr key={i.id}>
                  <td className="td font-mono text-xs">{i.invoice_no}</td>
                  <td className="td">{String(i.month).padStart(2, "0")}/{i.year}</td>
                  <td className="td">{formatRupiah(Number(i.payroll_total))}</td>
                  <td className="td">{formatRupiah(Number(i.ppn_amount))}</td>
                  <td className="td font-semibold">{formatRupiah(Number(i.total_due))}</td>
                  <td className="td">{i.due_date ?? "-"}</td>
                  <td className="td">
                    {i.status === "terkirim" || i.status === "draft" ? (
                      <button
                        onClick={() => updateStatus.mutate({ id: i.id, status: "dibayar" })}
                        className={`badge cursor-pointer ${st.cls}`}
                      >
                        {st.label} → tandai lunas
                      </button>
                    ) : (
                      <span className={`badge ${st.cls}`}>{st.label}</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {invoices?.length === 0 && (
              <tr>
                <td colSpan={7} className="td py-8 text-center text-slate-400">
                  Belum ada invoice.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="font-semibold text-rose-700">Aging — Tagihan Terlambat</h2>
        {(aging ?? []).length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">Tidak ada tagihan lewat jatuh tempo.</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {aging!.map((a) => (
              <li key={a.invoice_id} className="flex justify-between rounded-lg bg-rose-50 p-2">
                <span>
                  {a.client_name} · {a.invoice_no}
                </span>
                <span className="font-medium text-rose-700">
                  {formatRupiah(a.total_due)} · {a.days_overdue} hari ({a.bucket})
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-slate-700">Arus Kas</h2>
          <input
            type="number"
            value={cfYear}
            onChange={(e) => setCfYear(Number(e.target.value))}
            className="input w-24"
          />
        </div>
        <form onSubmit={handleCashflow} className="mt-3 flex flex-wrap gap-2">
          <select name="direction" className="input w-auto">
            <option value="masuk">Masuk</option>
            <option value="keluar">Keluar</option>
          </select>
          <input name="category" required placeholder="Kategori" className="input w-auto" />
          <input name="amount" type="number" required placeholder="Jumlah (Rp)" className="input w-40" />
          <input name="entry_date" type="date" className="input w-auto" />
          <button className="btn-secondary">Catat</button>
        </form>
        <ul className="mt-3 space-y-1 text-sm">
          {(cashflow ?? []).slice(0, 10).map((c) => (
            <li key={c.id} className="flex justify-between rounded-lg bg-slate-50 p-2">
              <span>
                {c.entry_date} · {c.category}
              </span>
              <span className={c.direction === "masuk" ? "text-emerald-700" : "text-rose-700"}>
                {c.direction === "masuk" ? "+" : "−"} {formatRupiah(Number(c.amount))}
              </span>
            </li>
          ))}
          {cashflow?.length === 0 && (
            <li className="text-sm text-slate-400">Belum ada catatan arus kas.</li>
          )}
        </ul>
      </div>

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold text-indigo-700">Forecast Arus Kas (AI)</h2>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              runForecast.mutate(Number(form.get("months_ahead")) || 3);
            }}
          >
            <select name="months_ahead" defaultValue="3" className="input w-auto">
              {[1, 2, 3, 6, 12].map((m) => (
                <option key={m} value={m}>
                  {m} bulan ke depan
                </option>
              ))}
            </select>
            <button className="btn" disabled={runForecast.isPending}>
              {runForecast.isPending ? "AI menganalisis..." : "Hitung Forecast"}
            </button>
          </form>
        </div>
        {runForecast.isPending && (
          <p className="mt-2 text-sm text-slate-400">AI sedang menganalisis tren arus kas...</p>
        )}
        {runForecast.error && (
          <p className="mt-2 text-sm text-red-600">{(runForecast.error as Error).message}</p>
        )}
        {forecast && !runForecast.isPending && (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`badge border-0 ${
                  forecast.outlook === "positif"
                    ? "bg-emerald-100 text-emerald-700"
                    : forecast.outlook === "negatif"
                      ? "bg-rose-100 text-rose-700"
                      : "bg-amber-100 text-amber-700"
                }`}
              >
                Outlook: {forecast.outlook}
              </span>
              <span className="text-xs text-slate-400">
                Piutang belum tertagih: {formatRupiah(forecast.pending_receivables)} · model:{" "}
                {forecast.model}
              </span>
            </div>
            <p className="text-sm text-slate-600">{forecast.summary}</p>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="th">Bulan</th>
                    <th className="th">Masuk</th>
                    <th className="th">Keluar</th>
                    <th className="th">Net</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {forecast.history.map((h) => (
                    <tr key={`h-${h.year}-${h.month}`} className="text-slate-500">
                      <td className="td">{`${h.year}-${String(h.month).padStart(2, "0")}`}</td>
                      <td className="td">{formatRupiah(h.inflow)}</td>
                      <td className="td">{formatRupiah(h.outflow)}</td>
                      <td className="td">{formatRupiah(h.net)}</td>
                    </tr>
                  ))}
                  {forecast.projection.map((p) => (
                    <tr key={`p-${p.year}-${p.month}`} className="bg-indigo-50/40 font-medium">
                      <td className="td">
                        {`${p.year}-${String(p.month).padStart(2, "0")}`} (proyeksi)
                      </td>
                      <td className="td">{formatRupiah(p.inflow)}</td>
                      <td className="td">{formatRupiah(p.outflow)}</td>
                      <td className={`td ${p.net >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                        {formatRupiah(p.net)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(forecast.risks.length > 0 || forecast.recommendations.length > 0) && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {forecast.risks.length > 0 && (
                  <div className="rounded-lg bg-rose-50 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-rose-700">
                      Risiko
                    </p>
                    <ul className="mt-1 list-disc pl-4 text-xs text-slate-600">
                      {forecast.risks.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {forecast.recommendations.length > 0 && (
                  <div className="rounded-lg bg-emerald-50 p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                      Rekomendasi
                    </p>
                    <ul className="mt-1 list-disc pl-4 text-xs text-slate-600">
                      {forecast.recommendations.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
