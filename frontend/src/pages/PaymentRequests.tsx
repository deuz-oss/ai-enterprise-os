import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { PageHeader } from "../components/notion";

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
}

const STATUS_BADGE: Record<string, string> = {
  diajukan: "bg-slate-100 text-slate-600",
  menunggu_atasan: "bg-amber-100 text-amber-700",
  disetujui_atasan: "bg-emerald-100 text-emerald-700",
  dieksekusi: "bg-blue-100 text-blue-700",
  ditolak: "bg-red-100 text-red-600",
};

export default function PaymentRequests() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");

  const prs = useQuery({
    queryKey: ["payment-requests", statusFilter],
    queryFn: () =>
      api.get<PrRow[]>(
        `/payment-requests${statusFilter ? `?status=${statusFilter}` : ""}`
      ),
  });

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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader
          emoji="🧾"
          title="Payment Request"
          subtitle="Diajukan → Menunggu Atasan (management) → Disetujui → Dieksekusi Finance"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="input w-auto"
        >
          <option value="">Semua status</option>
          {Object.keys(STATUS_BADGE).map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)" }}>
            <tr>
              <th className="th">Nomor</th>
              <th className="th">Jenis</th>
              <th className="th">Jumlah</th>
              <th className="th">Deskripsi</th>
              <th className="th">Status</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(prs.data ?? []).map((p) => (
              <tr key={p.id}>
                <td className="td font-mono text-xs font-medium">{p.pr_number}</td>
                <td className="td capitalize">{p.pr_type}</td>
                <td className="td font-semibold">{formatRupiah(Number(p.amount))}</td>
                <td className="td max-w-xs truncate">{p.description ?? "-"}</td>
                <td className="td">
                  <span className={`badge ${STATUS_BADGE[p.status] ?? ""}`}>
                    {p.status.replace("_", " ")}
                  </span>
                  {p.decision_note && (
                    <p className="mt-0.5 text-[11px]" style={{ color: "var(--n-text-muted)" }}>
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
                    <span style={{ color: "var(--n-text-muted)" }}>—</span>
                  )}
                </td>
              </tr>
            ))}
            {prs.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada payment request. Buat dari halaman Payroll setelah run difinalisasi.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {act.error && (
          <p className="px-4 pb-3 text-sm text-red-600">{(act.error as Error).message}</p>
        )}
      </div>
    </div>
  );
}
