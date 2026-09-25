import { FormEvent, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Archive, CheckCircle2, FileEdit, MessagesSquare, ShieldCheck } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { KpiCard } from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { RecordingPlayer } from "../components/RecordingPlayer";

interface Question {
  id: string;
  order: number;
  type: string;
  prompt: string;
  options: string[] | null;
  criterion_keys: string[];
  required: boolean;
  /** Fase 4 (suara real-time): kuota pertanyaan susulan & apa yang digali. */
  follow_up_max?: number;
  follow_up_focus?: string | null;
}

/** Pedoman percakapan agen suara: JIKA kondisi -> jawaban baku. */
interface Guideline {
  condition: string;
  response: string;
}

interface BuiltinGuideline extends Guideline {
  key: string | null;
  locked: boolean;
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
  guidelines: Guideline[];
  created_at: string;
  updated_at: string;
}

interface InterviewResponse {
  id: string;
  template_id: string;
  candidate_id: string;
  job_order_id: string | null;
  status: "diundang" | "berlangsung" | "terkirim" | "dinilai" | "kedaluwarsa";
  answers: {
    question_id: string;
    answer_text: string;
    submitted_at: string;
    audio_object_key?: string;
    transcription?: string;
  }[];
  transcript_text: string | null;
  transcript_clean: string | null;
  has_recording: boolean;
  recording_size_bytes: number | null;
  ai_score_overall: number | null;
  ai_score_breakdown: ScoreItem[];
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
  consent_given_at: string | null;
  consent_version: string | null;
  consent_withdrawn_at: string | null;
  data_purged_at: string | null;
  purge_reason: "retensi" | "penarikan_persetujuan" | "penghapusan_subjek" | null;
}

interface Candidate {
  id: string;
  full_name: string;
  email: string | null;
}

/** Item breakdown hasil penilaian. Field rubrik (label, evidence,
 * supported, ...) ada sejak Fase 1 roadmap (RUBRIC_VERSION 2026-09-24);
 * hasil lama hanya punya criterion_key/score/reasoning. */
interface ScoreItem {
  criterion_key: string;
  score: number | null;
  reasoning: string;
  label?: string;
  weight?: number;
  evidence?: string[];
  dropped_quotes?: number;
  supported?: boolean;
  rubric_version?: string;
}

/** Transkrip sesi suara: versi dirapikan (tanpa "eh/anu") untuk dibaca,
 * versi asli tetap bisa dibuka karena HANYA versi asli yang dipakai
 * penilaian & kutipan bukti. */
function TranscriptView({ raw, clean }: { raw: string; clean: string | null }) {
  const [showRaw, setShowRaw] = useState(false);
  const text = showRaw || !clean ? raw : clean;
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-[var(--accent)]">
        Lihat transkrip percakapan
      </summary>
      {clean && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[var(--text-muted)]">
          <span>
            {showRaw
              ? "Versi asli speech-to-text — dasar penilaian & kutipan bukti."
              : "Versi dirapikan AI untuk dibaca (kata pengisi dibuang). Tidak dipakai untuk penilaian."}
          </span>
          <button
            type="button"
            onClick={() => setShowRaw((v) => !v)}
            className="font-medium underline hover:opacity-80"
            style={{ color: "var(--accent)" }}
          >
            {showRaw ? "Tampilkan versi rapi" : "Tampilkan versi asli"}
          </button>
        </div>
      )}
      <div className="mt-1 space-y-0.5 text-xs text-[var(--text-muted)]">
        {text.split("\n").map((line, i) =>
          // Penanda pertanyaan dari agen terstruktur (Fase 4): "## Pertanyaan N: ..."
          line.startsWith("## ") ? (
            <p key={i} className="pt-2 font-semibold text-[var(--text)]">
              {line.slice(3)}
            </p>
          ) : (
            <p key={i} className="whitespace-pre-line">
              {line}
            </p>
          )
        )}
      </div>
    </details>
  );
}

function ScoreBreakdown({ items, model }: { items: ScoreItem[]; model: string | null }) {
  const isRubric = items.some((b) => b.supported !== undefined);
  const version = items.find((b) => b.rubric_version)?.rubric_version;
  return (
    <div className="mt-3 space-y-2">
      {items.map((b) => {
        const unsupported = isRubric && !b.supported;
        return (
          <div
            key={b.criterion_key}
            className="rounded-lg p-3"
            style={{
              border: "1px solid var(--border)",
              backgroundColor: unsupported ? "var(--bg)" : "var(--bg-elevated)",
            }}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-[var(--text)]">
                {b.label ?? b.criterion_key}
                {b.weight !== undefined && (
                  <span className="ml-1.5 text-xs font-normal text-[var(--text-muted)]">
                    bobot {b.weight}
                  </span>
                )}
              </p>
              {unsupported ? (
                <span className="pill p-yellow" title="Tidak ada kutipan jawaban kandidat yang mendukung skor ini">
                  Tanpa bukti — tidak dihitung
                </span>
              ) : (
                <span className="text-sm font-semibold tabular-nums text-[var(--text)]">
                  {b.score ?? "–"}
                </span>
              )}
            </div>
            {!unsupported && b.score !== null && (
              <div
                className="mt-1.5 h-1.5 overflow-hidden rounded-full"
                style={{ backgroundColor: "var(--hover)" }}
                role="meter"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={b.score}
                aria-label={`Skor ${b.label ?? b.criterion_key}`}
              >
                <div
                  className="h-full rounded-full"
                  style={{ width: `${b.score}%`, backgroundColor: "var(--accent)" }}
                />
              </div>
            )}
            {b.reasoning && <p className="mt-2 text-xs text-[var(--text-muted)]">{b.reasoning}</p>}
            {(b.evidence ?? []).length > 0 && (
              <ul className="mt-2 space-y-1">
                {b.evidence!.map((q) => (
                  <li
                    key={q}
                    className="rounded-r-md py-1 pl-2.5 pr-2 text-xs text-[var(--text)]"
                    style={{ borderLeft: "3px solid var(--accent)", backgroundColor: "var(--accent-tint)" }}
                  >
                    “{q}”
                  </li>
                ))}
              </ul>
            )}
            {(b.dropped_quotes ?? 0) > 0 && (
              <p className="mt-1.5 text-[11px] text-[var(--text-muted)]">
                {b.dropped_quotes} kutipan dari AI dibuang karena tidak ditemukan di jawaban kandidat.
              </p>
            )}
          </div>
        );
      })}
      <p className="text-[11px] text-[var(--text-muted)]">
        {isRubric
          ? "Skor total = rata-rata berbobot kriteria yang didukung kutipan jawaban kandidat. "
          : "Hasil penilaian format lama (tanpa kutipan bukti). "}
        {model && <>Dinilai oleh {model}</>}
        {version && <> · rubrik {version}</>}
      </p>
    </div>
  );
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

/** Fase 4: pedoman percakapan agen suara. Aturan bawaan ditampilkan
 * read-only (sumber: backend) supaya staf tahu apa yang sudah dijaga sistem
 * dan tidak menulis ulang aturan yang sama. */
function GuidelinesEditor({
  value,
  onChange,
}: {
  value: Guideline[];
  onChange: (next: Guideline[]) => void;
}) {
  const { data: builtin } = useQuery({
    queryKey: ["ai-interview-builtin-guidelines"],
    queryFn: () => api.get<BuiltinGuideline[]>("/ai-interview/guidelines/builtin"),
    staleTime: Infinity,
  });
  const update = (idx: number, patch: Partial<Guideline>) =>
    onChange(value.map((g, i) => (i === idx ? { ...g, ...patch } : g)));

  return (
    <div className="space-y-2">
      <div>
        <p className="text-xs font-medium text-[var(--text-muted)]">Pedoman percakapan</p>
        <p className="text-[11px] text-[var(--text-muted)]">
          Jawaban baku saat kandidat menanyakan hal tertentu. Diucapkan AI hampir persis, jadi
          tulis kalimat yang sudah disetujui tim.
        </p>
      </div>
      {value.map((g, idx) => (
        <div key={idx} className="flex flex-wrap items-start gap-2 sm:flex-nowrap">
          <input
            value={g.condition}
            onChange={(e) => update(idx, { condition: e.target.value })}
            placeholder="Jika kandidat… (mis. bertanya soal shift kerja)"
            aria-label={`Kondisi pedoman ${idx + 1}`}
            maxLength={300}
            className="input w-full py-1 text-xs sm:w-2/5"
          />
          <input
            value={g.response}
            onChange={(e) => update(idx, { response: e.target.value })}
            placeholder="Jawab: (mis. Shift kerja 3x8 jam, jadwal diatur supervisor.)"
            aria-label={`Jawaban pedoman ${idx + 1}`}
            maxLength={600}
            className="input min-w-0 flex-1 py-1 text-xs"
          />
          <button
            type="button"
            onClick={() => onChange(value.filter((_, i) => i !== idx))}
            className="text-xs text-red-600 dark:text-red-400"
          >
            Hapus
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...value, { condition: "", response: "" }])}
        className="btn-secondary py-1 text-xs"
        disabled={value.length >= 20}
      >
        + Tambah Pedoman
      </button>
      {builtin && builtin.length > 0 && (
        <details className="rounded-md border p-2" style={{ borderColor: "var(--border)" }}>
          <summary className="cursor-pointer text-xs text-[var(--accent)]">
            Aturan bawaan sistem ({builtin.length}) — selalu berlaku
          </summary>
          <ul className="mt-2 space-y-1.5">
            {builtin.map((g) => (
              <li key={g.key ?? g.condition} className="text-[11px] text-[var(--text-muted)]">
                <span
                  className={`pill mr-1.5 ${g.locked ? "p-red" : "p-gray"}`}
                  title={
                    g.locked
                      ? "Tidak bisa dikalahkan pedoman template"
                      : "Pedoman template untuk topik yang sama menggantikan jawaban ini"
                  }
                >
                  {g.locked ? "terkunci" : "default"}
                </span>
                <b className="text-[var(--text)]">Jika</b> {g.condition.toLowerCase()} →{" "}
                {g.response}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function AIInterview() {
  const qc = useQueryClient();
  // Fase 21 item 3 — deep-link dari tombol "Jadwalkan Interview" terunifikasi
  // di JobOrderDetail.tsx (mode AI): kandidat sudah terpilih begitu halaman
  // ini dibuka, recruiter tinggal pilih template.
  const [searchParams] = useSearchParams();
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [mode, setMode] = useState("async_text");
  const [guidelines, setGuidelines] = useState<Guideline[]>([]);
  const isVoice = mode === "realtime_voice";
  const [candidateIds, setCandidateIds] = useState<string[]>(() => {
    const preselected = searchParams.get("candidate_id");
    return preselected ? [preselected] : [];
  });
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
  const allTemplates = templates ?? [];
  const aktifCount = allTemplates.filter((t) => t.status === "aktif").length;
  const draftCount = allTemplates.filter((t) => t.status === "draft").length;
  const arsipCount = allTemplates.filter((t) => t.status === "arsip").length;
  // Fase 0 roadmap: masa retensi data interview (UU PDP), per tenant.
  const { data: interviewSettings } = useQuery({
    queryKey: ["ai-interview-settings"],
    queryFn: () => api.get<{ retention_days: number }>("/ai-interview/settings"),
  });
  const [editingRetention, setEditingRetention] = useState(false);
  const saveRetention = useMutation({
    mutationFn: (retention_days: number) =>
      api.put<{ retention_days: number }>("/ai-interview/settings", { retention_days }),
    onSuccess: () => {
      setEditingRetention(false);
      qc.invalidateQueries({ queryKey: ["ai-interview-settings"] });
    },
  });
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
      setGuidelines([]);
      setMode("async_text");
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
      mode,
      questions: questions.filter((q) => q.prompt.trim()),
      criteria: criteria.filter((c) => c.key.trim() && c.label.trim()),
      // Pedoman hanya dipakai agen suara real-time.
      guidelines: isVoice
        ? guidelines.filter((g) => g.condition.trim() && g.response.trim())
        : [],
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

      {/* KPI row -- pola yang sudah dipakai lintas modul lain, sebelumnya
          belum diterapkan di halaman ini (DES-013, audit desain 2026-09-15). */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Total Template" value={allTemplates.length} icon={MessagesSquare} iconTone="info" />
        <KpiCard label="Aktif" value={aktifCount} icon={CheckCircle2} iconTone="success" />
        <KpiCard label="Draft" value={draftCount} icon={FileEdit} iconTone="neutral" />
        <KpiCard label="Arsip" value={arsipCount} icon={Archive} iconTone="neutral" />
      </div>

      <div className="card flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--accent)" }} />
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--text)]">Privasi & kepatuhan data</p>
            <p className="text-xs text-[var(--text-muted)]">
              Kandidat wajib menyetujui pemrosesan data sebelum interview dan bisa menariknya kapan
              saja. Jawaban, transkrip, dan hasil AI dihapus otomatis{" "}
              <b className="text-[var(--text)]">{interviewSettings?.retention_days ?? 180} hari</b>{" "}
              setelah interview dikirim. AI hanya menilai isi jawaban, tidak menilai emosi, nada
              suara, aksen, atau cara bicara.
            </p>
          </div>
        </div>
        {editingRetention ? (
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const days = Number(new FormData(e.currentTarget).get("retention_days"));
              saveRetention.mutate(days);
            }}
          >
            <label htmlFor="retention_days" className="text-xs text-[var(--text-muted)]">
              Retensi (30–730 hari)
            </label>
            <input
              id="retention_days"
              name="retention_days"
              type="number"
              min={30}
              max={730}
              required
              defaultValue={interviewSettings?.retention_days ?? 180}
              className="input w-24 py-1 text-sm"
            />
            <button className="btn py-1 text-xs" disabled={saveRetention.isPending}>
              Simpan
            </button>
            <button
              type="button"
              className="btn-secondary py-1 text-xs"
              onClick={() => setEditingRetention(false)}
            >
              Batal
            </button>
            {saveRetention.error && (
              <p className="w-full text-xs text-red-600 dark:text-red-400">
                {(saveRetention.error as Error).message}
              </p>
            )}
          </form>
        ) : (
          <button
            type="button"
            className="btn-secondary py-1 text-xs"
            onClick={() => setEditingRetention(true)}
            title="Hanya role management yang dapat mengubah masa retensi"
          >
            Ubah retensi
          </button>
        )}
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
            <label htmlFor="mode" className="text-xs font-medium text-[var(--text-muted)]">
              Mode Interview
            </label>
            <select
              id="mode"
              name="mode"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="input mt-1 w-full"
            >
              <option value="async_text">Teks — kandidat ketik jawaban</option>
              <option value="async_recording">
                Rekaman jawaban — kandidat merekam jawaban suara per pertanyaan (butuh
                STT_BASE_URL)
              </option>
              <option value="realtime_voice">
                Suara real-time — kandidat ngobrol langsung dengan AI (butuh infra LIVEKIT_*
                dikonfigurasi, lihat .env.example)
              </option>
            </select>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-[var(--text-muted)]">Pertanyaan</p>
            {questions.map((q, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex items-center gap-2">
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
                    className="text-xs text-red-600 dark:text-red-400"
                  >
                    Hapus
                  </button>
                </div>
                {isVoice && (
                  <div className="flex flex-wrap items-center gap-2 pl-3 text-[11px] text-[var(--text-muted)]">
                    <label htmlFor={`fu-max-${idx}`}>Pertanyaan susulan maks.</label>
                    <select
                      id={`fu-max-${idx}`}
                      value={q.follow_up_max ?? 1}
                      onChange={(e) =>
                        setQuestions((qs) =>
                          qs.map((item, i) =>
                            i === idx ? { ...item, follow_up_max: Number(e.target.value) } : item
                          )
                        )
                      }
                      className="input w-16 py-0.5 text-xs"
                    >
                      {[0, 1, 2, 3].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                    <input
                      value={q.follow_up_focus ?? ""}
                      onChange={(e) =>
                        setQuestions((qs) =>
                          qs.map((item, i) =>
                            i === idx ? { ...item, follow_up_focus: e.target.value || null } : item
                          )
                        )
                      }
                      placeholder="yang digali (mis. hasil terukur, peran pribadi)"
                      aria-label={`Fokus pertanyaan susulan ${idx + 1}`}
                      maxLength={300}
                      disabled={(q.follow_up_max ?? 1) === 0}
                      className="input min-w-0 flex-1 py-0.5 text-xs"
                    />
                  </div>
                )}
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
                    follow_up_max: 1,
                    follow_up_focus: null,
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
                  className="text-xs text-red-600 dark:text-red-400"
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

          {isVoice && <GuidelinesEditor value={guidelines} onChange={setGuidelines} />}

          {createTemplate.error && (
            <p className="text-sm text-red-600 dark:text-red-400">
              {(createTemplate.error as Error).message}
            </p>
          )}
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
                        {r.ai_score_overall !== null ? (
                          <span className="pill p-blue">Skor {r.ai_score_overall}</span>
                        ) : (
                          r.status === "dinilai" &&
                          !r.data_purged_at && (
                            <span
                              className="pill p-yellow"
                              title="Tidak ada kriteria yang didukung kutipan jawaban kandidat"
                            >
                              Bukti tidak cukup
                            </span>
                          )
                        )}
                        {r.consent_withdrawn_at ? (
                          <span className="pill p-red">Persetujuan ditarik</span>
                        ) : r.consent_given_at ? (
                          <span className="pill p-green" title={`Versi ketentuan ${r.consent_version ?? "-"}`}>
                            Menyetujui data
                          </span>
                        ) : (
                          <span className="pill p-gray">Belum menyetujui</span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {!r.data_purged_at && (r.status === "terkirim" || r.status === "dinilai") && (
                        <button
                          className="btn-secondary py-1 text-xs"
                          disabled={scoreResponse.isPending}
                          onClick={() => scoreResponse.mutate(r.id)}
                        >
                          {r.status === "dinilai" ? "Nilai Ulang" : "Nilai"}
                        </button>
                      )}
                      {!r.data_purged_at && (r.status === "terkirim" || r.status === "dinilai") && (
                        <button
                          className="btn-secondary py-1 text-xs"
                          onClick={() => setReviewingId(reviewingId === r.id ? null : r.id)}
                        >
                          Review
                        </button>
                      )}
                    </div>
                  </div>

                  {r.data_purged_at && (
                    <p className="mt-2 text-xs text-[var(--text-muted)]">
                      {r.purge_reason === "penarikan_persetujuan"
                        ? "Kandidat menarik persetujuan"
                        : r.purge_reason === "penghapusan_subjek"
                          ? "Data kandidat dihapus atas permintaannya"
                          : "Masa retensi berakhir"}{" "}
                      — jawaban, transkrip, dan hasil AI dihapus pada{" "}
                      {new Date(r.data_purged_at).toLocaleDateString("id-ID")}.
                    </p>
                  )}
                  {r.ai_narrative && (
                    <p className="mt-2 text-sm text-[var(--text-muted)]">{r.ai_narrative}</p>
                  )}
                  {r.has_recording && !r.data_purged_at && <RecordingPlayer responseId={r.id} />}
                  {r.transcript_text && (
                    <TranscriptView raw={r.transcript_text} clean={r.transcript_clean} />
                  )}
                  {r.answers.length > 0 && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs text-[var(--accent)]">
                        Lihat jawaban kandidat
                      </summary>
                      <dl className="mt-2 space-y-2">
                        {r.answers.map((a) => (
                          <div key={a.question_id}>
                            <dt className="text-xs font-medium text-[var(--text)]">
                              {selected?.questions.find((q) => q.id === a.question_id)?.prompt ??
                                a.question_id}
                            </dt>
                            <dd className="mt-0.5 whitespace-pre-line text-xs text-[var(--text-muted)]">
                              {a.answer_text}
                            </dd>
                            {a.audio_object_key && !r.data_purged_at && (
                              <dd>
                                <RecordingPlayer
                                  responseId={r.id}
                                  urlPath={`/ai-interview/responses/${r.id}/answers/${a.question_id}/audio-url`}
                                  title="Rekaman jawaban (transkrip di atas = dasar penilaian)"
                                />
                              </dd>
                            )}
                          </div>
                        ))}
                      </dl>
                    </details>
                  )}
                  {r.ai_score_breakdown.length > 0 && (
                    <ScoreBreakdown items={r.ai_score_breakdown} model={r.ai_model} />
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
