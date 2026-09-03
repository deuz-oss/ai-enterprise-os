import { Fragment, FormEvent, useState } from "react";
import { BarChart3, Bot, BookOpen, Clock, FolderTree, Landmark, Lock, Package, ShoppingCart } from "lucide-react";
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

type Tab = "jurnal" | "coa" | "periode" | "ai" | "aging" | "assets" | "purchases" | "cashbank";

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

  const reverseEntry = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string | null }) =>
      api.post(`/accounting/journal/${id}/reverse`, { reason }),
    onSuccess: invalidateAll,
  });

  const deleteEntry = useMutation({
    mutationFn: (id: string) => api.delete(`/accounting/journal/${id}`),
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
        <PageHeader icon={BarChart3} title="Akunting" />
        <div className="flex items-center gap-2">
          <span className="text-sm" style={{ color: "var(--n-text-muted)" }}>Tahun</span>
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
            ["jurnal", "Jurnal", BookOpen],
            ["coa", "Bagan Akun", FolderTree],
            ["periode", "Periode & Tutup Buku", Lock],
            ["ai", "AI & Rekonsiliasi", Bot],
            ["aging", "Utang Jatuh Tempo", Clock],
            ["assets", "Aset Tetap", Package],
            ["purchases", "Pembelian", ShoppingCart],
            ["cashbank", "Kas & Bank", Landmark],
          ] as const
        ).map(([k, label, Icon]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className="flex items-center gap-1.5 rounded px-3 py-1.5 text-sm transition-colors"
            style={{
              border: "1px solid var(--n-border)",
              backgroundColor: tab === k ? "var(--n-hover)" : "transparent",
              color: tab === k ? "var(--n-text)" : "var(--n-text-muted)",
              fontWeight: tab === k ? 500 : 400,
            }}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {tab === "jurnal" && (
        <>
          <form onSubmit={handleCreate} className="card space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Jurnal Umum Baru</h2>
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

          <JournalList
            year={year}
            onPost={(id) => postEntry.mutate(id)}
            onReverse={(id, reason) => reverseEntry.mutate({ id, reason })}
            onDelete={(id) => deleteEntry.mutate(id)}
          />
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
                        <span className="pill p-gray">nonaktif</span>
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
          <CalloutBlock tone="warning">
            Tutup buku mengunci periode: input jurnal backdate ditolak dan mesin
            auto-journal melewati periode tertutup. Buka ulang tercatat di audit.
          </CalloutBlock>          <div className="card space-y-2">
            <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Tutup Bulan</h2>
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
                        className="text-xs font-medium hover:opacity-80"
                        style={{ color: "var(--accent)" }}
                      >
                        Buka Ulang
                      </button>
                    </td>
                  </tr>
                ))}
                {periods?.length === 0 && (
                  <tr>
                    <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
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

      {tab === "aging" && <ApAgingPanel />}
      {tab === "assets" && <FixedAssetsPanel />}
      {tab === "purchases" && <PurchasesPanel />}
      {tab === "cashbank" && <CashBankPanel />}

      {tab === "jurnal" && (
        <>
          <div className="card overflow-x-auto p-0">
            <div className="border-b p-4" style={{ borderColor: "var(--n-border)" }}>
              <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Neraca Saldo {year}</h2>
            </div>
            <table className="w-full">
              <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
                <tr>
                  <th className="th">Akun</th>
                  <th className="th">Nama</th>
                  <th className="th">Total Debit</th>
                  <th className="th">Total Kredit</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
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
                    <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                      Belum ada mutasi jurnal.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {incomeStatement && (
            <div className="card">
              <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Laba Rugi {incomeStatement.year}</h2>
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
              <p className="mt-3 border-t pt-3 text-right font-semibold" style={{ borderColor: "var(--n-border)" }}>
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

function JournalList({
  year,
  onPost,
  onReverse,
  onDelete,
}: {
  year: number;
  onPost: (id: string) => void;
  onReverse: (id: string, reason: string | null) => void;
  onDelete: (id: string) => void;
}) {
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
          is_reversed: boolean;
          lines: { account_code: string; debit: number; credit: number; memo: string | null }[];
        }[]
      >(`/accounting/journal?year=${year}${filter ? `&event_code=${filter}` : ""}${filter === "" ? "" : ""}`),
  });

  return (
    <div className="card overflow-x-auto p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4" style={{ borderColor: "var(--n-border)" }}>
        <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Daftar Jurnal {year}</h2>
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
        <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
          <tr>
            <th className="th">Tanggal</th>
            <th className="th">Keterangan</th>
            <th className="th">Baris</th>
            <th className="th">Status</th>
            <th className="th">Aksi</th>
          </tr>
        </thead>
        <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
          {(entries ?? []).map((e) => (
            <tr key={e.id}>
              <td className="td font-mono text-xs">{e.entry_date}</td>
              <td className="td">
                {e.description}
                {e.event_code && (
                  <span className="ml-1 pill p-gray">{e.event_code}</span>
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
                    className="font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                  >
                    Posting
                  </button>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <span className="pill p-green">posted</span>
                    {e.is_reversed && <span className="pill p-gray">dibalik</span>}
                  </span>
                )}
              </td>
              <td className="td">
                {e.status === "memorial" && (
                  <button
                    onClick={() => {
                      if (confirm(`Hapus jurnal draft "${e.description}"?`)) onDelete(e.id);
                    }}
                    className="text-xs font-medium text-red-600 hover:opacity-80"
                  >
                    Hapus
                  </button>
                )}
                {e.status === "posted" && !e.is_reversed && (
                  <button
                    onClick={() => {
                      const reason = prompt("Alasan pembalikan (opsional):") ?? "";
                      onReverse(e.id, reason || null);
                    }}
                    className="text-xs font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                  >
                    Balik Jurnal
                  </button>
                )}
              </td>
            </tr>
          ))}
          {entries?.length === 0 && (
            <tr>
              <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                Belum ada jurnal.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

interface ApAgingRow {
  bill_id: string;
  bill_number: string | null;
  vendor_name: string;
  total_due: number;
  due_date: string;
  days_overdue: number;
  bucket: string;
}

const AGING_BUCKETS = ["1-30", "31-60", ">60"] as const;
const AGING_BUCKET_CLS: Record<string, string> = {
  "1-30": "pill p-yellow",
  "31-60": "pill p-orange",
  ">60": "pill p-red",
};

function ApAgingPanel() {
  const { data: rows } = useQuery({
    queryKey: ["ap-aging"],
    queryFn: () => api.get<ApAgingRow[]>("/accounting/cashbank/bills/aging"),
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {AGING_BUCKETS.map((bucket) => {
          const bucketRows = (rows ?? []).filter((r) => r.bucket === bucket);
          const total = bucketRows.reduce((s, r) => s + r.total_due, 0);
          return (
            <div key={bucket} className="card">
              <span className={AGING_BUCKET_CLS[bucket]}>{bucket} hari</span>
              <p className="mt-2 text-lg font-semibold" style={{ color: "var(--n-text)" }}>
                {formatRupiah(total)}
              </p>
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                {bucketRows.length} tagihan
              </p>
            </div>
          );
        })}
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">No. Tagihan</th>
              <th className="th">Vendor</th>
              <th className="th">Jatuh Tempo</th>
              <th className="th">Hari Terlambat</th>
              <th className="th">Bucket</th>
              <th className="th">Jumlah</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(rows ?? []).map((r) => (
              <tr key={r.bill_id}>
                <td className="td font-mono text-xs">{r.bill_number ?? "-"}</td>
                <td className="td">{r.vendor_name}</td>
                <td className="td text-xs">{r.due_date}</td>
                <td className="td">{r.days_overdue}</td>
                <td className="td">
                  <span className={AGING_BUCKET_CLS[r.bucket] ?? "pill p-gray"}>{r.bucket}</span>
                </td>
                <td className="td font-medium">{formatRupiah(r.total_due)}</td>
              </tr>
            ))}
            {rows?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Tidak ada utang vendor yang jatuh tempo.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface FixedAssetRow {
  id: string;
  name: string;
  acquisition_date: string;
  cost: number;
  useful_life_months: number;
  accumulated_depreciation: number;
  monthly_depreciation: number;
  book_value: number;
  last_depreciated_ym: string | null;
  disposed_at: string | null;
}

function FixedAssetsPanel() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [includeDisposed, setIncludeDisposed] = useState(false);
  const now = new Date();
  const [depYear, setDepYear] = useState(now.getFullYear());
  const [depMonth, setDepMonth] = useState(now.getMonth() + 1);

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<AccountRow[]>("/accounting/accounts"),
  });
  const { data: assets } = useQuery({
    queryKey: ["fixed-assets", includeDisposed],
    queryFn: () =>
      api.get<FixedAssetRow[]>(`/accounting/assets?include_disposed=${includeDisposed}`),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["fixed-assets"] });

  const createAsset = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/accounting/assets", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const depreciateOne = useMutation({
    mutationFn: ({ id, year, month }: { id: string; year: number; month: number }) =>
      api.post(`/accounting/assets/${id}/depreciate`, { year, month }),
    onSuccess: invalidate,
  });

  const depreciatePeriod = useMutation({
    mutationFn: () => api.post<{ posted: string[]; skipped: { asset: string; reason: string }[] }>(
      "/accounting/assets/depreciate-period",
      { year: depYear, month: depMonth }
    ),
    onSuccess: invalidate,
  });

  const disposeAsset = useMutation({
    mutationFn: ({ id, proceeds }: { id: string; proceeds: number }) =>
      api.post(`/accounting/assets/${id}/dispose`, { proceeds }),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={depYear}
            onChange={(e) => setDepYear(Number(e.target.value))}
            className="input w-24"
          />
          <input
            type="number"
            min={1}
            max={12}
            value={depMonth}
            onChange={(e) => setDepMonth(Number(e.target.value))}
            className="input w-20"
          />
          <button
            className="btn-secondary"
            disabled={depreciatePeriod.isPending}
            onClick={() => depreciatePeriod.mutate()}
          >
            Jalankan Susutan Periode Ini
          </button>
          <label className="flex items-center gap-1.5 text-sm" style={{ color: "var(--n-text-muted)" }}>
            <input
              type="checkbox"
              checked={includeDisposed}
              onChange={(e) => setIncludeDisposed(e.target.checked)}
            />
            Tampilkan yang sudah dilepas
          </label>
        </div>
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Aset Baru"}
        </button>
      </div>

      {depreciatePeriod.data && (
        <CalloutBlock tone="success">
          Disusutkan: {depreciatePeriod.data.posted.length} aset.
          {depreciatePeriod.data.skipped.length > 0 &&
            ` Dilewati: ${depreciatePeriod.data.skipped.length} (sudah tersusut/tidak eligible).`}
        </CalloutBlock>
      )}
      {depreciateOne.error && (
        <p className="text-sm text-red-600">{(depreciateOne.error as Error).message}</p>
      )}
      {disposeAsset.error && (
        <p className="text-sm text-red-600">{(disposeAsset.error as Error).message}</p>
      )}

      {showForm && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            createAsset.mutate({
              name: form.get("name"),
              asset_account_id: form.get("asset_account_id"),
              funding_account_id: form.get("funding_account_id") || null,
              acquisition_date: form.get("acquisition_date") || null,
              cost: Number(form.get("cost") || 0),
              useful_life_months: Number(form.get("useful_life_months") || 48),
              notes: form.get("notes") || null,
            });
          }}
          className="card grid grid-cols-1 gap-3 sm:grid-cols-3"
        >
          <input name="name" required placeholder="Nama aset *" className="input" />
          <select name="asset_account_id" required className="input" defaultValue="">
            <option value="" disabled>
              Akun aset *
            </option>
            {(accounts ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} - {a.name}
              </option>
            ))}
          </select>
          <select name="funding_account_id" className="input" defaultValue="">
            <option value="">Akun pendanaan (opsional)</option>
            {(accounts ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} - {a.name}
              </option>
            ))}
          </select>
          <input name="acquisition_date" type="date" className="input" />
          <input name="cost" type="number" required placeholder="Harga perolehan (Rp) *" className="input" />
          <input
            name="useful_life_months"
            type="number"
            defaultValue={48}
            placeholder="Umur manfaat (bulan)"
            className="input"
          />
          <input name="notes" placeholder="Catatan" className="input sm:col-span-3" />
          {createAsset.error && (
            <p className="text-sm text-red-600 sm:col-span-3">{(createAsset.error as Error).message}</p>
          )}
          <button type="submit" disabled={createAsset.isPending} className="btn sm:col-span-3">
            Simpan Aset
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">Nama</th>
              <th className="th">Perolehan</th>
              <th className="th">Harga</th>
              <th className="th">Umur</th>
              <th className="th">Akumulasi Susut</th>
              <th className="th">Nilai Buku</th>
              <th className="th">Susut Terakhir</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(assets ?? []).map((a) => (
              <tr key={a.id}>
                <td className="td font-medium">{a.name}</td>
                <td className="td text-xs">{a.acquisition_date}</td>
                <td className="td">{formatRupiah(a.cost)}</td>
                <td className="td text-xs">{a.useful_life_months} bln</td>
                <td className="td">{formatRupiah(a.accumulated_depreciation)}</td>
                <td className="td font-medium">{formatRupiah(a.book_value)}</td>
                <td className="td text-xs">{a.last_depreciated_ym ?? "-"}</td>
                <td className="td">
                  {a.disposed_at ? (
                    <span className="pill p-gray">Dilepas {a.disposed_at}</span>
                  ) : (
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        className="text-xs font-medium hover:opacity-80"
                        style={{ color: "var(--accent)" }}
                        disabled={depreciateOne.isPending}
                        onClick={() =>
                          depreciateOne.mutate({ id: a.id, year: depYear, month: depMonth })
                        }
                      >
                        Susutkan
                      </button>
                      <button
                        className="text-xs font-medium text-red-600 hover:opacity-80"
                        onClick={() => {
                          const proceeds = prompt("Hasil pelepasan (Rp, 0 kalau tidak ada):", "0");
                          if (proceeds !== null) {
                            disposeAsset.mutate({ id: a.id, proceeds: Number(proceeds) || 0 });
                          }
                        }}
                      >
                        Lepas Aset
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {assets?.length === 0 && (
              <tr>
                <td colSpan={8} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada aset tetap.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface PurchaseBillRow {
  id: string;
  vendor_name: string;
  bill_number: string | null;
  amount: number;
  ppn_rate: number;
  ppn_amount: number;
  entry_date: string;
  due_date: string | null;
  status: string;
  notes: string | null;
}

const BILL_STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  belum_dibayar: { label: "belum dibayar", cls: "pill p-yellow" },
  dibayar: { label: "dibayar", cls: "pill p-green" },
};

function PurchasesPanel() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [payingId, setPayingId] = useState<string | null>(null);

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<AccountRow[]>("/accounting/accounts"),
  });
  const { data: bills } = useQuery({
    queryKey: ["purchase-bills", statusFilter],
    queryFn: () =>
      api.get<PurchaseBillRow[]>(`/accounting/purchases${statusFilter ? `?status=${statusFilter}` : ""}`),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["purchase-bills"] });

  const createBill = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/accounting/purchases", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const payBill = useMutation({
    mutationFn: ({ id, bankAccountId }: { id: string; bankAccountId: string }) =>
      api.post(`/accounting/purchases/${id}/pay`, { bank_account_id: bankAccountId }),
    onSuccess: () => {
      setPayingId(null);
      invalidate();
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input w-auto">
          <option value="">Semua status</option>
          <option value="belum_dibayar">Belum dibayar</option>
          <option value="dibayar">Dibayar</option>
        </select>
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Bill Vendor Baru"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            createBill.mutate({
              vendor_name: form.get("vendor_name"),
              expense_account_id: form.get("expense_account_id"),
              amount: Number(form.get("amount") || 0),
              ppn_rate: Number(form.get("ppn_rate") || 0),
              entry_date: form.get("entry_date") || null,
              due_date: form.get("due_date") || null,
              bill_number: form.get("bill_number") || null,
              notes: form.get("notes") || null,
            });
          }}
          className="card grid grid-cols-1 gap-3 sm:grid-cols-3"
        >
          <input name="vendor_name" required placeholder="Nama vendor *" className="input" />
          <select name="expense_account_id" required className="input" defaultValue="">
            <option value="" disabled>
              Akun beban *
            </option>
            {(accounts ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} - {a.name}
              </option>
            ))}
          </select>
          <input name="bill_number" placeholder="No. tagihan" className="input" />
          <input name="amount" type="number" required placeholder="Jumlah (Rp) *" className="input" />
          <input name="ppn_rate" type="number" step="0.01" placeholder="Tarif PPN (0-1)" className="input" />
          <input name="entry_date" type="date" className="input" />
          <input name="due_date" type="date" placeholder="Jatuh tempo" className="input" />
          <input name="notes" placeholder="Catatan" className="input sm:col-span-3" />
          {createBill.error && (
            <p className="text-sm text-red-600 sm:col-span-3">{(createBill.error as Error).message}</p>
          )}
          <button type="submit" disabled={createBill.isPending} className="btn sm:col-span-3">
            Simpan Bill
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">No. Tagihan</th>
              <th className="th">Vendor</th>
              <th className="th">Tanggal</th>
              <th className="th">Jatuh Tempo</th>
              <th className="th">Jumlah</th>
              <th className="th">PPN</th>
              <th className="th">Status</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(bills ?? []).map((b) => {
              const st = BILL_STATUS_LABELS[b.status] ?? BILL_STATUS_LABELS.belum_dibayar;
              return (
                <Fragment key={b.id}>
                  <tr>
                    <td className="td font-mono text-xs">{b.bill_number ?? "-"}</td>
                    <td className="td">{b.vendor_name}</td>
                    <td className="td text-xs">{b.entry_date}</td>
                    <td className="td text-xs">{b.due_date ?? "-"}</td>
                    <td className="td font-medium">{formatRupiah(b.amount + b.ppn_amount)}</td>
                    <td className="td">{formatRupiah(b.ppn_amount)}</td>
                    <td className="td">
                      <span className={st.cls}>{st.label}</span>
                    </td>
                    <td className="td">
                      {b.status === "belum_dibayar" && (
                        <button
                          className="text-xs font-medium hover:opacity-80"
                          style={{ color: "var(--accent)" }}
                          onClick={() => setPayingId(payingId === b.id ? null : b.id)}
                        >
                          Bayar
                        </button>
                      )}
                    </td>
                  </tr>
                  {payingId === b.id && (
                    <tr>
                      <td colSpan={8} className="td" style={{ backgroundColor: "var(--n-hover)" }}>
                        <form
                          className="flex flex-wrap items-center gap-2 py-2"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const form = new FormData(e.currentTarget);
                            const bankAccountId = String(form.get("bank_account_id") || "");
                            if (bankAccountId) payBill.mutate({ id: b.id, bankAccountId });
                          }}
                        >
                          <select name="bank_account_id" required className="input w-auto" defaultValue="">
                            <option value="" disabled>
                              Bayar dari akun kas/bank *
                            </option>
                            {(accounts ?? []).map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.code} - {a.name}
                              </option>
                            ))}
                          </select>
                          <button type="submit" disabled={payBill.isPending} className="btn py-1 text-xs">
                            Konfirmasi Bayar
                          </button>
                          {payBill.error && (
                            <p className="text-xs text-red-600">{(payBill.error as Error).message}</p>
                          )}
                        </form>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {bills?.length === 0 && (
              <tr>
                <td colSpan={8} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada bill vendor.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface BankTxRow {
  id: string;
  tx_date: string;
  tx_type: string;
  amount: number;
  description: string | null;
  reconciled: boolean;
}

const BANK_TX_LABELS: Record<string, string> = {
  penerimaan: "Penerimaan",
  pembayaran: "Pembayaran",
  transfer_antar_rekening: "Transfer Antar Rekening",
};

function CashBankPanel() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState<number | "">(now.getMonth() + 1);
  const [reconciledFilter, setReconciledFilter] = useState<"" | "true" | "false">("");

  const { data: accounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<AccountRow[]>("/accounting/accounts"),
  });
  const { data: txs } = useQuery({
    queryKey: ["bank-transactions", year, month, reconciledFilter],
    queryFn: () => {
      const params = new URLSearchParams({ year: String(year) });
      if (month) params.set("month", String(month));
      if (reconciledFilter) params.set("reconciled", reconciledFilter);
      return api.get<BankTxRow[]>(`/accounting/cashbank/transactions?${params}`);
    },
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["bank-transactions"] });

  const createTx = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/accounting/cashbank/transactions", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const reconcileTx = useMutation({
    mutationFn: (id: string) => api.post(`/accounting/cashbank/transactions/${id}/reconcile`, {}),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-24" />
          <select
            value={month}
            onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : "")}
            className="input w-auto"
          >
            <option value="">Semua bulan</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select
            value={reconciledFilter}
            onChange={(e) => setReconciledFilter(e.target.value as "" | "true" | "false")}
            className="input w-auto"
          >
            <option value="">Semua</option>
            <option value="true">Sudah rekonsiliasi</option>
            <option value="false">Belum rekonsiliasi</option>
          </select>
        </div>
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Transaksi Baru"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            createTx.mutate({
              tx_type: form.get("tx_type"),
              bank_account_id: form.get("bank_account_id"),
              counter_account_id: form.get("counter_account_id") || null,
              amount: Number(form.get("amount") || 0),
              tx_date: form.get("tx_date") || null,
              description: form.get("description") || null,
            });
          }}
          className="card grid grid-cols-1 gap-3 sm:grid-cols-3"
        >
          <select name="tx_type" required className="input" defaultValue="penerimaan">
            {Object.entries(BANK_TX_LABELS).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
          <select name="bank_account_id" required className="input" defaultValue="">
            <option value="" disabled>
              Akun kas/bank *
            </option>
            {(accounts ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} - {a.name}
              </option>
            ))}
          </select>
          <select name="counter_account_id" className="input" defaultValue="">
            <option value="">Akun lawan (opsional)</option>
            {(accounts ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} - {a.name}
              </option>
            ))}
          </select>
          <input name="amount" type="number" required placeholder="Jumlah (Rp) *" className="input" />
          <input name="tx_date" type="date" className="input" />
          <input name="description" placeholder="Keterangan" className="input sm:col-span-3" />
          {createTx.error && (
            <p className="text-sm text-red-600 sm:col-span-3">{(createTx.error as Error).message}</p>
          )}
          <button type="submit" disabled={createTx.isPending} className="btn sm:col-span-3">
            Simpan Transaksi
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">Tanggal</th>
              <th className="th">Tipe</th>
              <th className="th">Jumlah</th>
              <th className="th">Keterangan</th>
              <th className="th">Rekonsiliasi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(txs ?? []).map((t) => (
              <tr key={t.id}>
                <td className="td text-xs">{t.tx_date}</td>
                <td className="td">{BANK_TX_LABELS[t.tx_type] ?? t.tx_type}</td>
                <td className="td font-medium">{formatRupiah(t.amount)}</td>
                <td className="td">{t.description ?? "-"}</td>
                <td className="td">
                  {t.reconciled ? (
                    <span className="pill p-green">rekonsiliasi</span>
                  ) : (
                    <button
                      className="text-xs font-medium hover:opacity-80"
                      style={{ color: "var(--accent)" }}
                      disabled={reconcileTx.isPending}
                      onClick={() => reconcileTx.mutate(t.id)}
                    >
                      Tandai rekonsiliasi
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {txs?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada transaksi kas/bank periode ini.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
