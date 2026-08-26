import { FormEvent, useState } from "react";
import { PageHeader } from "../components/notion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { AiResultCard, ScoreBadge } from "../components/Ai";
import type { MatchResult } from "../components/Ai";
import type { ClientRow } from "./Clients";

export interface JobOrder {
  id: string;
  client_id: string;
  title: string;
  headcount: number;
  salary_min: number | null;
  salary_max: number | null;
  due_date: string | null;
  status: string;
}

const STATUSES = ["open", "screening", "interview_klien", "offering", "filled", "closed"];

// B1: pill palet hex Notion (index.css).
const BADGE_COLORS: Record<string, string> = {
  open: "pill p-blue",
  screening: "pill p-indigo",
  interview_klien: "pill p-violet",
  offering: "pill p-yellow",
  filled: "pill p-green",
  closed: "pill p-gray",
};

export default function JobOrders() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const { data: jobOrders } = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });
  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["job-orders"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const createJO = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/recruitment/job-orders", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const changeStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/recruitment/job-orders/${id}`, { status }),
    onSuccess: invalidate,
  });

  const match = useMutation({
    mutationFn: (id: string) => api.post<MatchResult>(`/ai/job-orders/${id}/match`),
    onSuccess: (data) => setMatchResult(data),
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createJO.mutate({
      client_id: form.get("client_id"),
      title: form.get("title"),
      headcount: Number(form.get("headcount")) || 1,
      requirements: form.get("requirements") || null,
      salary_min: Number(form.get("salary_min")) || null,
      salary_max: Number(form.get("salary_max")) || null,
      due_date: form.get("due_date") || null,
    });
  }

  const clientName = (id: string) => clients?.find((c) => c.id === id)?.name ?? "-";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader emoji="🧲" title="Job Orders" />
        <button className="btn" onClick={() => setShowForm(!showForm)} disabled={!clients?.length}>
          {showForm ? "Tutup" : "+ Job Order Baru"}
        </button>
      </div>

      {!clients?.length && (
        <p className="text-sm text-[var(--n-text-muted)]">Tambahkan klien terlebih dahulu untuk membuat job order.</p>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
          <select name="client_id" required className="input">
            <option value="">-- Pilih klien --</option>
            {(clients ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <input name="title" required placeholder="Posisi *" className="input" />
          <input name="headcount" type="number" min={1} defaultValue={1} placeholder="Jumlah" className="input" />
          <input name="salary_min" type="number" placeholder="Gaji min (Rp)" className="input" />
          <input name="salary_max" type="number" placeholder="Gaji max (Rp)" className="input" />
          <input name="due_date" type="date" placeholder="Target tanggal" className="input" />
          <input name="requirements" placeholder="Kualifikasi" className="input sm:col-span-3" />
          <button type="submit" disabled={createJO.isPending} className="btn sm:col-span-3">
            Simpan Job Order
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-[var(--n-border)] bg-[var(--n-hover)]">
            <tr>
              <th className="th">Posisi</th>
              <th className="th">Klien</th>
              <th className="th">Kebutuhan</th>
              <th className="th">Range Gaji</th>
              <th className="th">Status</th>
              <th className="th">AI Matching</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--n-border)]">
            {(jobOrders ?? []).map((jo) => (
              <tr key={jo.id} className="hover:bg-[var(--n-hover)]">
                <td className="td font-medium">{jo.title}</td>
                <td className="td">{clientName(jo.client_id)}</td>
                <td className="td">{jo.headcount} orang</td>
                <td className="td">
                  {formatRupiah(jo.salary_min)} – {formatRupiah(jo.salary_max)}
                </td>
                <td className="td">
                  <select
                    value={jo.status}
                    onChange={(e) => changeStatus.mutate({ id: jo.id, status: e.target.value })}
                    className={`cursor-pointer border-0 ${BADGE_COLORS[jo.status]}`}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="td">
                  <button
                    className="btn-secondary py-1 text-xs"
                    disabled={match.isPending}
                    onClick={() => match.mutate(jo.id)}
                  >
                    {match.isPending ? "AI menilai..." : "Cari Kandidat"}
                  </button>
                </td>
              </tr>
            ))}
            {jobOrders?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center text-[var(--n-text-muted)]">
                  Belum ada job order.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {(match.isPending || match.error || matchResult) && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-[var(--n-text)]">Hasil AI Matching</h2>
            {matchResult && (
              <span className="text-xs text-[var(--n-text-muted)]">
                {matchResult.evaluated} kandidat dinilai
                {matchResult.reused > 0 && ` · ${matchResult.reused} memakai hasil sebelumnya`}
              </span>
            )}
          </div>
          {match.isPending && (
            <p className="text-sm text-[var(--n-text-muted)]">
              AI sedang menilai kandidat (bisa memakan waktu beberapa saat)...
            </p>
          )}
          {match.error && (
            <p className="text-sm text-red-600">{(match.error as Error).message}</p>
          )}
          {matchResult && (
            <ol className="space-y-2">
              {matchResult.results.map((item, idx) => (
                <li key={item.candidate.id} className="flex gap-3">
                  <span className="w-6 pt-4 text-right text-sm font-bold text-[var(--n-text-muted)]">
                    {idx + 1}.
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[var(--n-text)]">
                      {item.candidate.full_name}{" "}
                      <span className={`ml-1 text-xs`}>
                        (skor <ScoreBadge score={item.screening.score} />)
                      </span>
                    </p>
                    <AiResultCard screening={item.screening} />
                  </div>
                </li>
              ))}
              {matchResult.results.length === 0 && (
                <li className="text-sm text-[var(--n-text-muted)]">
                  Tidak ada kandidat aktif untuk job order ini.
                </li>
              )}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
