import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { CheckCircle2, ClipboardList, Clock, Wallet } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { KpiCard, PillTabs, type PillTab } from "../components/ui";
import { Pagination } from "../components/Pagination";

interface PrDecision {
  step_no: number;
  approver_id: string;
  approved: boolean;
  note: string | null;
  decided_at: string;
}

interface PrRow {
  id: string;
  pr_number: string;
  pr_type: string;
  payroll_run_id: string | null;
  amount: number;
  description: string | null;
  status: string;
  decision_note: string | null;
  created_at: string;
  progress: {
    total_steps: number;
    current_step: number | null;
    pending_step: number | null;
    decisions: PrDecision[];
  };
}

interface ChainStep {
  seq: number;
  approver_id: string | null;
  approver_name: string | null;
  approver_role: string | null;
}

const STATUS_BADGE: Record<string, string> = {
  diajukan: "pill p-gray",
  menunggu_atasan: "pill p-yellow",
  disetujui_atasan: "pill p-green",
  dieksekusi: "pill p-blue",
  ditolak: "pill p-red",
};

const ROLE_OPTIONS = [
  { value: "management", label: "Management" },
  { value: "finance", label: "Finance" },
  { value: "hr", label: "HR" },
  { value: "operations", label: "Operations" },
  { value: "business_dev", label: "Business Dev" },
  { value: "recruiter", label: "Recruiter" },
];

function ApprovalChainPanel() {
  const qc = useQueryClient();
  const [rows, setRows] = useState<{ kind: "role"; role: string }[]>([]);
  const [dirty, setDirty] = useState(false);
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
  });
  const canEdit = me.data?.role === "admin" || me.data?.role === "management";
  const chain = useQuery({
    queryKey: ["pr-chain"],
    queryFn: () => api.get<ChainStep[]>("/payment-requests/approval-chain"),
  });

  const save = useMutation({
    mutationFn: (steps: { approver_role?: string; approver_id?: string }[]) =>
      api.put<{ steps: ChainStep[] }>("/payment-requests/approval-chain", { steps }),
    onSuccess: () => {
      setDirty(false);
      setRows([]);
      void qc.invalidateQueries({ queryKey: ["pr-chain"] });
      void qc.invalidateQueries({ queryKey: ["payment-requests"] });
    },
  });

  const current: { kind: "role"; role: string }[] =
    dirty || rows.length > 0
      ? rows
      : (chain.data ?? []).map((s) => ({ kind: "role" as const, role: s.approver_role ?? "" }));

  const update = (idx: number, role: string) => {
    const next = [...current];
    next[idx] = { kind: "role", role };
    setRows(next);
    setDirty(true);
  };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">Rantai Approval</h3>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Urutan tahap persetujuan PR per tenant. Kosong = management/admin mana pun memutus.
          </p>
        </div>
        {canEdit && (
          <div className="flex gap-2 text-xs">
            <button
              onClick={() => {
                setRows([...current, { kind: "role", role: "management" }]);
                setDirty(true);
              }}
              className="font-medium text-emerald-700 hover:text-emerald-900"
            >
              + Tahap
            </button>
            <button
              onClick={() => {
                setRows(current.slice(0, -1));
                setDirty(true);
              }}
              disabled={current.length === 0}
              className="font-medium hover:opacity-80 disabled:opacity-40"
              style={{ color: "var(--text-muted)" }}
            >
              − Hapus Terakhir
            </button>
          </div>
        )}
      </div>

      <ol className="mt-3 space-y-1.5">
        {(chain.data ?? []).map((s) => (
          <li key={s.seq} className="text-xs flex items-center gap-2">
            <span
              className="inline-flex h-5 w-5 items-center justify-center rounded-full font-semibold"
              style={{ backgroundColor: "var(--hover)", color: "var(--text)" }}
            >
              {s.seq}
            </span>
            <span>{s.approver_name ?? ROLE_OPTIONS.find((r) => r.value === s.approver_role)?.label ?? s.approver_role}</span>
          </li>
        ))}
        {(chain.data?.length ?? 0) === 0 && !dirty && (
          <li className="text-xs italic" style={{ color: "var(--text-muted)" }}>
            Belum dikonfigurasi — satu tahap (legacy).
          </li>
        )}
      </ol>

      {canEdit && dirty && (
        <div className="mt-3 space-y-2 border-t pt-3" style={{ borderColor: "var(--border)" }}>
          {current.map((row, idx) => (
            <div key={idx} className="flex items-center gap-2 text-xs">
              <span className="w-12">Tahap {idx + 1}</span>
              <select
                value={row.role}
                onChange={(e) => update(idx, e.target.value)}
                className="input w-auto py-1 text-xs"
              >
                {ROLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    Peran: {o.label}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button
              onClick={() =>
                save.mutate(
                  current.map((r) => ({ approver_role: r.role })),
                )
              }
              disabled={save.isPending || current.some((r) => !r.role)}
              className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-40"
            >
              Simpan Rantai
            </button>
            <button
              onClick={() => {
                setRows([]);
                setDirty(false);
              }}
              className="px-2 py-1 text-xs hover:opacity-80"
              style={{ color: "var(--text-muted)" }}
            >
              Batal
            </button>
          </div>
          {save.error && (
            <p className="text-xs text-red-600">{(save.error as Error).message}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function PaymentRequests() {
  const qc = useQueryClient();
  // Tab/Pill filter (§1.5) butuh count tiap status sekaligus -- diambil
  // sekali (limit besar, endpoint yang sama) lalu difilter+dipaginasi di
  // klien, bukan 5x query terpisah per status.
  const [statusFilter, setStatusFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const pageLimit = 50;

  const prs = useQuery({
    queryKey: ["payment-requests"],
    queryFn: () => api.getPaged<PrRow>(`/payment-requests?limit=1000&offset=0`),
  });
  const allPrs = prs.data?.data ?? [];
  const filteredPrs = useMemo(
    () => allPrs.filter((p) => !statusFilter || p.status === statusFilter),
    [allPrs, statusFilter]
  );
  const prRows = filteredPrs.slice(offset, offset + pageLimit);
  const prTotal = filteredPrs.length;
  const statusTabs: PillTab[] = [
    { key: "", label: "Semua", count: allPrs.length },
    ...Object.keys(STATUS_BADGE).map((s) => {
      const label = s.replace("_", " ");
      return {
        key: s,
        label: label[0].toUpperCase() + label.slice(1),
        count: allPrs.filter((p) => p.status === s).length,
      };
    }),
  ];
  const awaitingCount = allPrs.filter((p) => p.status === "diajukan" || p.status === "menunggu_atasan").length;
  const readyToExecuteCount = allPrs.filter((p) => p.status === "disetujui_atasan").length;
  const outstandingTotal = allPrs
    .filter((p) => p.status !== "dieksekusi" && p.status !== "ditolak")
    .reduce((sum, p) => sum + Number(p.amount), 0);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["payment-requests"] });

  const act = useMutation({
    mutationFn: ({ id, action, note }: { id: string; action: string; note?: string }) =>
      api.post(
        `/payment-requests/${id}/${action}`,
        note ? { note } : {}
      ),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardList}
        title="Payment Request"
        subtitle="Diajukan → Menunggu Atasan (rantai approval per tenant) → Disetujui → Dieksekusi Finance"
      />

      <ApprovalChainPanel />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Payment Request" value={allPrs.length} icon={ClipboardList} iconTone="info" />
        <KpiCard
          label="Menunggu Persetujuan"
          value={awaitingCount}
          icon={Clock}
          iconTone="warning"
          badge={awaitingCount > 0 ? { label: "Perlu Tindakan", tone: "warning" } : undefined}
        />
        <KpiCard label="Siap Dieksekusi" value={readyToExecuteCount} icon={CheckCircle2} iconTone="accent" />
        <KpiCard label="Total Nilai Outstanding" value={formatRupiah(outstandingTotal)} icon={Wallet} iconTone="neutral" />
      </div>

      <PillTabs
        tabs={statusTabs}
        value={statusFilter}
        onChange={(k) => {
          setStatusFilter(k);
          setOffset(0);
        }}
      />

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--hover)" }}>
            <tr>
              <th className="th">Nomor</th>
              <th className="th">Jenis</th>
              <th className="th">Jumlah</th>
              <th className="th">Deskripsi</th>
              <th className="th">Status</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {prRows.map((p) => (
              <tr key={p.id}>
                <td className="td font-mono text-xs font-medium">{p.pr_number}</td>
                <td className="td capitalize">{p.pr_type}</td>
                <td className="td font-semibold">{formatRupiah(Number(p.amount))}</td>
                <td className="td max-w-xs truncate">{p.description ?? "-"}</td>
                <td className="td">
                  <span className={`${STATUS_BADGE[p.status] ?? "pill p-gray"}`}>
                    {p.status.replace("_", " ")}
                  </span>
                  {p.progress?.total_steps > 0 &&
                    (p.status === "menunggu_atasan" || p.status === "disetujui_atasan") && (
                      <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                        Tahap{" "}
                        {Math.min(p.progress.decisions.filter((d) => d.approved).length + 1, p.progress.total_steps)}
                        /{p.progress.total_steps}
                        {p.progress.decisions.some((d) => !d.approved) && " · ditolak di rantai"}
                      </p>
                    )}
                  {p.decision_note && (
                    <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                      {p.decision_note}
                    </p>
                  )}
                </td>
                <td className="td whitespace-nowrap text-xs">
                  {(p.status === "diajukan" || p.status === "menunggu_atasan") && (
                    <>
                      <button
                        onClick={() => act.mutate({ id: p.id, action: "approve" })}
                        disabled={act.isPending}
                        className="font-medium text-emerald-600 hover:text-emerald-800"
                      >
                        Setujui
                      </button>
                      {" · "}
                      <button
                        onClick={() => {
                          const note = window.prompt("Catatan penolakan (wajib):");
                          if (note) act.mutate({ id: p.id, action: "reject", note });
                        }}
                        disabled={act.isPending}
                        className="font-medium text-rose-600 hover:text-rose-800"
                      >
                        Tolak
                      </button>
                      {" · "}
                    </>
                  )}
                  {p.status === "disetujui_atasan" ? (
                    <button
                      onClick={() => act.mutate({ id: p.id, action: "execute" })}
                      disabled={act.isPending}
                      className="font-medium text-blue-600 hover:text-blue-800"
                    >
                      Eksekusi Pembayaran
                    </button>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>—</span>
                  )}
                </td>
              </tr>
            ))}
            {prRows.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  {allPrs.length === 0
                    ? "Belum ada payment request. Buat dari halaman Payroll setelah run difinalisasi."
                    : "Tidak ada payment request untuk status ini."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <Pagination offset={offset} limit={pageLimit} total={prTotal} onOffsetChange={setOffset} />
        {act.error && (
          <p className="px-4 pb-3 text-sm text-red-600">{(act.error as Error).message}</p>
        )}
      </div>
    </div>
  );
}
