import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile } from "../api/client";
import { AiResultCard, type Screening } from "../components/Ai";
import { CalloutBlock } from "../components/workspace";
import type { JobOrder } from "./JobOrders";

/** Panel-panel detail kandidat -- pindahan dari `TalentPool.tsx` (dulu baris
 * expand di dalam tabel list, sekarang isi tab di `TalentPoolDetail.tsx`).
 * Dipindah apa adanya, tidak ada perubahan internal -- komponen ini sudah
 * tidak pernah terikat ke mekanisme tabel (colSpan dsb ada di pemanggil). */

interface IntakeDetail {
  id: string;
  candidate_id: string;
  status: string;
  doc_kind: string | null;
  file_name: string;
  schema_version: number;
  prompt_version: number;
  extracted: Record<string, unknown> | null;
  confidences: Record<string, number>;
  needs_review: string[];
  reviewed_fields: string[];
  versions: { id: string; seq: number; is_locked: boolean; created_at: string; download_url: string }[];
}

interface CandidateExperience {
  id: string;
  company: string;
  position: string;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

interface ActivityLogEntry {
  id: string;
  action: string;
  detail: unknown;
  created_at: string;
}

const GROUP_LABELS: Record<string, string> = {
  identitas: "Identitas",
  pendidikan: "Pendidikan",
  pengalaman: "Pengalaman",
  skill: "Skill & Sertifikasi",
  penempatan: "Data Penempatan",
};

export function IntakeReviewPanel({ intakeId }: { intakeId: string }) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const [reviewed, setReviewed] = useState<string[]>([]);

  const detail = useQuery({
    queryKey: ["talentpool-intake", intakeId],
    queryFn: () => api.get<IntakeDetail>(`/talentpool/intake/${intakeId}`),
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["talentpool-intake", intakeId] });
    void qc.invalidateQueries({ queryKey: ["talentpool"] });
  };

  const review = useMutation({
    mutationFn: () =>
      api.post(`/talentpool/intake/${intakeId}/review`, {
        corrections: edits,
        reviewed,
      }),
    onSuccess: () => {
      setEdits({});
      setReviewed([]);
      invalidate();
    },
  });
  const finalize = useMutation({
    mutationFn: () => api.post(`/talentpool/intake/${intakeId}/finalize`, {}),
    onSuccess: invalidate,
  });
  const reprocess = useMutation({
    mutationFn: () => api.post(`/talentpool/intake/${intakeId}/reprocess`, {}),
    onSuccess: invalidate,
  });

  if (detail.isLoading) return <p className="text-xs">Memuat profil…</p>;
  if (detail.error) return <p className="text-xs text-red-600">{(detail.error as Error).message}</p>;
  const d = detail.data!;
  const p = d.extracted ?? {};

  const field = (key: string, label: string) => (
    <label className="block text-xs">
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <input
        className="input mt-0.5"
        defaultValue={String(p[key] ?? "")}
        onChange={(e) => setEdits((prev) => ({ ...prev, [key]: e.target.value || null }))}
      />
    </label>
  );

  return (
    <div className="space-y-3 rounded p-3" style={{ backgroundColor: "var(--hover)" }}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`${d.status === "gagal" ? "pill p-red" : d.status === "finalisasi" ? "pill p-green" : "pill p-yellow"}`}>
          {d.status.replace("_", " ")}
        </span>
        <span style={{ color: "var(--text-muted)" }}>{d.file_name} · skema v{d.schema_version}/prompt v{d.prompt_version}</span>
        {d.status === "gagal" && (
          <button
            onClick={() => reprocess.mutate()}
            disabled={reprocess.isPending}
            className="font-medium text-blue-600 hover:text-blue-800"
          >
            Proses Ulang
          </button>
        )}
      </div>

      {d.status === "gagal" && (
        <CalloutBlock tone="warning">
          Ekstraksi gagal: {d.needs_review.length ? "" : ""}
          {"AI belum dikonfigurasi atau dokumen tidak terbaca. Coba proses ulang."}
        </CalloutBlock>
      )}

      {d.extracted && (
        <>
          {d.needs_review.length > 0 && d.status === "menunggu_review" && (
            <div className="rounded border p-2 text-xs" style={{ borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,.08)" }}>
              <b>Wajib dicek recruiter:</b>{" "}
              {d.needs_review.map((g) => GROUP_LABELS[g] ?? g).join(", ")} — centang setelah verifikasi:
              {d.needs_review.map((g) => (
                <label key={g} className="ml-3 inline-flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={reviewed.includes(g)}
                    onChange={(e) =>
                      setReviewed((prev) =>
                        e.target.checked ? [...prev, g] : prev.filter((x) => x !== g)
                      )
                    }
                  />
                  {GROUP_LABELS[g] ?? g}
                </label>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {field("full_name", "Nama lengkap")}
            {field("phone", "No. HP")}
            {field("email", "Email")}
            {field("domisili", "Domisili")}
            {field("birth_date", "Tanggal lahir (YYYY-MM-DD)")}
            {field("expected_salary", "Ekspektasi gaji")}
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {field("summary", "Ringkasan profil")}
            {field("contract_preference", "Preferensi kontrak")}
          </div>

          <details className="text-xs">
            <summary className="cursor-pointer font-medium">Skema lengkap (JSON)</summary>
            <pre className="mt-1 max-h-56 overflow-auto rounded p-2" style={{ backgroundColor: "var(--hover)" }}>
              {JSON.stringify(p, null, 2)}
            </pre>
          </details>

          <div className="flex flex-wrap items-center gap-3 text-xs">
            {d.status === "menunggu_review" && (
              <>
                <button
                  onClick={() => review.mutate()}
                  disabled={review.isPending || Object.keys(edits).length === 0}
                  className="rounded bg-[var(--accent)] px-3 py-1.5 font-medium text-[var(--accent-contrast)] disabled:opacity-40"
                >
                  Simpan Koreksi
                </button>
                <button
                  onClick={() => finalize.mutate()}
                  disabled={finalize.isPending}
                  className="rounded bg-emerald-600 px-3 py-1.5 font-medium text-white disabled:opacity-40"
                >
                  Finalisasi → CV Standar v{(d.versions[0]?.seq ?? 0) + 1}
                </button>
              </>
            )}
          </div>
        </>
      )}

      {(review.error || finalize.error || reprocess.error) && (
        <p className="text-xs text-red-600">
          {((review.error || finalize.error || reprocess.error) as Error).message}
        </p>
      )}

      {d.versions.length > 0 && (
        <div className="text-xs">
          <b>Versi CV standar:</b>
          <ul className="mt-1 space-y-0.5">
            {d.versions.map((v) => (
              <li key={v.id}>
                v{v.seq}{" "}
                <button
                  onClick={() => void downloadFile(v.download_url)}
                  className="font-medium text-blue-600 hover:text-blue-800"
                >
                  Unduh PDF
                </button>
                {v.is_locked && <span className="pill p-gray ml-1">terkunci submission</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** AI Screening — pindahan dari Candidates.tsx. Beda dari kolom "Skor
 * Match" di tabel (native matching, me-ranking BANYAK kandidat per SATU job
 * order): ini menilai SATU kandidat secara mendalam (verdict + alasan LLM),
 * opsional terhadap satu job order. */
export function ScreeningPanel({
  candidateId,
  cvFileName,
  jobOrders,
}: {
  candidateId: string;
  cvFileName: string | null;
  jobOrders: JobOrder[];
}) {
  const qc = useQueryClient();
  const screenings = useQuery({
    queryKey: ["screenings", candidateId],
    queryFn: () => api.get<Screening[]>(`/ai/candidates/${candidateId}/screenings`),
  });
  const runScreening = useMutation({
    mutationFn: (joId: string) =>
      api.post<Screening>(`/ai/candidates/${candidateId}/screen`, { job_order_id: joId || null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["screenings", candidateId] }),
  });

  return (
    <div className="space-y-3 rounded p-3" style={{ backgroundColor: "var(--hover)" }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
          Screening AI
        </span>
        {!cvFileName && (
          <span className="badge border-0 bg-red-100 text-red-600">
            CV belum diunggah — unggah dulu agar AI bisa menilai
          </span>
        )}
        <form
          className="ml-auto flex gap-1"
          onSubmit={(e) => {
            e.preventDefault();
            const sel = e.currentTarget.elements.namedItem("jo") as HTMLSelectElement;
            runScreening.mutate(sel.value);
          }}
        >
          <select name="jo" className="input w-auto py-1 text-xs">
            <option value="">Tanpa job order (nilai umum)</option>
            {jobOrders.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title}
              </option>
            ))}
          </select>
          <button className="btn py-1 text-xs" disabled={runScreening.isPending || !cvFileName}>
            {runScreening.isPending ? "AI sedang menilai..." : "Jalankan Screening"}
          </button>
        </form>
      </div>
      {runScreening.error && <p className="text-sm text-red-600">{(runScreening.error as Error).message}</p>}
      {screenings.isLoading ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Memuat riwayat...</p>
      ) : (
        <div className="space-y-2">
          {(screenings.data ?? []).map((s) => (
            <AiResultCard key={s.id} screening={s} />
          ))}
          {screenings.data?.length === 0 && (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada hasil screening.</p>
          )}
        </div>
      )}
    </div>
  );
}

/** Riwayat pengalaman + activity log — pindahan dari Candidates.tsx. */
export function HistoryPanel({ candidateId }: { candidateId: string }) {
  const qc = useQueryClient();
  const experiences = useQuery({
    queryKey: ["candidate-experiences", candidateId],
    queryFn: () => api.get<CandidateExperience[]>(`/recruitment/candidates/${candidateId}/experiences`),
  });
  const activityLog = useQuery({
    queryKey: ["candidate-activity-log", candidateId],
    queryFn: () => api.get<ActivityLogEntry[]>(`/recruitment/candidates/${candidateId}/activity-log`),
  });
  const createExperience = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(`/recruitment/candidates/${candidateId}/experiences`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidate-experiences", candidateId] }),
  });
  const deleteExperience = useMutation({
    mutationFn: (id: string) => api.delete(`/recruitment/candidates/experiences/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidate-experiences", candidateId] }),
  });

  return (
    <div className="grid grid-cols-1 gap-4 rounded p-3 sm:grid-cols-2" style={{ backgroundColor: "var(--hover)" }}>
      <div>
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
          Riwayat Pengalaman
        </span>
        <form
          className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            createExperience.mutate({
              company: form.get("company"),
              position: form.get("position"),
              start_date: form.get("start_date") || null,
              end_date: form.get("end_date") || null,
            });
            e.currentTarget.reset();
          }}
        >
          <input name="company" required placeholder="Perusahaan" className="input py-1 text-xs" />
          <input name="position" required placeholder="Posisi" className="input py-1 text-xs" />
          <input name="start_date" type="date" className="input py-1 text-xs" />
          <input name="end_date" type="date" className="input py-1 text-xs" />
          <button disabled={createExperience.isPending} className="btn-secondary py-1 text-xs sm:col-span-2">
            + Tambah Pengalaman
          </button>
        </form>
        <ul className="mt-2 space-y-1.5">
          {(experiences.data ?? []).map((exp) => (
            <li
              key={exp.id}
              className="flex items-center justify-between rounded p-2 text-xs"
              style={{ backgroundColor: "var(--bg-elevated)", border: "1px solid var(--border)" }}
            >
              <div>
                <p className="font-medium" style={{ color: "var(--text)" }}>
                  {exp.position} · {exp.company}
                </p>
                <p style={{ color: "var(--text-muted)" }}>
                  {exp.start_date ?? "?"} s/d {exp.end_date ?? "sekarang"}
                </p>
              </div>
              <button onClick={() => deleteExperience.mutate(exp.id)} className="text-rose-600 hover:text-rose-800">
                Hapus
              </button>
            </li>
          ))}
          {experiences.data?.length === 0 && (
            <li className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada riwayat pengalaman.</li>
          )}
        </ul>
      </div>
      <div>
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
          Aktivitas Terbaru
        </span>
        <ul className="mt-2 space-y-1">
          {(activityLog.data ?? []).map((a) => (
            <li key={a.id} className="text-xs" style={{ color: "var(--text-muted)" }}>
              <span style={{ color: "var(--text)" }}>{a.action}</span> ·{" "}
              {new Date(a.created_at).toLocaleString("id-ID")}
            </li>
          ))}
          {activityLog.data?.length === 0 && (
            <li className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada aktivitas tercatat.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
