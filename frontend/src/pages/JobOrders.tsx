import { FormEvent, useState } from "react";
import { Magnet } from "lucide-react";
import { PageHeader } from "../components/notion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { ScoreBadge } from "../components/Ai";
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
  request_id: string | null;
  request_date: string;
  area: string | null;
  contract_duration_months: number | null;
  gross_salary: number | null;
  business_status: string;
  requires_ojt: boolean;
  is_stale: boolean;
}

interface MatchCandidateRow {
  id: string;
  full_name: string;
  city: string | null;
  expected_salary: number | null;
}

interface MatchItem {
  candidate_id: string;
  match_score: number;
  explain: string;
  missing: string[];
}

const BUSINESS_STATUSES = ["dibuka", "ditahan", "dibatalkan", "terisi"];

const BUSINESS_STATUS_COLORS: Record<string, string> = {
  dibuka: "pill p-blue",
  ditahan: "pill p-yellow",
  dibatalkan: "pill p-red",
  terisi: "pill p-green",
};

export default function JobOrders() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [matchJoId, setMatchJoId] = useState<string | null>(null);
  const [matchResults, setMatchResults] = useState<MatchItem[] | null>(null);
  const { data: jobOrders } = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });
  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const { data: matchCandidates } = useQuery({
    queryKey: ["candidates-for-match"],
    queryFn: () => api.get<MatchCandidateRow[]>("/recruitment/candidates"),
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

  const changeBusinessStatus = useMutation({
    mutationFn: ({ id, business_status }: { id: string; business_status: string }) =>
      api.patch(`/recruitment/job-orders/${id}`, { business_status }),
    onSuccess: invalidate,
  });

  const match = useMutation({
    mutationFn: (id: string) =>
      api.post<MatchItem[]>(`/recruitment/job-orders/${id}/match`, { top_k: 20 }),
    onSuccess: (data) => setMatchResults(data),
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
      request_id: form.get("request_id") || null,
      request_date: form.get("request_date") || null,
      area: form.get("area") || null,
      contract_duration_months: Number(form.get("contract_duration_months")) || null,
      gross_salary: Number(form.get("gross_salary")) || null,
      requires_ojt: form.get("requires_ojt") === "on",
    });
  }

  const clientName = (id: string) => clients?.find((c) => c.id === id)?.name ?? "-";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader icon={Magnet} title="Job Orders" />
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
          <input
            name="request_id"
            placeholder="Request ID (kosongkan untuk auto-generate)"
            className="input"
          />
          <input
            name="request_date"
            type="date"
            defaultValue={new Date().toISOString().slice(0, 10)}
            title="Request Date"
            className="input"
          />
          <input name="area" placeholder="Area" className="input" />
          <input
            name="contract_duration_months"
            type="number"
            min={1}
            placeholder="Durasi kontrak (bulan)"
            className="input"
          />
          <input name="gross_salary" type="number" placeholder="Gross Salary (Rp)" className="input" />
          <label className="input flex items-center gap-2 text-sm">
            <input name="requires_ojt" type="checkbox" className="h-4 w-4" />
            Butuh OJT (On Job Training)
          </label>
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
              <th className="th">Request ID</th>
              <th className="th">Posisi</th>
              <th className="th">Klien</th>
              <th className="th">Area</th>
              <th className="th">Kebutuhan</th>
              <th className="th">Range Gaji</th>
              <th className="th">Status</th>
              <th className="th">AI Matching</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--n-border)]">
            {(jobOrders ?? []).map((jo) => (
              <tr key={jo.id} className="hover:bg-[var(--n-hover)]">
                <td className="td">
                  {jo.request_id ?? "-"}
                  {jo.is_stale && (
                    <span
                      className="pill p-red ml-1 text-[10px]"
                      title={`Request Date: ${jo.request_date} — belum filled >=30 hari`}
                    >
                      &gt;30 hari
                    </span>
                  )}
                </td>
                <td className="td font-medium">{jo.title}</td>
                <td className="td">{clientName(jo.client_id)}</td>
                <td className="td">{jo.area ?? "-"}</td>
                <td className="td">{jo.headcount} orang</td>
                <td className="td">
                  {formatRupiah(jo.salary_min)} – {formatRupiah(jo.salary_max)}
                </td>
                <td className="td">
                  <select
                    value={jo.business_status}
                    onChange={(e) =>
                      changeBusinessStatus.mutate({ id: jo.id, business_status: e.target.value })
                    }
                    className={`cursor-pointer border-0 ${BUSINESS_STATUS_COLORS[jo.business_status]}`}
                  >
                    {BUSINESS_STATUSES.map((s) => (
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
                    onClick={() => {
                      setMatchJoId(jo.id);
                      match.mutate(jo.id);
                    }}
                  >
                    {match.isPending && matchJoId === jo.id ? "AI menilai..." : "Cari Kandidat"}
                  </button>
                </td>
              </tr>
            ))}
            {jobOrders?.length === 0 && (
              <tr>
                <td colSpan={8} className="td py-8 text-center text-[var(--n-text-muted)]">
                  Belum ada job order.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {(match.isPending || match.error || matchResults) && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-[var(--n-text)]">
              Hasil AI Matching — Talent Cloud
            </h2>
            {matchJoId && (
              <span className="text-xs text-[var(--n-text-muted)]">
                {jobOrders?.find((j) => j.id === matchJoId)?.title}
              </span>
            )}
          </div>
          <p className="text-[11px] text-[var(--n-text-muted)]">
            Matching native Talent Cloud — dikenakan 2k per pencarian job order, bukan per
            kandidat.
          </p>
          {match.isPending && (
            <p className="text-sm text-[var(--n-text-muted)]">
              AI sedang menilai kandidat (bisa memakan waktu beberapa saat)...
            </p>
          )}
          {match.error && (
            <p className="text-sm text-red-600">{(match.error as Error).message}</p>
          )}
          {matchResults && (
            <ol className="space-y-2">
              {matchResults.map((item, idx) => {
                const cand = matchCandidates?.find((c) => c.id === item.candidate_id);
                return (
                  <li key={item.candidate_id} className="flex gap-3">
                    <span className="w-6 pt-0.5 text-right text-sm font-bold text-[var(--n-text-muted)]">
                      {idx + 1}.
                    </span>
                    <div className="min-w-0 flex-1 rounded-lg border p-3" style={{ borderColor: "var(--n-border)" }}>
                      <p className="text-sm font-medium text-[var(--n-text)]">
                        {cand?.full_name ?? item.candidate_id}{" "}
                        <span className="ml-1 text-xs">
                          (skor <ScoreBadge score={item.match_score} />/100)
                        </span>
                      </p>
                      <p className="text-xs text-[var(--n-text-muted)]">
                        {cand?.city ?? "-"}
                        {cand?.expected_salary ? ` · ${formatRupiah(cand.expected_salary)}` : ""}
                      </p>
                      <p className="mt-1 text-sm text-[var(--n-text)]">{item.explain}</p>
                      {item.missing.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {item.missing.map((m) => (
                            <span key={m} className="pill p-red text-[10px]">
                              {m}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
              {matchResults.length === 0 && (
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
