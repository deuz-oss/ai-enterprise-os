import { FormEvent, Fragment, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { AiResultCard } from "../components/Ai";
import type { Screening } from "../components/Ai";
import { ChevronLeft, ChevronRight, LayoutGrid, List, Paperclip, Users as UsersIcon } from "lucide-react";
import { CalloutBlock, PageHeader } from "../components/notion";
import { Pagination } from "../components/Pagination";
import type { JobOrder } from "./JobOrders";

interface Candidate {
  id: string;
  full_name: string;
  city: string | null;
  expected_salary: number | null;
  status: string;
  cv_file_name: string | null;
}

interface Interview {
  id: string;
  candidate_id: string;
  job_order_id: string;
  interviewer_id: string | null;
  scheduled_at: string;
  location: string | null;
  meeting_url: string | null;
  status: string;
  interview_type: string;
  feedback: string | null;
  score: number | null;
}

interface UserOption {
  id: string;
  full_name: string;
}

interface Placement {
  id: string;
  candidate_id: string;
  job_order_id: string;
  status: string;
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
  const [interviewCandidateId, setInterviewCandidateId] = useState<string | null>(null);
  const [onboardCandidateId, setOnboardCandidateId] = useState<string | null>(null);
  const [offeringCandidateId, setOfferingCandidateId] = useState<string | null>(null);
  const cvRef = useRef<HTMLInputElement>(null);
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const pageLimit = 50;
  const { data: candidatesPage } = useQuery({
    queryKey: ["candidates", offset, q, statusFilter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(pageLimit), offset: String(offset) });
      if (q) params.set("q", q);
      if (statusFilter) params.set("candidate_status", statusFilter);
      return api.getPaged<Candidate>(`/recruitment/candidates?${params}`);
    },
  });
  const candidates = candidatesPage?.data;
  const candidatesTotal = candidatesPage?.total ?? 0;
  // Papan Kanban butuh keseluruhan (dikelompokkan per status), bukan satu
  // halaman — dimuat terpisah, cuma saat papan aktif (limit maksimum backend).
  const { data: boardCandidates } = useQuery({
    queryKey: ["candidates-board"],
    queryFn: () => api.get<Candidate[]>("/recruitment/candidates?limit=1000"),
    enabled: view === "papan",
  });
  const { data: jobOrders } = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["candidates"] });
    qc.invalidateQueries({ queryKey: ["candidates-board"] });
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

  const interviews = useQuery({
    queryKey: ["interviews"],
    queryFn: () => api.get<Interview[]>("/recruitment/interviews"),
    enabled: !!interviewCandidateId,
  });

  const users = useQuery({
    queryKey: ["users-for-interview"],
    queryFn: () => api.get<UserOption[]>("/auth/users"),
    enabled: !!interviewCandidateId,
  });

  const scheduleInterview = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/recruitment/interviews", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interviews"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const [feedbackOpenId, setFeedbackOpenId] = useState<string | null>(null);
  const updateInterview = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/recruitment/interviews/${id}`, body),
    onSuccess: () => {
      setFeedbackOpenId(null);
      qc.invalidateQueries({ queryKey: ["interviews"] });
    },
  });

  const placements = useQuery({
    queryKey: ["placements"],
    queryFn: () => api.get<Placement[]>("/recruitment/placements"),
    enabled: !!onboardCandidateId || !!offeringCandidateId,
  });

  const onboardEmployee = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/employees/onboard", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["placements"] });
      invalidate();
    },
  });

  // PRD v3.0 §4 aksi 2/3 "Offering": surat penawaran PDF branded -> esign.
  const sendOffering = useMutation({
    mutationFn: ({ placementId, body }: { placementId: string; body: Record<string, unknown> }) =>
      api.post(`/recruitment/placements/${placementId}/offering`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["placements"] });
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
        <PageHeader icon={UsersIcon} title="Database Kandidat" />
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
                {v === "tabel" ? <List className="inline h-3.5 w-3.5" /> : <LayoutGrid className="inline h-3.5 w-3.5" />}{" "}
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

      {view === "tabel" && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
            placeholder="Cari nama kandidat..."
            className="input w-56"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setOffset(0);
            }}
            className="input w-auto"
          >
            <option value="">Semua status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}

      {candidates?.length === 0 && view === "tabel" && (
        <CalloutBlock tone="info">
          {q || statusFilter ? (
            "Tidak ada kandidat yang cocok dengan pencarian/filter."
          ) : (
            <>
              Belum ada kandidat. Klik <b>"+ Kandidat Baru"</b> untuk mulai.
            </>
          )}
        </CalloutBlock>
      )}

      {view === "tabel" && (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead className="border-b border-[var(--n-border)] bg-[var(--n-hover)]">
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
          <tbody className="divide-y divide-[var(--n-border)]">
            {(candidates ?? []).map((c) => (
              <Fragment key={c.id}>
                <tr className="hover:bg-[var(--n-hover)]">
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
                      className="text-xs font-medium text-[var(--accent)] hover:opacity-80"
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
                  <div className="flex gap-1">
                    <button
                      className={`py-1 text-xs ${aiCandidateId === c.id ? "btn" : "btn-secondary"}`}
                      onClick={() => setAiCandidateId(aiCandidateId === c.id ? null : c.id)}
                    >
                      Screening
                    </button>
                    <button
                      className={`py-1 text-xs ${interviewCandidateId === c.id ? "btn" : "btn-secondary"}`}
                      onClick={() =>
                        setInterviewCandidateId(interviewCandidateId === c.id ? null : c.id)
                      }
                    >
                      Interview
                    </button>
                    <button
                      className={`py-1 text-xs ${offeringCandidateId === c.id ? "btn" : "btn-secondary"}`}
                      onClick={() =>
                        setOfferingCandidateId(offeringCandidateId === c.id ? null : c.id)
                      }
                    >
                      Penawaran
                    </button>
                    <button
                      className={`py-1 text-xs ${onboardCandidateId === c.id ? "btn" : "btn-secondary"}`}
                      onClick={() =>
                        setOnboardCandidateId(onboardCandidateId === c.id ? null : c.id)
                      }
                    >
                      Onboard
                    </button>
                  </div>
                </td>
              </tr>
                {offeringCandidateId === c.id && (
                  <tr>
                    <td colSpan={7} className="bg-[var(--n-hover)]/60 px-4 py-4">
                      <div className="space-y-3">
                        <span className="text-sm font-semibold text-[var(--n-text)]">
                          Kirim Surat Penawaran: {c.full_name}
                        </span>
                        {(placements.data ?? []).filter(
                          (p) => p.candidate_id === c.id && p.status !== "dibatalkan"
                        ).length === 0 && !placements.isLoading ? (
                          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                            Kandidat ini belum diusulkan (placement) ke job order manapun. Gunakan
                            "Usulkan" di atas dulu sebelum kirim penawaran.
                          </p>
                        ) : (
                          <form
                            className="grid grid-cols-1 gap-2 sm:grid-cols-5"
                            onSubmit={(e) => {
                              e.preventDefault();
                              const form = new FormData(e.currentTarget);
                              const placementId = form.get("placement_id");
                              if (!placementId) return;
                              sendOffering.mutate({
                                placementId: String(placementId),
                                body: {
                                  signer_name: form.get("signer_name") || c.full_name,
                                  signer_email: form.get("signer_email"),
                                  offered_salary: Number(form.get("offered_salary")) || undefined,
                                  start_date: form.get("start_date") || undefined,
                                },
                              });
                            }}
                          >
                            <select name="placement_id" required className="input py-1 text-xs">
                              <option value="">-- Placement (job order) --</option>
                              {(placements.data ?? [])
                                .filter((p) => p.candidate_id === c.id && p.status !== "dibatalkan")
                                .map((p) => (
                                  <option key={p.id} value={p.id}>
                                    {(jobOrders ?? []).find((j) => j.id === p.job_order_id)?.title ??
                                      p.job_order_id}{" "}
                                    · {p.status}
                                  </option>
                                ))}
                            </select>
                            <input
                              name="offered_salary"
                              type="number"
                              required
                              placeholder="Gaji ditawarkan (Rp) *"
                              className="input py-1 text-xs"
                            />
                            <input name="start_date" type="date" className="input py-1 text-xs" />
                            <input
                              name="signer_email"
                              type="email"
                              required
                              placeholder="Email kandidat *"
                              className="input py-1 text-xs"
                            />
                            <button
                              type="submit"
                              disabled={sendOffering.isPending}
                              className="btn py-1 text-xs"
                            >
                              Kirim Penawaran
                            </button>
                          </form>
                        )}
                        {sendOffering.error && (
                          <p className="text-sm text-red-600">
                            {(sendOffering.error as Error).message}
                          </p>
                        )}
                        {sendOffering.isSuccess && (
                          <CalloutBlock tone="success">
                            Surat penawaran terkirim untuk tanda tangan elektronik. Status kandidat
                            otomatis menjadi <b>offered</b>.
                          </CalloutBlock>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
                {onboardCandidateId === c.id && (
                  <tr>
                    <td colSpan={7} className="bg-[var(--n-hover)]/60 px-4 py-4">
                      <div className="space-y-3">
                        <span className="text-sm font-semibold text-[var(--n-text)]">
                          Angkat jadi Karyawan: {c.full_name}
                        </span>
                        {(placements.data ?? []).filter(
                          (p) => p.candidate_id === c.id && p.status !== "dibatalkan"
                        ).length === 0 && !placements.isLoading ? (
                          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                            Kandidat ini belum diusulkan (placement) ke job order manapun. Gunakan
                            "Usulkan" di atas dulu sebelum onboard.
                          </p>
                        ) : (
                          <form
                            className="grid grid-cols-1 gap-2 sm:grid-cols-4"
                            onSubmit={(e) => {
                              e.preventDefault();
                              const form = new FormData(e.currentTarget);
                              const placementId = form.get("placement_id");
                              if (!placementId) return;
                              onboardEmployee.mutate({
                                placement_id: placementId,
                                employee_no: form.get("employee_no") || null,
                                join_date: form.get("join_date") || null,
                                phone: form.get("phone") || null,
                              });
                            }}
                          >
                            <select name="placement_id" required className="input py-1 text-xs">
                              <option value="">-- Placement (job order) --</option>
                              {(placements.data ?? [])
                                .filter((p) => p.candidate_id === c.id && p.status !== "dibatalkan")
                                .map((p) => (
                                  <option key={p.id} value={p.id}>
                                    {(jobOrders ?? []).find((j) => j.id === p.job_order_id)?.title ??
                                      p.job_order_id}{" "}
                                    · {p.status}
                                  </option>
                                ))}
                            </select>
                            <input
                              name="employee_no"
                              placeholder="No. Karyawan (auto jika kosong)"
                              className="input py-1 text-xs"
                            />
                            <input name="join_date" type="date" className="input py-1 text-xs" />
                            <button
                              type="submit"
                              disabled={onboardEmployee.isPending}
                              className="btn py-1 text-xs"
                            >
                              Angkat jadi Karyawan
                            </button>
                          </form>
                        )}
                        {onboardEmployee.error && (
                          <p className="text-sm text-red-600">
                            {(onboardEmployee.error as Error).message}
                          </p>
                        )}
                        {onboardEmployee.isSuccess && (
                          <CalloutBlock tone="success">
                            Berhasil diangkat jadi karyawan. Lihat di halaman{" "}
                            <b>People & Ops</b> untuk lengkapi kontrak, BPJS, dan asuransi.
                          </CalloutBlock>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
                {interviewCandidateId === c.id && (
                  <tr>
                    <td colSpan={7} className="bg-[var(--n-hover)]/60 px-4 py-4">
                      <div className="space-y-3">
                        <span className="text-sm font-semibold text-[var(--n-text)]">
                          Jadwalkan Interview: {c.full_name}
                        </span>
                        <form
                          className="grid grid-cols-1 gap-2 sm:grid-cols-6"
                          onSubmit={(e) => {
                            e.preventDefault();
                            const form = new FormData(e.currentTarget);
                            const joId = form.get("job_order_id");
                            const scheduledAt = form.get("scheduled_at");
                            if (!joId || !scheduledAt) return;
                            scheduleInterview.mutate({
                              candidate_id: c.id,
                              job_order_id: joId,
                              interviewer_id: form.get("interviewer_id") || null,
                              scheduled_at: new Date(String(scheduledAt)).toISOString(),
                              location: form.get("location") || null,
                              meeting_url: form.get("meeting_url") || null,
                              interview_type: form.get("interview_type") || "internal",
                            });
                            e.currentTarget.reset();
                          }}
                        >
                          <select name="job_order_id" required className="input py-1 text-xs">
                            <option value="">-- Job Order --</option>
                            {(jobOrders ?? []).map((j) => (
                              <option key={j.id} value={j.id}>
                                {j.title}
                              </option>
                            ))}
                          </select>
                          <select name="interview_type" className="input py-1 text-xs" defaultValue="internal">
                            <option value="internal">Interview Rekruter (internal)</option>
                            <option value="klien">Interview User (klien)</option>
                          </select>
                          <input
                            name="scheduled_at"
                            type="datetime-local"
                            required
                            className="input py-1 text-xs"
                          />
                          <select name="interviewer_id" className="input py-1 text-xs">
                            <option value="">-- Interviewer (opsional) --</option>
                            {(users.data ?? []).map((u) => (
                              <option key={u.id} value={u.id}>
                                {u.full_name}
                              </option>
                            ))}
                          </select>
                          <input name="location" placeholder="Lokasi" className="input py-1 text-xs" />
                          <button
                            type="submit"
                            disabled={scheduleInterview.isPending}
                            className="btn py-1 text-xs"
                          >
                            Jadwalkan
                          </button>
                        </form>
                        {scheduleInterview.error && (
                          <p className="text-sm text-red-600">
                            {(scheduleInterview.error as Error).message}
                          </p>
                        )}
                        <div className="space-y-1">
                          {(interviews.data ?? [])
                            .filter((i) => i.candidate_id === c.id)
                            .map((i) => (
                              <div key={i.id} className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                                <span
                                  className={`pill ${i.interview_type === "klien" ? "p-violet" : "p-blue"} mr-1 text-[10px]`}
                                >
                                  {i.interview_type === "klien" ? "Klien" : "Internal"}
                                </span>
                                {new Date(i.scheduled_at).toLocaleString("id-ID")} ·{" "}
                                {(jobOrders ?? []).find((j) => j.id === i.job_order_id)?.title ?? "-"}
                                {i.location ? ` · ${i.location}` : ""} ·{" "}
                                <span className="capitalize">{i.status}</span>
                                {i.score !== null && (
                                  <span className="ml-1 pill p-green text-[10px]">Skor {i.score}</span>
                                )}
                                {" · "}
                                <button
                                  type="button"
                                  className="hover:underline"
                                  style={{ color: "var(--accent)" }}
                                  onClick={() => setFeedbackOpenId(feedbackOpenId === i.id ? null : i.id)}
                                >
                                  {i.feedback ? "Lihat/ubah feedback" : "Isi feedback"}
                                </button>
                                {i.feedback && feedbackOpenId !== i.id && (
                                  <p className="mt-0.5 italic">"{i.feedback}"</p>
                                )}
                                {feedbackOpenId === i.id && (
                                  <form
                                    className="mt-1 flex flex-col gap-1.5 rounded p-2"
                                    style={{ backgroundColor: "var(--n-hover)" }}
                                    onSubmit={(e) => {
                                      e.preventDefault();
                                      const form = new FormData(e.currentTarget);
                                      updateInterview.mutate({
                                        id: i.id,
                                        body: {
                                          feedback: form.get("feedback") || null,
                                          score: form.get("score") ? Number(form.get("score")) : null,
                                        },
                                      });
                                    }}
                                  >
                                    <textarea
                                      name="feedback"
                                      defaultValue={i.feedback ?? ""}
                                      placeholder="Catatan hasil interview..."
                                      className="input text-xs"
                                      rows={2}
                                    />
                                    <div className="flex items-center gap-2">
                                      <input
                                        name="score"
                                        type="number"
                                        min={0}
                                        max={100}
                                        defaultValue={i.score ?? ""}
                                        placeholder="Skor (0-100)"
                                        className="input w-28 py-1 text-xs"
                                      />
                                      <button
                                        type="submit"
                                        disabled={updateInterview.isPending}
                                        className="btn py-1 text-xs"
                                      >
                                        Simpan
                                      </button>
                                    </div>
                                  </form>
                                )}
                              </div>
                            ))}
                          {interviews.data &&
                            interviews.data.filter((i) => i.candidate_id === c.id).length === 0 && (
                              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                                Belum ada interview terjadwal.
                              </p>
                            )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
                {aiCandidateId === c.id && (
                  <tr>
                    <td colSpan={7} className="bg-[var(--n-hover)]/60 px-4 py-4">
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-[var(--n-text)]">
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
                          <p className="text-sm text-[var(--n-text-muted)]">Memuat riwayat...</p>
                        ) : (
                          <div className="space-y-2">
                            {(screenings.data ?? []).map((s) => (
                              <AiResultCard key={s.id} screening={s} />
                            ))}
                            {screenings.data?.length === 0 && (
                              <p className="text-sm text-[var(--n-text-muted)]">Belum ada hasil screening.</p>
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
                <td colSpan={7} className="td py-8 text-center text-[var(--n-text-muted)]">
                  Belum ada kandidat.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
      )}

      {view === "tabel" && (
        <Pagination offset={offset} limit={pageLimit} total={candidatesTotal} onOffsetChange={setOffset} />
      )}

      {view === "papan" && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STATUSES.map((stage) => {
            const cards = (boardCandidates ?? []).filter((c) => c.status === stage);
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
                      {c.cv_file_name && (
                        <p className="mt-1 flex items-center gap-1 text-xs text-[var(--accent)]">
                          <Paperclip className="h-3 w-3 shrink-0" /> {c.cv_file_name}
                        </p>
                      )}
                      <div className="mt-2 flex items-center justify-between text-xs" onClick={(e) => e.stopPropagation()}>
                        <button
                          disabled={STATUSES.indexOf(c.status) === 0}
                          onClick={() => changeStatus.mutate({ id: c.id, status: STATUSES[STATUSES.indexOf(c.status) - 1] })}
                          className="rounded px-1.5 py-0.5 disabled:opacity-25"
                          style={{ border: "1px solid var(--n-border)" }}
                        >
                          <ChevronLeft className="h-3.5 w-3.5" />
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
                          <ChevronRight className="h-3.5 w-3.5" />
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

      {boardCandidates?.length === 0 && view === "papan" && (
        <CalloutBlock tone="info">
          Belum ada kandidat untuk ditampilkan di papan.
        </CalloutBlock>
      )}
    </div>
  );
}
