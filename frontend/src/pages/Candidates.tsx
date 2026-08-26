import { FormEvent, Fragment, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { AiResultCard } from "../components/Ai";
import type { Screening } from "../components/Ai";
import { CalloutBlock, PageHeader } from "../components/notion";
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

// B1: pill palet hex Notion (index.css).
const BADGE_COLORS: Record<string, string> = {
  baru: "pill p-gray",
  screening: "pill p-blue",
  interview: "pill p-indigo",
  offered: "pill p-yellow",
  placed: "pill p-green",
  gagal: "pill p-red",
  arsip: "pill p-gray",
};

const STATUS_DOT: Record<string, string> = {
  baru: "#9f9f9f",
  screening: "#2383e2",
  interview: "#5b5bd6",
  offered: "#cb912f",
  placed: "#0f7b6c",
  gagal: "#e03e3e",
  arsip: "#787774",
};

export default function Candidates() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [view, setView] = useState<"tabel" | "papan">("tabel");
  const [aiCandidateId, setAiCandidateId] = useState<string | null>(null);
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

  const screenings = useQuery({
    queryKey: ["screenings", aiCandidateId],
    queryFn: () => api.get<Screening[]>(`/ai/candidates/${aiCandidateId}/screenings`),
    enabled: !!aiCandidateId,
  });

  const runScreening = useMutation({
    mutationFn: ({ id, joId }: { id: string; joId: string }) =>
      api.post<Screening>(`/ai/candidates/${id}/screen`, {
        job_order_id: joId || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["screenings", aiCandidateId] });
      invalidate();
    },
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader emoji="🧲" title="Database Kandidat" />
        <div className="flex items-center gap-2">
          <div className="flex overflow-hidden rounded text-sm" style={{ border: "1px solid var(--n-border)" }}>
            {(["tabel", "papan"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className="px-3 py-1.5 capitalize transition-colors"
                style={{
                  backgroundColor: view === v ? "var(--n-hover)" : "transparent",
                  color: view === v ? "var(--n-text)" : "var(--n-text-muted)",
                  fontWeight: view === v ? 500 : 400,
                }}
              >
                {view === v ? "☰ " : "▦ "}
                {v}
              </button>
            ))}
          </div>
          <button className="btn" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Tutup" : "+ Kandidat Baru"}
          </button>
        </div>
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

      {candidates?.length === 0 && view === "tabel" && (
        <CalloutBlock emoji="🌱" tone="info">
          Belum ada kandidat. Klik <b>"+ Kandidat Baru"</b> untuk mulai.
        </CalloutBlock>
      )}

      {view === "tabel" && (
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
                <th className="th">AI</th>
              </tr>
            </thead>
          <tbody className="divide-y divide-slate-100">
            {(candidates ?? []).map((c) => (
              <Fragment key={c.id}>
                <tr className="hover:bg-slate-50">
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
                    className={`cursor-pointer border-0 ${BADGE_COLORS[c.status]}`}
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
                <td className="td">
                  <button
                    className={`py-1 text-xs ${aiCandidateId === c.id ? "btn" : "btn-secondary"}`}
                    onClick={() => setAiCandidateId(aiCandidateId === c.id ? null : c.id)}
                  >
                    Screening
                  </button>
                </td>
              </tr>
                {aiCandidateId === c.id && (
                  <tr>
                    <td colSpan={7} className="bg-slate-50/60 px-4 py-4">
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-slate-700">
                            Screening AI: {c.full_name}
                          </span>
                          {!c.cv_file_name && (
                            <span className="badge border-0 bg-red-100 text-red-600">
                              CV belum diunggah — unggah dulu agar AI bisa menilai
                            </span>
                          )}
                          <form
                            className="ml-auto flex gap-1"
                            onSubmit={(e) => {
                              e.preventDefault();
                              const sel = e.currentTarget.elements.namedItem(
                                "jo"
                              ) as HTMLSelectElement;
                              runScreening.mutate({ id: c.id, joId: sel.value });
                            }}
                          >
                            <select name="jo" className="input w-auto py-1 text-xs">
                              <option value="">Tanpa job order (nilai umum)</option>
                              {(jobOrders ?? []).map((j) => (
                                <option key={j.id} value={j.id}>
                                  {j.title}
                                </option>
                              ))}
                            </select>
                            <button
                              className="btn py-1 text-xs"
                              disabled={runScreening.isPending || !c.cv_file_name}
                            >
                              {runScreening.isPending
                                ? "AI sedang menilai..."
                                : "Jalankan Screening"}
                            </button>
                          </form>
                        </div>
                        {runScreening.error && (
                          <p className="text-sm text-red-600">
                            {(runScreening.error as Error).message}
                          </p>
                        )}
                        {screenings.isLoading ? (
                          <p className="text-sm text-slate-400">Memuat riwayat...</p>
                        ) : (
                          <div className="space-y-2">
                            {(screenings.data ?? []).map((s) => (
                              <AiResultCard key={s.id} screening={s} />
                            ))}
                            {screenings.data?.length === 0 && (
                              <p className="text-sm text-slate-400">Belum ada hasil screening.</p>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {candidates?.length === 0 && (
              <tr>
                <td colSpan={7} className="td py-8 text-center text-slate-400">
                  Belum ada kandidat.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
      )}

      {view === "papan" && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STATUSES.map((stage) => {
            const cards = (candidates ?? []).filter((c) => c.status === stage);
            return (
              <div key={stage} className="w-64 shrink-0 rounded-md" style={{ backgroundColor: "var(--n-hover)" }}>
                <div className="flex items-center justify-between px-3 pt-3">
                  <span className="flex items-center gap-2 text-sm font-medium" style={{ color: "var(--n-text)" }}>
                    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: STATUS_DOT[stage] }} />
                    <span className="capitalize">{stage}</span>
                    <span style={{ color: "var(--n-text-muted)" }}>{cards.length}</span>
                  </span>
                </div>
                <div className="space-y-2 px-2 pb-3 pt-2">
                  {cards.map((c) => (
                    <div
                      key={c.id}
                      className="rounded-md p-3 shadow-sm transition-shadow hover:shadow"
                      style={{ backgroundColor: "var(--n-bg-elevated)", border: "1px solid var(--n-border)" }}
                    >
                      <p className="text-sm font-medium" style={{ color: "var(--n-text)" }}>
                        {c.full_name}
                      </p>
                      <p className="mt-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
                        {c.city ?? "—"} · {formatRupiah(c.expected_salary)}
                      </p>
                      {c.cv_file_name && <p className="mt-1 text-xs text-indigo-600">📎 {c.cv_file_name}</p>}
                      <div className="mt-2 flex items-center justify-between text-xs" onClick={(e) => e.stopPropagation()}>
                        <button
                          disabled={STATUSES.indexOf(c.status) === 0}
                          onClick={() => changeStatus.mutate({ id: c.id, status: STATUSES[STATUSES.indexOf(c.status) - 1] })}
                          className="rounded px-1.5 py-0.5 disabled:opacity-25"
                          style={{ border: "1px solid var(--n-border)" }}
                        >
                          ←
                        </button>
                        <select
                          value={c.status}
                          onChange={(e) => changeStatus.mutate({ id: c.id, status: e.target.value })}
                          className="cursor-pointer rounded bg-transparent text-xs capitalize"
                          style={{ color: "var(--n-text-muted)", border: "none", outline: "none" }}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                        <button
                          disabled={STATUSES.indexOf(c.status) === STATUSES.length - 1}
                          onClick={() => changeStatus.mutate({ id: c.id, status: STATUSES[STATUSES.indexOf(c.status) + 1] })}
                          className="rounded px-1.5 py-0.5 disabled:opacity-25"
                          style={{ border: "1px solid var(--n-border)" }}
                        >
                          →
                        </button>
                      </div>
                    </div>
                  ))}
                  {cards.length === 0 && <p className="px-1 py-3 text-center text-xs" style={{ color: "var(--n-text-muted)" }}>Kosong</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {candidates?.length === 0 && view === "papan" && (
        <CalloutBlock emoji="🌱" tone="info">
          Belum ada kandidat untuk ditampilkan di papan.
        </CalloutBlock>
      )}
    </div>
  );
}
