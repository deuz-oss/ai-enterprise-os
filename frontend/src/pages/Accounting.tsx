import { FormEvent, useState } from "react";
import { PageHeader } from "../components/notion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";

interface AccountRow {
  code: string;
  name: string;
  category: string;
}

interface LineIn {
  account_code: string;
  debit: number;
  credit: number;
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

export default function Accounting() {
  const qc = useQueryClient();
  const [year, setYear] = useState(2026);
  const [lines, setLines] = useState<LineIn[]>([
    { account_code: "1-1100", debit: 0, credit: 0 },
    { account_code: "4-1000", debit: 0, credit: 0 },
  ]);

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<AccountRow[]>("/accounting/accounts"),
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

  const createEntry = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post("/accounting/journal", body),
    onSuccess: () => {
      setLines([
        { account_code: "1-1100", debit: 0, credit: 0 },
        { account_code: "4-1000", debit: 0, credit: 0 },
      ]);
      qc.invalidateQueries({ queryKey: ["trial-balance"] });
      qc.invalidateQueries({ queryKey: ["income-statement"] });
    },
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
      lines: filled,
    });
  }

  function updateLine(index: number, patch: Partial<LineIn>) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
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

      <form onSubmit={handleCreate} className="card space-y-3">
        <h2 className="font-semibold text-slate-700">Jurnal Umum Baru</h2>
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
                <option key={a.code} value={a.code}>
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
          </div>
        ))}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() =>
              setLines((p) => [...p, { account_code: "1-1100", debit: 0, credit: 0 }])
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
    </div>
  );
}
