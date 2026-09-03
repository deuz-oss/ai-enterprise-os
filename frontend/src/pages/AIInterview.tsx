import { FormEvent, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

interface Question {
  id: string;
  order: number;
  type: string;
  prompt: string;
  options: string[] | null;
  criterion_keys: string[];
  required: boolean;
}

interface Criterion {
  key: string;
  label: string;
  weight: number;
  description?: string | null;
}

interface Template {
  id: string;
  job_order_id: string | null;
  title: string;
  objective: string | null;
  mode: string;
  status: "draft" | "aktif" | "arsip";
  questions: Question[];
  criteria: Criterion[];
  created_at: string;
  updated_at: string;
}

interface InterviewResponse {
  id: string;
  template_id: string;
  candidate_id: string;
  job_order_id: string | null;
  status: "diundang" | "berlangsung" | "terkirim" | "dinilai" | "kedaluwarsa";
  answers: { question_id: string; answer_text: string; submitted_at: string }[];
  transcript_text: string | null;
  ai_score_overall: number | null;
  ai_score_breakdown: { criterion_key: string; score: number; reasoning: string }[];
  ai_narrative: string | null;
  ai_model: string | null;
  review_status: "menunggu_review" | "disetujui" | "disesuaikan" | "ditolak";
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  invited_at: string;
  started_at: string | null;
  submitted_at: string | null;
  expires_at: string | null;
}

interface Candidate {
  id: string;
  full_name: string;
  email: string | null;
}

const STATUS_PILL: Record<string, string> = {
  diundang: "p-gray",
  berlangsung: "p-blue",
  terkirim: "p-yellow",
  dinilai: "p-green",
  kedaluwarsa: "p-red",
};

const REVIEW_PILL: Record<string, string> = {
  menunggu_review: "p-yellow",
  disetujui: "p-green",
  disesuaikan: "p-blue",
  ditolak: "p-red",
};

export default function AIInterview() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [candidateIds, setCandidateIds] = useState<string[]>([]);
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  const { data: templates } = useQuery({
    queryKey: ["ai-interview-templates"],
    queryFn: () => api.get<Template[]>("/ai-interview/templates"),
  });
  const { data: candidates } = useQuery({
    queryKey: ["candidates-lite"],
    queryFn: () => api.get<Candidate[]>("/recruitment/candidates"),
  });
  const selected = templates?.find((t) => t.id === selectedId) ?? null;
  const { data: responses } = useQuery({
    queryKey: ["ai-interview-responses", selectedId],
    queryFn: () => api.get<InterviewResponse[]>(`/ai-interview/responses?template_id=${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const candidateName = (id: string) => candidates?.find((c) => c.id === id)?.full_name ?? id;

  const invalidateTemplates = () => qc.invalidateQueries({ queryKey: ["ai-interview-templates"] });
  const invalidateResponses = () =>
    qc.invalidateQueries({ queryKey: ["ai-interview-responses", selectedId] });

  const createTemplate = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/ai-interview/templates", body),
    onSuccess: () => {
      setShowForm(false);
      setQuestions([]);
      setCriteria([]);
      invalidateTemplates();
    },
  });

  const activateTemplate = useMutation({
    mutationFn: (id: string) => api.patch(`/ai-interview/templates/${id}`, { status: "aktif" }),
    onSuccess: invalidateTemplates,
  });

  const inviteCandidates = useMutation({
    mutationFn: () =>
      api.post(`/ai-interview/templates/${selectedId}/invite`, {
        candidate_ids: candidateIds,
        expires_in_hours: 72,
      }),
    onSuccess: () => {
      setCandidateIds([]);
      invalidateResponses();
    },
  });

  const reviewResponse = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.post(`/ai-interview/responses/${id}/review`, body),
    onSuccess: () => {
      setReviewingId(null);
      invalidateResponses();
    },
  });

  const scoreResponse = useMutation({
    mutationFn: (id: string) => api.post(`/ai-interview/responses/${id}/score`),
    onSuccess: invalidateResponses,
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createTemplate.mutate({
      title: form.get("title"),
      objective: form.get("objective") || null,
      mode: form.get("mode") || "async_text",
      questions: questions.filter((q) => q.prompt.trim()),
      criteria: criteria.filter((c) => c.key.trim() && c.label.trim()),
    });
  }

  function handleReview(e: FormEvent<HTMLFormElement>, responseId: string) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const reviewStatus = String(form.get("review_status"));
    const body: Record<string, unknown> = {
      review_status: reviewStatus,
      review_notes: form.get("review_notes") || null,
    };
    if (reviewStatus === "disesuaikan") {
      const overall = form.get("ai_score_overall");
      if (overall) body.ai_score_overall = Number(overall);
    }
    reviewResponse.mutate({ id: responseId, body });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader icon={MessagesSquare} title="AI Interview" />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Template Baru"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card space-y-3">
          <input name="title" required placeholder="Judul interview *" className="input w-full" />
          <textarea
            name="objective"
            placeholder="Tujuan penilaian (opsional)"
            className="input w-full"
            rows={2}
          />
          <div>
            <label className="text-xs font-medium text-[var(--text-muted)]">Mode Interview</label>
            <select name="mode" defaultValue="async_text" className="input mt-1 w-full">
              <option value="async_text">Teks — kandidat ketik jawaban</option>
              <option value="realtime_voice">
                Suara real-time — kandidat ngobrol langsung dengan AI (butuh infra LIVEKIT_*
                dikonfigurasi, lihat .env.example)
              </option>
            </select>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-[var(--text-muted)]">Pertanyaan</p>
            {questions.map((q, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  value={q.prompt}
                  onChange={(e) =>
                    setQuestions((qs) =>
                      qs.map((item, i) => (i === idx ? { ...item, prompt: e.target.value } : item))
                    )
                  }
                  placeholder={`Pertanyaan ${idx + 1}`}
                  className="input flex-1 py-1 text-xs"
                />
                <input
                  value={q.criterion_keys.join(",")}
                  onChange={(e) =>
                    setQuestions((qs) =>
                      qs.map((item, i) =>
                        i === idx
                          ? {
                              ...item,
                              criterion_keys: e.target.value
                                .split(",")
                                .map((s) => s.trim())
                                .filter(Boolean),
                            }
                          : item
                      )
                    )
                  }
                  placeholder="kriteria (pisah koma)"
                  className="input w-40 py-1 text-xs"
                />
                <button
                  type="button"
                  onClick={() => setQuestions((qs) => qs.filter((_, i) => i !== idx))}
                  className="text-xs text-red-600"
                >
                  Hapus
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                setQuestions((qs) => [
                  ...qs,
                  {
                    id: `q${qs.length + 1}`,
                    order: qs.length + 1,
                    type: "open_ended",
                    prompt: "",
                    options: null,
                    criterion_keys: [],
                    required: true,
                  },
                ])
              }
              className="btn-secondary py-1 text-xs"
            >
              + Tambah Pertanyaan
            </button>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-[var(--text-muted)]">
              Kriteria Penilaian (kunci harus cocok dengan yang dipakai di pertanyaan di atas)
            </p>
            {criteria.map((c, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  value={c.key}
                  onChange={(e) =>
                    setCriteria((cs) =>
                      cs.map((item, i) => (i === idx ? { ...item, key: e.target.value } : item))
                    )
                  }
                  placeholder="kunci (mis. komunikasi)"
                  className="input w-32 py-1 text-xs"
                />
                <input
                  value={c.label}
                  onChange={(e) =>
                    setCriteria((cs) =>
                      cs.map((item, i) => (i === idx ? { ...item, label: e.target.value } : item))
                    )
                  }
                  placeholder="Label"
                  className="input flex-1 py-1 text-xs"
                />
                <input
                  type="number"
                  step="0.1"
                  value={c.weight}
                  onChange={(e) =>
                    setCriteria((cs) =>
                      cs.map((item, i) =>
                        i === idx ? { ...item, weight: Number(e.target.value) } : item
                      )
                    )
                  }
                  className="input w-20 py-1 text-xs"
                />
                <button
                  type="button"
                  onClick={() => setCriteria((cs) => cs.filter((_, i) => i !== idx))}
                  className="text-xs text-red-600"
                >
                  Hapus
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setCriteria((cs) => [...cs, { key: "", label: "", weight: 1 }])}
              className="btn-secondary py-1 text-xs"
            >
              + Tambah Kriteria
            </button>
          </div>

          <button type="submit" disabled={createTemplate.isPending} className="btn w-full">
            Simpan Template (draft)
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="card space-y-2 p-0 md:col-span-1">
          {(templates ?? []).map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedId(t.id === selectedId ? null : t.id)}
              className="flex w-full items-center justify-between border-b p-3 text-left transition-colors hover:bg-[var(--hover)]"
              style={{
                borderColor: "var(--border)",
                backgroundColor: selectedId === t.id ? "var(--accent-tint)" : undefined,
              }}
            >
              <div>
                <p className="text-sm font-medium text-[var(--text)]">{t.title}</p>
                <p className="text-xs text-[var(--text-muted)]">{t.questions.length} pertanyaan</p>
              </div>
              <span className={`pill ${t.status === "aktif" ? "p-green" : "p-gray"}`}>{t.status}</span>
            </button>
          ))}
          {templates?.length === 0 && (
            <p className="p-4 text-sm text-[var(--text-muted)]">Belum ada template.</p>
          )}
        </div>

        {selected && (
          <div className="space-y-4 md:col-span-2">
            <div className="card space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-[var(--text)]">{selected.title}</h3>
                  {selected.objective && (
                    <p className="text-sm text-[var(--text-muted)]">{selected.objective}</p>
                  )}
                </div>
                {selected.status === "draft" && (
                  <button
                    className="btn-secondary"
                    disabled={activateTemplate.isPending}
                    onClick={() => activateTemplate.mutate(selected.id)}
                  >
                    Aktifkan
                  </button>
                )}
              </div>

              {selected.status === "aktif" && (
                <div className="space-y-2 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                  <p className="text-xs font-medium text-[var(--text-muted)]">Undang Kandidat</p>
                  <div className="max-h-40 space-y-1 overflow-y-auto">
                    {(candidates ?? []).map((c) => (
                      <label key={c.id} className="flex items-center gap-2 text-sm text-[var(--text)]">
                        <input
                          type="checkbox"
                          checked={candidateIds.includes(c.id)}
                          onChange={(e) =>
                            setCandidateIds((ids) =>
                              e.target.checked ? [...ids, c.id] : ids.filter((id) => id !== c.id)
                            )
                          }
                        />
                        {c.full_name} {c.email ? `(${c.email})` : "(tanpa email)"}
                      </label>
                    ))}
                  </div>
                  <button
                    className="btn"
                    disabled={candidateIds.length === 0 || inviteCandidates.isPending}
                    onClick={() => inviteCandidates.mutate()}
                  >
                    Undang {candidateIds.length || ""} Kandidat
                  </button>
                </div>
              )}
            </div>

            <div className="card space-y-3 p-0">
              <h4 className="p-3 pb-0 font-medium text-[var(--text)]">Response Kandidat</h4>
              {(responses ?? []).map((r) => (
                <div key={r.id} className="border-t p-3" style={{ borderColor: "var(--border)" }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-[var(--text)]">
                        {candidateName(r.candidate_id)}
                      </p>
                      <div className="mt-1 flex gap-2">
                        <span className={`pill ${STATUS_PILL[r.status]}`}>{r.status}</span>
                        <span className={`pill ${REVIEW_PILL[r.review_status]}`}>{r.review_status}</span>
                        {r.ai_score_overall !== null && (
                          <span className="pill p-blue">Skor {r.ai_score_overall}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {(r.status === "terkirim" || r.status === "dinilai") && (
                        <button
                          className="btn-secondary py-1 text-xs"
                          disabled={scoreResponse.isPending}
                          onClick={() => scoreResponse.mutate(r.id)}
                        >
                          {r.status === "dinilai" ? "Nilai Ulang" : "Nilai"}
                        </button>
                      )}
                      {(r.status === "terkirim" || r.status === "dinilai") && (
                        <button
                          className="btn-secondary py-1 text-xs"
                          onClick={() => setReviewingId(reviewingId === r.id ? null : r.id)}
                        >
                          Review
                        </button>
                      )}
                    </div>
                  </div>

                  {r.ai_narrative && (
                    <p className="mt-2 text-sm text-[var(--text-muted)]">{r.ai_narrative}</p>
                  )}
                  {r.transcript_text && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs text-[var(--accent)]">
                        Lihat transkrip percakapan
                      </summary>
                      <p className="mt-1 whitespace-pre-line text-xs text-[var(--text-muted)]">
                        {r.transcript_text}
                      </p>
                    </details>
                  )}
                  {r.ai_score_breakdown.length > 0 && (
                    <ul className="mt-1 space-y-0.5 text-xs text-[var(--text-muted)]">
                      {r.ai_score_breakdown.map((b) => (
                        <li key={b.criterion_key}>
                          {b.criterion_key}: {b.score} — {b.reasoning}
                        </li>
                      ))}
                    </ul>
                  )}

                  {reviewingId === r.id && (
                    <form
                      onSubmit={(e) => handleReview(e, r.id)}
                      className="mt-2 space-y-2 rounded-lg border p-2"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <select name="review_status" className="input w-full py-1 text-xs" required>
                        <option value="disetujui">Setujui</option>
                        <option value="disesuaikan">Sesuaikan (override skor)</option>
                        <option value="ditolak">Tolak</option>
                      </select>
                      <input
                        name="ai_score_overall"
                        type="number"
                        min={0}
                        max={100}
                        placeholder="Skor override (kalau disesuaikan)"
                        className="input w-full py-1 text-xs"
                      />
                      <textarea
                        name="review_notes"
                        placeholder="Catatan review"
                        className="input w-full py-1 text-xs"
                        rows={2}
                      />
                      <button type="submit" disabled={reviewResponse.isPending} className="btn py-1 text-xs">
                        Simpan Review
                      </button>
                    </form>
                  )}
                </div>
              ))}
              {responses?.length === 0 && (
                <p className="p-3 text-sm text-[var(--text-muted)]">Belum ada kandidat diundang.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
