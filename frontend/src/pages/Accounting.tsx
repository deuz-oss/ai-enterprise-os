import { FormEvent, useState } from "react";
import { BarChart3, Bot, BookOpen, Clock, FolderTree, Landmark, Lock, Package, ShoppingCart } from "lucide-react";
import { PageHeader, CalloutBlock } from "../components/workspace";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatDate, formatRupiah } from "../api/client";
import { toast } from "sonner";
import {
  confirmDialog,
  confirmToast,
  DataTable,
  MONTH_NAMES,
  PeriodPicker,
  type Column,
} from "../components/ui";
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
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [lines, setLines] = useState<LineIn[]>([
    { account_code: "1-1100", debit: 0, credit: 0, client_dim_id: null },
    { account_code: "4-1000", debit: 0, credit: 0, client_dim_id: null },
  ]);

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<AccountRow[]>("/accounting/accounts"),
  });
  const accounts = accountsQuery.data;
  const clients = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/clients"),
  });
  const periodsQuery = useQuery({
    queryKey: ["periods"],
    queryFn: () => api.get<PeriodRow[]>("/accounting/periods"),
  });
  const periods = periodsQuery.data;
  const trialBalanceQuery = useQuery({
    queryKey: ["trial-balance", year],
    queryFn: () =>
      api.get<TrialBalanceRow[]>(`/accounting/trial-balance?year=${year}`),
  });
  const trialBalance = trialBalanceQuery.data;
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

  // ---------- Tabel (DataTable) ----------
  const accountColumns: Column<AccountRow>[] = [
    { key: "code", header: "Kode", className: "font-mono text-xs", cell: (a) => a.code, sortValue: (a) => a.code },
    { key: "name", header: "Nama", cell: (a) => a.name, sortValue: (a) => a.name },
    {
      key: "group",
      header: "Kelompok",
      className: "text-xs",
      cell: (a) => GROUP_LABELS[a.group_type] ?? a.group_type,
      sortValue: (a) => GROUP_LABELS[a.group_type] ?? a.group_type,
    },
    { key: "normal", header: "Saldo Normal", className: "capitalize", cell: (a) => a.normal_balance },
    {
      key: "status",
      header: "Status",
      cell: (a) => (a.is_active ? null : <span className="pill p-gray">nonaktif</span>),
    },
  ];

  const periodColumns: Column<PeriodRow>[] = [
    {
      key: "period",
      header: "Periode",
      className: "font-medium",
      cell: (p) => `${String(p.month).padStart(2, "0")}/${p.year}`,
      sortValue: (p) => p.year * 100 + p.month,
    },
    { key: "closed", header: "Ditutup", className: "text-xs", cell: (p) => formatDate(p.closed_at) },
    { key: "notes", header: "Catatan", className: "text-xs", cell: (p) => p.notes ?? "-" },
    {
      key: "aksi",
      header: "Aksi",
      cell: (p) => (
        <button
          onClick={() =>
            // Buka ulang = jurnal backdate ke periode ini diizinkan lagi
            // (tercatat di audit; bisa ditutup kembali).
            confirmDialog({
              title: `Buka ulang periode ${String(p.month).padStart(2, "0")}/${p.year}?`,
              message:
                "Jurnal dengan tanggal di periode ini bisa diposting/diubah lagi dan laporan periode tersebut bisa berubah. Tindakan dicatat di audit; periode bisa ditutup kembali.",
              confirmLabel: "Buka Ulang",
              tone: "primary",
              onConfirm: () => reopenPeriod.mutate({ y: p.year, m: p.month }),
            })
          }
          className="text-xs font-medium hover:opacity-80"
          style={{ color: "var(--accent)" }}
        >
          Buka Ulang
        </button>
      ),
    },
  ];

  // Neraca saldo: hanya akun bermutasi + total debit/kredit (wajib sama).
  const trialRows = (trialBalance ?? []).filter((r) => r.total_debit > 0 || r.total_credit > 0);
  const trialDebit = trialRows.reduce((sum, r) => sum + Number(r.total_debit), 0);
  const trialCredit = trialRows.reduce((sum, r) => sum + Number(r.total_credit), 0);
  const trialBalanced = Math.abs(trialDebit - trialCredit) < 0.005;
  const trialColumns: Column<TrialBalanceRow>[] = [
    {
      key: "code",
      header: "Akun",
      className: "font-mono text-xs",
      cell: (r) => r.account_code,
      sortValue: (r) => r.account_code,
      footer: "Total",
    },
    { key: "name", header: "Nama", cell: (r) => r.account_name, sortValue: (r) => r.account_name },
    {
      key: "debit",
      header: "Total Debit",
      numeric: true,
      cell: (r) => formatRupiah(Number(r.total_debit)),
      sortValue: (r) => Number(r.total_debit),
      footer: formatRupiah(trialDebit),
    },
    {
      key: "credit",
      header: "Total Kredit",
      numeric: true,
      cell: (r) => formatRupiah(Number(r.total_credit)),
      sortValue: (r) => Number(r.total_credit),
      footer: formatRupiah(trialCredit),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader icon={BarChart3} title="Akunting" />
        <div className="flex items-center gap-2">
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>Tahun</span>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="input w-24"
            aria-label="Tahun"
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
              border: "1px solid var(--border)",
              backgroundColor: tab === k ? "var(--hover)" : "transparent",
              color: tab === k ? "var(--text)" : "var(--text-muted)",
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
          {/* JournalList (daftar) didahulukan dari form "buat baru" (DES-012,
              audit desain 2026-09-15) -- browse daftar jurnal existing adalah
              tugas yang lebih sering daripada bikin entri baru setiap buka
              tab ini. Isi form tidak berubah, cuma posisinya. */}
          <JournalList
            year={year}
            onPost={(id) =>
              confirmDialog({
                title: "Posting jurnal memorial?",
                message:
                  "Jurnal yang sudah diposting masuk ke buku besar dan tidak bisa diedit atau dihapus — koreksi hanya lewat jurnal balik.",
                confirmLabel: "Posting",
                tone: "primary",
                onConfirm: () =>
                  postEntry.mutate(id, {
                    onSuccess: () => toast.success("Jurnal diposting"),
                    onError: (e) => toast.error(`Gagal posting: ${(e as Error).message}`),
                  }),
              })
            }
            onReverse={(id, reason) => reverseEntry.mutate({ id, reason })}
            onDelete={(id) => deleteEntry.mutate(id)}
          />

          <form onSubmit={handleCreate} className="card space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold" style={{ color: "var(--text)" }}>Jurnal Umum Baru</h2>
              <select name="status" defaultValue="posted" className="input w-auto text-xs" aria-label="Status jurnal">
                <option value="posted">Langsung posted</option>
                <option value="memorial">Memorial (draft)</option>
              </select>
            </div>
            <div className="flex flex-wrap gap-2">
              <input name="entry_date" type="date" className="input w-auto" aria-label="Tanggal entri" />
              <input name="description" required placeholder="Keterangan *" className="input w-72" />
            </div>
            {lines.map((line, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <select
                  value={line.account_code}
                  onChange={(e) => updateLine(i, { account_code: e.target.value })}
                  className="input w-auto"
                  aria-label="Kode akun"
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
                  aria-label="Dimensi klien (opsional)"
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
            <select name="group_type" defaultValue="beban_usaha" className="input w-auto capitalize" aria-label="Kelompok akun">
              {Object.entries(GROUP_LABELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <select name="normal_balance" defaultValue="debit" className="input w-auto" aria-label="Saldo normal">
              <option value="debit">Debit</option>
              <option value="kredit">Kredit</option>
            </select>
            <button disabled={createAccount.isPending} className="btn">
              + Akun
            </button>
          </form>

          <DataTable
            label="Bagan akun"
            rows={accounts}
            columns={accountColumns}
            rowKey={(a) => a.id}
            query={accountsQuery}
            defaultSort={{ key: "code", dir: "asc" }}
            emptyTitle="Belum ada akun."
          />
        </>
      )}

      {tab === "periode" && (
        <>
          <CalloutBlock tone="warning">
            Tutup buku mengunci periode: input jurnal backdate ditolak dan mesin
            auto-journal melewati periode tertutup. Buka ulang tercatat di audit.
          </CalloutBlock>          <div className="card space-y-2">
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Tutup Bulan</h2>
            <div className="flex flex-wrap items-end gap-2">
              <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
                <span>Bulan</span>
                <select defaultValue={new Date().getMonth() + 1} id="close-month" className="input w-auto">
                  {MONTH_NAMES.map((m, i) => (
                    <option key={m} value={i + 1}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
                <span>Tahun</span>
                <input type="number" defaultValue={year} id="close-year" className="input w-24" />
              </label>
              <button
                className="btn-secondary"
                onClick={() => {
                  const m = Number(
                    (document.getElementById("close-month") as HTMLSelectElement).value
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
              <p className="text-sm text-red-600 dark:text-red-400">{(closePeriod.error as Error).message}</p>
            )}
          </div>
          <DataTable
            label="Periode tutup buku"
            rows={periods}
            columns={periodColumns}
            rowKey={(p) => `${p.year}-${p.month}`}
            query={periodsQuery}
            defaultSort={{ key: "period", dir: "desc" }}
            emptyTitle="Belum ada periode yang ditutup."
          />
        </>
      )}

      {tab === "ai" && <AccountingAi />}

      {tab === "aging" && <ApAgingPanel />}
      {tab === "assets" && <FixedAssetsPanel />}
      {tab === "purchases" && <PurchasesPanel />}
      {tab === "cashbank" && <CashBankPanel />}

      {tab === "jurnal" && (
        <>
          <section className="space-y-2" aria-labelledby="trial-balance-title">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 id="trial-balance-title" className="font-semibold" style={{ color: "var(--text)" }}>
                Neraca Saldo {year}
              </h2>
              {trialRows.length > 0 && (
                <span className={`pill ${trialBalanced ? "p-green" : "p-red"}`}>
                  {trialBalanced ? "Seimbang" : `Tidak seimbang: selisih ${formatRupiah(trialDebit - trialCredit)}`}
                </span>
              )}
            </div>
            <DataTable
              label={`Neraca saldo ${year}`}
              rows={trialRows}
              columns={trialColumns}
              rowKey={(r) => r.account_code}
              query={trialBalanceQuery}
              defaultSort={{ key: "code", dir: "asc" }}
              emptyTitle="Belum ada mutasi jurnal."
            />
          </section>

          {incomeStatement && (
            <div className="card">
              <h2 className="font-semibold" style={{ color: "var(--text)" }}>Laba Rugi {incomeStatement.year}</h2>
              <div className="mt-3 grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">Pendapatan</p>
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
                  <p className="text-sm font-semibold text-rose-700 dark:text-rose-400">Beban</p>
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
              <p className="mt-3 border-t pt-3 text-right font-semibold" style={{ borderColor: "var(--border)" }}>
                Laba Bersih:{" "}
                <span className={incomeStatement.net_income >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}>
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

interface JournalEntryRow {
  id: string;
  entry_date: string;
  description: string;
  status: string;
  event_code: string | null;
  is_reversed: boolean;
  lines: { account_code: string; debit: number; credit: number; memo: string | null }[];
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
  const entriesQuery = useQuery({
    queryKey: ["journal", year, filter],
    queryFn: () =>
      api.get<JournalEntryRow[]>(`/accounting/journal?year=${year}${filter ? `&event_code=${filter}` : ""}`),
  });

  const columns: Column<JournalEntryRow>[] = [
    {
      key: "date",
      header: "Tanggal",
      className: "whitespace-nowrap text-xs",
      cell: (e) => formatDate(e.entry_date),
      sortValue: (e) => e.entry_date,
    },
    {
      key: "desc",
      header: "Keterangan",
      cell: (e) => (
        <>
          {e.description}
          {e.event_code && <span className="ml-1 pill p-gray">{e.event_code}</span>}
        </>
      ),
      sortValue: (e) => e.description,
    },
    {
      key: "lines",
      header: "Baris",
      className: "text-xs",
      // Satu baris per akun (dulu digabung jadi satu string panjang "kode:D Rp… | …").
      cell: (e) => (
        <ul className="space-y-0.5">
          {e.lines.map((l, i) => (
            <li key={i} className="whitespace-nowrap tabular-nums">
              <span className="font-mono">{l.account_code}</span>{" "}
              {l.debit > 0 ? `D ${formatRupiah(l.debit)}` : `K ${formatRupiah(l.credit)}`}
            </li>
          ))}
        </ul>
      ),
    },
    {
      key: "amount",
      header: "Jumlah",
      numeric: true,
      cell: (e) => formatRupiah(e.lines.reduce((sum, l) => sum + Number(l.debit), 0)),
      sortValue: (e) => e.lines.reduce((sum, l) => sum + Number(l.debit), 0),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (e) => e.status,
      cell: (e) =>
        e.status === "memorial" ? (
          <button onClick={() => onPost(e.id)} className="font-medium hover:opacity-80" style={{ color: "var(--accent)" }}>
            Posting
          </button>
        ) : (
          <span className="flex items-center gap-1.5">
            <span className="pill p-green">posted</span>
            {e.is_reversed && <span className="pill p-gray">dibalik</span>}
          </span>
        ),
    },
    {
      key: "aksi",
      header: "Aksi",
      cell: (e) => (
        <>
          {e.status === "memorial" && (
            <button
              onClick={() => confirmToast(`Hapus jurnal draft "${e.description}"?`, () => onDelete(e.id))}
              className="text-xs font-medium text-red-600 hover:opacity-80 dark:text-red-400"
            >
              Hapus
            </button>
          )}
          {e.status === "posted" && !e.is_reversed && (
            <button
              onClick={() =>
                // Dulu window.prompt(): menekan Batal tetap membalik jurnal
                // (null ?? "" -> lanjut). Kini dialog; Batal = tidak terjadi apa-apa.
                confirmDialog({
                  title: "Balik jurnal ini?",
                  message: `Jurnal pembalik (debit/kredit ditukar) diposting untuk "${e.description}". Jurnal asli tetap tercatat dan ditandai dibalik.`,
                  confirmLabel: "Balik Jurnal",
                  tone: "primary",
                  input: { label: "Alasan pembalikan (opsional)", placeholder: "mis. salah akun" },
                  onConfirm: (reason) => onReverse(e.id, reason || null),
                })
              }
              className="text-xs font-medium hover:opacity-80"
              style={{ color: "var(--accent)" }}
            >
              Balik Jurnal
            </button>
          )}
        </>
      ),
    },
  ];

  return (
    <section className="space-y-2" aria-labelledby="journal-list-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="journal-list-title" className="font-semibold" style={{ color: "var(--text)" }}>
          Daftar Jurnal {year}
        </h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="input w-auto text-xs"
          aria-label="Filter sumber jurnal"
        >
          <option value="">Semua sumber</option>
          <option value="invoice_issued">invoice_issued</option>
          <option value="invoice_paid">invoice_paid</option>
          <option value="payroll_finalized_internal">payroll_finalized_internal</option>
          <option value="payroll_finalized_proyek">payroll_finalized_proyek</option>
          <option value="pr_executed">pr_executed</option>
        </select>
      </div>
      <DataTable
        label={`Daftar jurnal ${year}`}
        rows={entriesQuery.data}
        columns={columns}
        rowKey={(e) => e.id}
        query={entriesQuery}
        defaultSort={{ key: "date", dir: "desc" }}
        pageSize={50}
        emptyTitle={filter ? "Tidak ada jurnal dari sumber ini." : "Belum ada jurnal."}
      />
    </section>
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
  const rowsQuery = useQuery({
    queryKey: ["ap-aging"],
    queryFn: () => api.get<ApAgingRow[]>("/accounting/cashbank/bills/aging"),
  });
  const rows = rowsQuery.data;
  const columns: Column<ApAgingRow>[] = [
    {
      key: "no",
      header: "No. Tagihan",
      className: "font-mono text-xs",
      cell: (r) => r.bill_number ?? "-",
      sortValue: (r) => r.bill_number,
      footer: "Total",
    },
    { key: "vendor", header: "Vendor", cell: (r) => r.vendor_name, sortValue: (r) => r.vendor_name },
    {
      key: "due",
      header: "Jatuh Tempo",
      className: "whitespace-nowrap text-xs",
      cell: (r) => formatDate(r.due_date),
      sortValue: (r) => r.due_date,
    },
    {
      key: "days",
      header: "Hari Terlambat",
      numeric: true,
      cell: (r) => r.days_overdue,
      sortValue: (r) => r.days_overdue,
    },
    {
      key: "bucket",
      header: "Bucket",
      cell: (r) => <span className={AGING_BUCKET_CLS[r.bucket] ?? "pill p-gray"}>{r.bucket}</span>,
    },
    {
      key: "amount",
      header: "Jumlah",
      numeric: true,
      className: "font-medium",
      cell: (r) => formatRupiah(r.total_due),
      sortValue: (r) => r.total_due,
      footer: formatRupiah((rows ?? []).reduce((sum, r) => sum + r.total_due, 0)),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {AGING_BUCKETS.map((bucket) => {
          const bucketRows = (rows ?? []).filter((r) => r.bucket === bucket);
          const total = bucketRows.reduce((s, r) => s + r.total_due, 0);
          return (
            <div key={bucket} className="card">
              <span className={AGING_BUCKET_CLS[bucket]}>{bucket} hari</span>
              <p className="mt-2 text-lg font-semibold" style={{ color: "var(--text)" }}>
                {formatRupiah(total)}
              </p>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {bucketRows.length} tagihan
              </p>
            </div>
          );
        })}
      </div>

      <DataTable
        label="Utang vendor jatuh tempo"
        rows={rows}
        columns={columns}
        rowKey={(r) => r.bill_id}
        query={rowsQuery}
        defaultSort={{ key: "days", dir: "desc" }}
        emptyTitle="Tidak ada utang vendor yang jatuh tempo."
      />
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
  const assetsQuery = useQuery({
    queryKey: ["fixed-assets", includeDisposed],
    queryFn: () =>
      api.get<FixedAssetRow[]>(`/accounting/assets?include_disposed=${includeDisposed}`),
  });
  const assets = assetsQuery.data;

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

  // Pelepasan aset tidak bisa dibatalkan (jurnal laba/rugi pelepasan). Dulu
  // window.prompt(): input "Rp 1.500.000" -> Number(...) || 0 = 0 diam-diam.
  function askDispose(a: FixedAssetRow) {
    confirmDialog({
      title: `Lepas aset "${a.name}"?`,
      message: `Nilai buku ${formatRupiah(a.book_value)}. Aset ditandai dilepas dan jurnal laba/rugi pelepasan diposting. Tindakan ini tidak bisa dibatalkan.`,
      confirmLabel: "Lepas Aset",
      input: { label: "Hasil pelepasan (Rp) -- kosongkan bila tidak ada", placeholder: "mis. 1.500.000" },
      onConfirm: (raw) => {
        const proceeds = Number(raw.replace(/[^\d]/g, "")) || 0;
        disposeAsset.mutate(
          { id: a.id, proceeds },
          {
            onSuccess: () => toast.success(`Aset dilepas, hasil pelepasan ${formatRupiah(proceeds)}`),
            onError: (e) => toast.error(`Gagal melepas aset: ${(e as Error).message}`),
          }
        );
      },
    });
  }

  const assetColumns: Column<FixedAssetRow>[] = [
    { key: "name", header: "Nama", className: "font-medium", cell: (a) => a.name, sortValue: (a) => a.name },
    {
      key: "acq",
      header: "Perolehan",
      className: "whitespace-nowrap text-xs",
      cell: (a) => formatDate(a.acquisition_date),
      sortValue: (a) => a.acquisition_date,
    },
    {
      key: "cost",
      header: "Harga",
      numeric: true,
      cell: (a) => formatRupiah(a.cost),
      sortValue: (a) => a.cost,
      footer: formatRupiah((assets ?? []).reduce((sum, a) => sum + Number(a.cost), 0)),
    },
    {
      key: "life",
      header: "Umur",
      numeric: true,
      className: "text-xs",
      cell: (a) => `${a.useful_life_months} bln`,
      sortValue: (a) => a.useful_life_months,
    },
    {
      key: "acc",
      header: "Akumulasi Susut",
      numeric: true,
      cell: (a) => formatRupiah(a.accumulated_depreciation),
      sortValue: (a) => a.accumulated_depreciation,
      footer: formatRupiah((assets ?? []).reduce((sum, a) => sum + Number(a.accumulated_depreciation), 0)),
    },
    {
      key: "book",
      header: "Nilai Buku",
      numeric: true,
      className: "font-medium",
      cell: (a) => formatRupiah(a.book_value),
      sortValue: (a) => a.book_value,
      footer: formatRupiah((assets ?? []).reduce((sum, a) => sum + Number(a.book_value), 0)),
    },
    { key: "last", header: "Susut Terakhir", className: "text-xs", cell: (a) => a.last_depreciated_ym ?? "-" },
    {
      key: "aksi",
      header: "Aksi",
      cell: (a) =>
        a.disposed_at ? (
          <span className="pill p-gray">Dilepas {formatDate(a.disposed_at)}</span>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="text-xs font-medium hover:opacity-80"
              style={{ color: "var(--accent)" }}
              disabled={depreciateOne.isPending}
              onClick={() => depreciateOne.mutate({ id: a.id, year: depYear, month: depMonth })}
            >
              Susutkan
            </button>
            <button
              className="text-xs font-medium text-red-600 hover:opacity-80 dark:text-red-400"
              disabled={disposeAsset.isPending}
              onClick={() => askDispose(a)}
            >
              Lepas Aset…
            </button>
          </div>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <PeriodPicker
            value={{ year: depYear, month: depMonth }}
            onChange={(p) => {
              setDepYear(p.year);
              setDepMonth(p.month);
            }}
            label="periode susutan"
          />
          <button
            className="btn-secondary"
            disabled={depreciatePeriod.isPending}
            onClick={() => depreciatePeriod.mutate()}
          >
            Jalankan Susutan Periode Ini
          </button>
          <label className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-muted)" }}>
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
        <p className="text-sm text-red-600 dark:text-red-400">{(depreciateOne.error as Error).message}</p>
      )}
      {disposeAsset.error && (
        <p className="text-sm text-red-600 dark:text-red-400">{(disposeAsset.error as Error).message}</p>
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
            <p className="text-sm text-red-600 dark:text-red-400 sm:col-span-3">{(createAsset.error as Error).message}</p>
          )}
          <button type="submit" disabled={createAsset.isPending} className="btn sm:col-span-3">
            Simpan Aset
          </button>
        </form>
      )}

      <DataTable
        label="Aset tetap"
        rows={assets}
        columns={assetColumns}
        rowKey={(a) => a.id}
        query={assetsQuery}
        defaultSort={{ key: "acq", dir: "desc" }}
        emptyTitle="Belum ada aset tetap."
      />
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
  const billsQuery = useQuery({
    queryKey: ["purchase-bills", statusFilter],
    queryFn: () =>
      api.get<PurchaseBillRow[]>(`/accounting/purchases${statusFilter ? `?status=${statusFilter}` : ""}`),
  });
  const bills = billsQuery.data;

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


  function renderPayForm(b: PurchaseBillRow) {
    return (
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
                                  <p className="text-xs text-red-600 dark:text-red-400">{(payBill.error as Error).message}</p>
                                )}
                              </form>
    );
  }

  const billColumns: Column<PurchaseBillRow>[] = [
    {
      key: "no",
      header: "No. Tagihan",
      className: "font-mono text-xs",
      cell: (b) => b.bill_number ?? "-",
      sortValue: (b) => b.bill_number,
      footer: "Total",
    },
    { key: "vendor", header: "Vendor", cell: (b) => b.vendor_name, sortValue: (b) => b.vendor_name },
    {
      key: "date",
      header: "Tanggal",
      className: "whitespace-nowrap text-xs",
      cell: (b) => formatDate(b.entry_date),
      sortValue: (b) => b.entry_date,
    },
    {
      key: "due",
      header: "Jatuh Tempo",
      className: "whitespace-nowrap text-xs",
      cell: (b) => formatDate(b.due_date),
      sortValue: (b) => b.due_date,
    },
    {
      key: "total",
      header: "Jumlah",
      numeric: true,
      className: "font-medium",
      cell: (b) => formatRupiah(Number(b.amount) + Number(b.ppn_amount)),
      sortValue: (b) => Number(b.amount) + Number(b.ppn_amount),
      footer: formatRupiah((bills ?? []).reduce((sum, b) => sum + Number(b.amount) + Number(b.ppn_amount), 0)),
    },
    {
      key: "ppn",
      header: "PPN",
      numeric: true,
      cell: (b) => formatRupiah(b.ppn_amount),
      sortValue: (b) => Number(b.ppn_amount),
      footer: formatRupiah((bills ?? []).reduce((sum, b) => sum + Number(b.ppn_amount), 0)),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (b) => b.status,
      cell: (b) => {
        const st = BILL_STATUS_LABELS[b.status] ?? BILL_STATUS_LABELS.belum_dibayar;
        return <span className={st.cls}>{st.label}</span>;
      },
    },
    {
      key: "aksi",
      header: "Aksi",
      cell: (b) =>
        b.status === "belum_dibayar" ? (
          <button
            className="text-xs font-medium hover:opacity-80"
            style={{ color: "var(--accent)" }}
            onClick={() => setPayingId(payingId === b.id ? null : b.id)}
          >
            Bayar
          </button>
        ) : null,
    },
  ];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input w-auto" aria-label="Filter status tagihan">
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
            <p className="text-sm text-red-600 dark:text-red-400 sm:col-span-3">{(createBill.error as Error).message}</p>
          )}
          <button type="submit" disabled={createBill.isPending} className="btn sm:col-span-3">
            Simpan Bill
          </button>
        </form>
      )}

      <DataTable
        label="Tagihan vendor"
        rows={bills}
        columns={billColumns}
        rowKey={(b) => b.id}
        query={billsQuery}
        defaultSort={{ key: "date", dir: "desc" }}
        renderExpanded={(b) => (payingId === b.id ? renderPayForm(b) : null)}
        emptyTitle="Belum ada bill vendor."
      />
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
  const txsQuery = useQuery({
    queryKey: ["bank-transactions", year, month, reconciledFilter],
    queryFn: () => {
      const params = new URLSearchParams({ year: String(year) });
      if (month) params.set("month", String(month));
      if (reconciledFilter) params.set("reconciled", reconciledFilter);
      return api.get<BankTxRow[]>(`/accounting/cashbank/transactions?${params}`);
    },
  });
  const txs = txsQuery.data;

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


  const txColumns: Column<BankTxRow>[] = [
    {
      key: "date",
      header: "Tanggal",
      className: "whitespace-nowrap text-xs",
      cell: (t) => formatDate(t.tx_date),
      sortValue: (t) => t.tx_date,
    },
    {
      key: "type",
      header: "Tipe",
      cell: (t) => BANK_TX_LABELS[t.tx_type] ?? t.tx_type,
      sortValue: (t) => BANK_TX_LABELS[t.tx_type] ?? t.tx_type,
    },
    {
      key: "amount",
      header: "Jumlah",
      numeric: true,
      className: "font-medium",
      cell: (t) => formatRupiah(t.amount),
      sortValue: (t) => Number(t.amount),
    },
    { key: "desc", header: "Keterangan", cell: (t) => t.description ?? "-" },
    {
      key: "rec",
      header: "Rekonsiliasi",
      sortValue: (t) => (t.reconciled ? 1 : 0),
      cell: (t) =>
        t.reconciled ? (
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
        ),
    },
  ];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-24" aria-label="Tahun mutasi kas/bank" />
          <select
            value={month}
            onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : "")}
            className="input w-auto"
            aria-label="Bulan mutasi kas/bank"
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
            aria-label="Filter status rekonsiliasi"
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
            <p className="text-sm text-red-600 dark:text-red-400 sm:col-span-3">{(createTx.error as Error).message}</p>
          )}
          <button type="submit" disabled={createTx.isPending} className="btn sm:col-span-3">
            Simpan Transaksi
          </button>
        </form>
      )}

      <DataTable
        label="Transaksi kas dan bank"
        rows={txs}
        columns={txColumns}
        rowKey={(t) => t.id}
        query={txsQuery}
        defaultSort={{ key: "date", dir: "desc" }}
        pageSize={50}
        emptyTitle="Belum ada transaksi kas/bank periode ini."
      />
    </div>
  );
}
