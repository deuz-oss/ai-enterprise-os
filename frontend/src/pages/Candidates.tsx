import { FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import type { JobOrder } from "./JobOrders";

interface Candidate {
  id: string;
  full_name: string;
  city: string | null;
  expected_salary: number | null;
  status: string;
  cv_file_name: string | null;
}

const STATUSES = ["baru", "screening", "interview", "offered", "placed", "gagal", "arsip"];

const BADGE_COLORS: Record<string, string> = {
  baru: "bg-slate-100 text-slate-600",
  screening: "bg-blue-100 text-blue-700",
  interview: "bg-indigo-100 text-indigo-700",
  offered: "bg-amber-100 text-amber-700",
  placed: "bg-emerald-100 text-emerald-700",
  gagal: "bg-red-100 text-red-600",
  arsip: "bg-slate-100 text-slate-400",
};

export default function Candidates() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const cvRef = useRef<HTMLInputElement>(null);
  const { data: candidates } = useQuery({
    queryKey: ["candidates"],
    queryFn: () => api.get<Candidate[]>("/recruitment/candidates"),
  });
  const { data: jobOrders } = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["candidates"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const createCandidate = useMutation({
    mutationFn: async ({ body, cv }: { body: Record<string, unknown>; cv: File | null }) => {
      const created = await api.post<{ id: string }>("/recruitment/candidates", body);
      if (cv && cvRef.current?.files?.[0]) {
        const fd = new FormData();
        fd.append("file", cv);
        await api.upload(`/recruitment/candidates/${created.id}/cv`, fd);
      }
      return created;
    },
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const changeStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/recruitment/candidates/${id}`, { status }),
    onSuccess: invalidate,
  });

  const place = useMutation({
    mutationFn: ({ candidateId, joId }: { candidateId: string; joId: string }) =>
      api.post("/recruitment/placements", { candidate_id: candidateId, job_order_id: joId }),
    onSuccess: invalidate,
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createCandidate.mutate({
      body: {
        full_name: form.get("full_name"),
        phone: form.get("phone") || null,
        city: form.get("city") || null,
        education: form.get("education") || null,
        expected_salary: Number(form.get("expected_salary")) || null,
        source: form.get("source") || null,
      },
      cv: cvRef.current?.files?.[0] ?? null,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Database Kandidat</h1>
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Kandidat Baru"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input name="full_name" required placeholder="Nama lengkap *" className="input" />
          <input name="phone" placeholder="Telepon" className="input" />
          <input name="city" placeholder="Kota" className="input" />
          <input name="education" placeholder="Pendidikan terakhir" className="input" />
          <input name="expected_salary" type="number" placeholder="Ekspektasi gaji (Rp)" className="input" />
          <input name="source" placeholder="Sumber (referral/loker/dll)" className="input" />
          <input ref={cvRef} type="file" accept=".pdf,.doc,.docx" className="input" />
          <button
            type="submit"
            disabled={createCandidate.isPending}
            className="btn sm:col-span-3"
          >
            Simpan Kandidat
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Nama</th>
              <th className="th">Kota</th>
              <th className="th">Ekspektasi</th>
              <th className="th">CV</th>
              <th className="th">Status</th>
              <th className="th">Place ke Job Order</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(candidates ?? []).map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="td font-medium">{c.full_name}</td>
                <td className="td">{c.city ?? "-"}</td>
                <td className="td">{formatRupiah(c.expected_salary)}</td>
                <td className="td">
                  {c.cv_file_name ? (
                    <a
                      href="#"
                      onClick={async (e) => {
                        e.preventDefault();
                        const { url } = await api.get<{ url: string }>(
                          `/recruitment/candidates/${c.id}/cv-download-url`
                        );
                        window.open(url, "_blank");
                      }}
                      className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
                    >
                      {c.cv_file_name}
                    </a>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="td">
                  <select
                    value={c.status}
                    onChange={(e) => changeStatus.mutate({ id: c.id, status: e.target.value })}
                    className={`badge cursor-pointer border-0 ${BADGE_COLORS[c.status]}`}
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="td">
                  <form
                    className="flex gap-1"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const sel = e.currentTarget.elements.namedItem("jo") as HTMLSelectElement;
                      if (sel.value) place.mutate({ candidateId: c.id, joId: sel.value });
                    }}
                  >
                    <select name="jo" className="input w-auto py-1 text-xs">
                      <option value="">-- pilih --</option>
                      {(jobOrders ?? [])
                        .filter((j) => !["filled", "closed"].includes(j.status))
                        .map((j) => (
                          <option key={j.id} value={j.id}>
                            {j.title}
                          </option>
                        ))}
                    </select>
                    <button className="btn-secondary py-1 text-xs">Usulkan</button>
                  </form>
                </td>
              </tr>
            ))}
            {candidates?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center text-slate-400">
                  Belum ada kandidat.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
