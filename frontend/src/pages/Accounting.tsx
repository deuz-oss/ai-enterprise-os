import { FormEvent, useState } from "react";
import { PageHeader, CalloutBlock } from "../components/notion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import AccountingAi from "./AccountingAi";

interface AccountRow {
  id: string;
  code: string;
  name: string;
  group_type: string;
  normal_balance: string;
  is_active: boolean;
}

interface LineIn {
  account_code: string;
  debit: number;
  credit: number;
  client_dim_id: string | null;
}

interface TrialBalanceRow {
  account_code: string;
  account_name: string;
  category: string;
  total_debit: number;
  total_credit: number;
}

interface IncomeStatement {
  year: number;
  revenues: { account_code: string; account_name: string; amount: number }[];
  expenses: { account_code: string; account_name: string; amount: number }[];
  total_revenue: number;
  total_expense: number;
  net_income: number;
}

interface PeriodRow {
  year: number;
  month: number;
  closed_at: string | null;
  notes: string | null;
}

const GROUP_LABELS: Record<string, string> = {
  aset_lancar: "Aset Lancar",
  aset_tetap: "Aset Tetap",
  liabilitas_pendek: "Liabilitas Pendek",
  liabilitas_panjang: "Liabilitas Panjang",
  ekuitas: "Ekuitas",
  pendapatan: "Pendapatan",
  hpp: "HPP",
  beban_usaha: "Beban Usaha",
  beban_lain: "Beban Lain",
  pendapatan_lain: "Pendapatan Lain",
};

type Tab = "jurnal" | "coa" | "periode" | "ai";

export default function Accounting() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("jurnal");
  const [year, setYear] = useState(2026);
  const [lines, setLines] = useState<LineIn[]>([
    { account_code: "1-1100", debit: 0, credit: 0, client_dim_id: null },
    { account_code: "4-1000", debit: 0, credit: 0, client_dim_id: null },
  ]);

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<AccountRow[]>("/accounting/accounts"),
  });
  const clients = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/clients"),
  });
  const { data: periods } = useQuery({
    queryKey: ["periods"],
    queryFn: () => api.get<PeriodRow[]>("/accounting/periods"),
  });
  const { data: trialBalance } = useQuery({
    queryKey: ["trial-balance", year],
    queryFn: () =>
      api.get<TrialBalanceRow[]>(`/accounting/trial-balance?year=${year}`),
  });
  const { data: incomeStatement } = useQuery({
    queryKey: ["income-statement", year],
    queryFn: () =>
      api.get<IncomeStatement>(`/accounting/reports/income-statement?year=${year}`),
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["trial-balance"] });
    qc.invalidateQueries({ queryKey: ["income-statement"] });
    qc.invalidateQueries({ queryKey: ["journal"] });
    qc.invalidateQueries({ queryKey: ["periods"] });
    qc.invalidateQueries({ queryKey: ["accounts"] });
  };

  const createEntry = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/accounting/journal", body),
    onSuccess: () => {
      setLines([
        { account_code: "1-1100", debit: 0, credit: 0, client_dim_id: null },
        { account_code: "4-1000", debit: 0, credit: 0, client_dim_id: null },
      ]);
      invalidateAll();
    },
  });

  const postEntry = useMutation({
    mutationFn: (id: string) => api.post(`/accounting/journal/${id}/post`, {}),
    onSuccess: invalidateAll,
  });

  const createAccount = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/accounting/accounts", body),
    onSuccess: invalidateAll,
  });

  const closePeriod = useMutation({
    mutationFn: (p: { y: number; m: number }) =>
      api.post(`/accounting/periods/${p.y}/${p.m}/close`, {}),
    onSuccess: invalidateAll,
  });

  const reopenPeriod = useMutation({
    mutationFn: (p: { y: number; m: number }) =>
      api.post(`/accounting/periods/${p.y}/${p.m}/reopen`, {}),
    onSuccess: invalidateAll,
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const filled = lines.map((l) => ({
      ...l,
      debit: Number(l.debit) || 0,
      credit: Number(l.credit) || 0,
    }));
    createEntry.mutate({
      entry_date: form.get("entry_date") || null,
      description: form.get("description"),
      status: form.get("status"),
      lines: filled,
    });
  }

  function updateLine(index: number, patch: Partial<LineIn>) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader emoji="📊" title="Akunting" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">Tahun</span>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="input w-24"
          />
        </div>
      </div>

      <div className="flex gap-2">
        {(
          [
            ["jurnal", "📓 Jurnal"],
            ["coa", "🗂️ Bagan Akun"],
            ["periode", "🔒 Periode & Tutup Buku"],
            ["ai", "🤖 AI & Rekonsiliasi"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className="rounded px-3 py-1.5 text-sm transition-colors"
            style={{
              border: "1px solid var(--n-border)",
              backgroundColor: tab === k ? "var(--n-hover)" : "transparent",
              color: tab === k ? "var(--n-text)" : "var(--n-text-muted)",
              fontWeight: tab === k ? 500 : 400,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "jurnal" && (
        <>
          <form onSubmit={handleCreate} className="card space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold text-slate-700">Jurnal Umum Baru</h2>
              <select name="status" defaultValue="posted" className="input w-auto text-xs">
                <option value="posted">Langsung posted</option>
                <option value="memorial">Memorial (draft)</option>
              </select>
            </div>
            <div className="flex flex-wrap gap-2">
              <input name="entry_date" type="date" className="input w-auto" />
              <input name="description" required placeholder="Keterangan *" className="input w-72" />
            </div>
            {lines.map((line, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <select
                  value={line.account_code}
                  onChange={(e) => updateLine(i, { account_code: e.target.value })}
                  className="input w-auto"
                >
                  {(accounts ?? []).map((a) => (
                    <option key={a.id} value={a.code}>
                      {a.code} · {a.name}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  placeholder="Debit"
                  value={line.debit || ""}
                  onChange={(e) => updateLine(i, { debit: Number(e.target.value), credit: 0 })}
                  className="input w-36"
                />
                <input
                  type="number"
                  placeholder="Kredit"
                  value={line.credit || ""}
                  onChange={(e) => updateLine(i, { credit: Number(e.target.value), debit: 0 })}
                  className="input w-36"
                />
                <select
                  value={line.client_dim_id ?? ""}
                  onChange={(e) => updateLine(i, { client_dim_id: e.target.value || null })}
                  className="input w-auto text-xs"
                  title="Dimensi klien (opsional)"
                >
                  <option value="">— tanpa dimensi —</option>
                  {(clients.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            ))}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() =>
                  setLines((p) => [
                    ...p,
                    { account_code: "1-1100", debit: 0, credit: 0, client_dim_id: null },
                  ])
                }
                className="btn-secondary text-xs"
              >
                + Baris
              </button>
              <button type="submit" disabled={createEntry.isPending} className="btn">
                Simpan Jurnal
              </button>
            </div>
          </form>

          <JournalList year={year} onPost={(id) => postEntry.mutate(id)} />
        </>
      )}

      {tab === "coa" && (
        <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              createAccount.mutate({
                code: f.get("code"),
                name: f.get("name"),
                group_type: f.get("group_type"),
                normal_balance: f.get("normal_balance"),
              });
              e.currentTarget.reset();
            }}
            className="card grid grid-cols-1 gap-2 sm:grid-cols-[auto_1fr_auto_auto_auto]"
          >
            <input name="code" required placeholder="Kode (mis. 5-6000)" className="input w-auto" />
            <input name="name" required placeholder="Nama akun *" className="input" />
            <select name="group_type" defaultValue="beban_usaha" className="input w-auto capitalize">
              {Object.entries(GROUP_LABELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <select name="normal_balance" defaultValue="debit" className="input w-auto">
              <option value="debit">Debit</option>
              <option value="kredit">Kredit</option>
            </select>
            <button disabled={createAccount.isPending} className="btn">
              + Akun
            </button>
          </form>

          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead style={{ backgroundColor: "var(--n-hover)" }}>
                <tr>
                  <th className="th">Kode</th>
                  <th className="th">Nama</th>
                  <th className="th">Kelompok</th>
                  <th className="th">Saldo Normal</th>
                  <th className="th">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
                {(accounts ?? []).map((a) => (
                  <tr key={a.id}>
                    <td className="td font-mono text-xs">{a.code}</td>
                    <td className="td">{a.name}</td>
                    <td className="td text-xs">{GROUP_LABELS[a.group_type] ?? a.group_type}</td>
                    <td className="td capitalize">{a.normal_balance}</td>
                    <td className="td">
                      {!a.is_active && (
                        <span className="badge bg-slate-100 text-slate-500">nonaktif</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "periode" && (
        <>
          <CalloutBlock emoji="🔒" tone="warning">
            Tutup buku mengunci periode: input jurnal backdate ditolak dan mesin
            auto-journal melewati periode tertutup. Buka ulang tercatat di audit.
          </CalloutBlock>          <div className="card space-y-2">
            <h2 className="font-semibold text-slate-700">Tutup Bulan</h2>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="number"
                min={1}
                max={12}
                placeholder="Bulan"
                defaultValue={new Date().getMonth() + 1}
                id="close-month"
                className="input w-24"
              />
              <input
                type="number"
                placeholder="Tahun"
                defaultValue={year}
                id="close-year"
                className="input w-24"
              />
              <button
                className="btn-secondary"
                onClick={() => {
                  const m = Number(
                    (document.getElementById("close-month") as HTMLInputElement).value
                  );
                  const y = Number(
                    (document.getElementById("close-year") as HTMLInputElement).value
                  );
                  closePeriod.mutate({ y, m });
                }}
              >
                Tutup Buku
              </button>
            </div>
            {closePeriod.error && (
              <p className="text-sm text-red-600">{(closePeriod.error as Error).message}</p>
            )}
          </div>
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead style={{ backgroundColor: "var(--n-hover)" }}>
                <tr>
                  <th className="th">Periode</th>
                  <th className="th">Ditutup</th>
                  <th className="th">Catatan</th>
                  <th className="th">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
                {(periods ?? []).map((p) => (
                  <tr key={`${p.year}-${p.month}`}>
                    <td className="td font-medium">
                      {String(p.month).padStart(2, "0")}/{p.year}
                    </td>
                    <td className="td text-xs">
                      {p.closed_at ? new Date(p.closed_at).toLocaleDateString("id-ID") : "-"}
                    </td>
                    <td className="td text-xs">{p.notes ?? "-"}</td>
                    <td className="td">
                      <button
                        onClick={() => reopenPeriod.mutate({ y: p.year, m: p.month })}
                        className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                      >
                        Buka Ulang
                      </button>
                    </td>
                  </tr>
                ))}
                {periods?.length === 0 && (
                  <tr>
                    <td colSpan={4} className="td py-8 text-center text-slate-400">
                      Belum ada periode yang ditutup.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "ai" && <AccountingAi />}

      {tab === "jurnal" && (
        <>
          <div className="card overflow-x-auto p-0">
            <div className="border-b border-slate-200 p-4">
              <h2 className="font-semibold text-slate-700">Neraca Saldo {year}</h2>
            </div>
            <table className="w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="th">Akun</th>
                  <th className="th">Nama</th>
                  <th className="th">Total Debit</th>
                  <th className="th">Total Kredit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(trialBalance ?? [])
                  .filter((r) => r.total_debit > 0 || r.total_credit > 0)
                  .map((r) => (
                    <tr key={r.account_code}>
                      <td className="td font-mono text-xs">{r.account_code}</td>
                      <td className="td">{r.account_name}</td>
                      <td className="td">{formatRupiah(Number(r.total_debit))}</td>
                      <td className="td">{formatRupiah(Number(r.total_credit))}</td>
                    </tr>
                  ))}
                {(trialBalance ?? []).every((r) => r.total_debit === 0 && r.total_credit === 0) && (
                  <tr>
                    <td colSpan={4} className="td py-8 text-center text-slate-400">
                      Belum ada mutasi jurnal.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {incomeStatement && (
            <div className="card">
              <h2 className="font-semibold text-slate-700">Laba Rugi {incomeStatement.year}</h2>
              <div className="mt-3 grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <p className="text-sm font-semibold text-emerald-700">Pendapatan</p>
                  <ul className="mt-1 space-y-1 text-sm">
                    {incomeStatement.revenues.map((r) => (
                      <li key={r.account_code} className="flex justify-between">
                        <span>{r.account_name}</span>
                        <span>{formatRupiah(r.amount)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-sm font-semibold text-rose-700">Beban</p>
                  <ul className="mt-1 space-y-1 text-sm">
                    {incomeStatement.expenses.map((r) => (
                      <li key={r.account_code} className="flex justify-between">
                        <span>{r.account_name}</span>
                        <span>{formatRupiah(r.amount)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <p className="mt-3 border-t border-slate-200 pt-3 text-right font-semibold">
                Laba Bersih:{" "}
                <span className={incomeStatement.net_income >= 0 ? "text-emerald-700" : "text-rose-700"}>
                  {formatRupiah(incomeStatement.net_income)}
                </span>
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function JournalList({ year, onPost }: { year: number; onPost: (id: string) => void }) {
  const [filter, setFilter] = useState("");
  const { data: entries } = useQuery({
    queryKey: ["journal", year, filter],
    queryFn: () =>
      api.get<
        {
          id: string;
          entry_date: string;
          description: string;
          status: string;
          event_code: string | null;
          lines: { account_code: string; debit: number; credit: number; memo: string | null }[];
        }[]
      >(`/accounting/journal?year=${year}${filter ? `&event_code=${filter}` : ""}${filter === "" ? "" : ""}`),
  });

  return (
    <div className="card overflow-x-auto p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 p-4">
        <h2 className="font-semibold text-slate-700">Daftar Jurnal {year}</h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="input w-auto text-xs"
        >
          <option value="">Semua sumber</option>
          <option value="invoice_issued">invoice_issued</option>
          <option value="invoice_paid">invoice_paid</option>
          <option value="payroll_finalized_internal">payroll_finalized_internal</option>
          <option value="payroll_finalized_proyek">payroll_finalized_proyek</option>
          <option value="pr_executed">pr_executed</option>
        </select>
      </div>
      <table className="w-full">
        <thead className="border-b border-slate-200 bg-slate-50">
          <tr>
            <th className="th">Tanggal</th>
            <th className="th">Keterangan</th>
            <th className="th">Baris</th>
            <th className="th">Status</th>
            <th className="th">Aksi</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {(entries ?? []).map((e) => (
            <tr key={e.id}>
              <td className="td font-mono text-xs">{e.entry_date}</td>
              <td className="td">
                {e.description}
                {e.event_code && (
                  <span className="ml-1 badge bg-slate-100 text-slate-500">{e.event_code}</span>
                )}
              </td>
              <td className="td text-xs">
                {e.lines
                  .map(
                    (l) =>
                      `${l.account_code}:${l.debit > 0 ? `D ${formatRupiah(l.debit)}` : `K ${formatRupiah(l.credit)}`}`
                  )
                  .join(" | ")}
              </td>
              <td className="td">
                {e.status === "memorial" ? (
                  <button
                    onClick={() => onPost(e.id)}
                    className="font-medium text-indigo-600 hover:text-indigo-800"
                  >
                    Posting
                  </button>
                ) : (
                  <span className="badge bg-emerald-100 text-emerald-700">posted</span>
                )}
              </td>
            </tr>
          ))}
          {entries?.length === 0 && (
            <tr>
              <td colSpan={5} className="td py-8 text-center text-slate-400">
                Belum ada jurnal.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
