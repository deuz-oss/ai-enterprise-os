import { FormEvent, useState } from "react";
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

const BADGE_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-700",
  screening: "bg-indigo-100 text-indigo-700",
  interview_klien: "bg-violet-100 text-violet-700",
  offering: "bg-amber-100 text-amber-700",
  filled: "bg-emerald-100 text-emerald-700",
  closed: "bg-slate-100 text-slate-500",
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
        <h1 className="text-2xl font-bold text-slate-800">Job Orders</h1>
        <button className="btn" onClick={() => setShowForm(!showForm)} disabled={!clients?.length}>
          {showForm ? "Tutup" : "+ Job Order Baru"}
        </button>
      </div>

      {!clients?.length && (
        <p className="text-sm text-slate-500">Tambahkan klien terlebih dahulu untuk membuat job order.</p>
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
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Posisi</th>
              <th className="th">Klien</th>
              <th className="th">Kebutuhan</th>
              <th className="th">Range Gaji</th>
              <th className="th">Status</th>
              <th className="th">AI Matching</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(jobOrders ?? []).map((jo) => (
              <tr key={jo.id} className="hover:bg-slate-50">
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
                    className={`badge cursor-pointer border-0 ${BADGE_COLORS[jo.status]}`}
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
                <td colSpan={6} className="td py-8 text-center text-slate-400">
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
            <h2 className="text-lg font-semibold text-slate-800">Hasil AI Matching</h2>
            {matchResult && (
              <span className="text-xs text-slate-400">
                {matchResult.evaluated} kandidat dinilai
                {matchResult.reused > 0 && ` · ${matchResult.reused} memakai hasil sebelumnya`}
              </span>
            )}
          </div>
          {match.isPending && (
            <p className="text-sm text-slate-500">
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
                  <span className="w-6 pt-4 text-right text-sm font-bold text-slate-400">
                    {idx + 1}.
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-700">
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
                <li className="text-sm text-slate-400">
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
