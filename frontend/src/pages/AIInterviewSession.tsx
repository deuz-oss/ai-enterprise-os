import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { api, ApiError } from "../api/client";
import { AIInterviewRecording } from "./AIInterviewRecording";
import { AIInterviewVoiceCall } from "./AIInterviewVoiceCall";

/** Sesi kandidat AI Interview (PRD v3.1 Patch 4) — publik, TANPA Layout/login,
 * diakses via {token} di URL. Mirror pola CareerPortal.tsx. Mode `async_text`
 * = form jawaban teks (di bawah); mode `realtime_voice` (Fase 2) = panggilan
 * suara langsung lewat `AIInterviewVoiceCall`.
 *
 * Fase 0 roadmap (UU PDP): kandidat wajib menyetujui ketentuan pemrosesan
 * data sebelum interview dimulai (backend menolak aksi apa pun tanpa itu),
 * dan bisa menarik persetujuan kapan saja -- seluruh datanya dihapus. */

interface PublicQuestion {
  id: string;
  order: number;
  type: string;
  prompt: string;
  options: string[] | null;
}

interface PublicSession {
  title: string;
  objective: string | null;
  status: "diundang" | "berlangsung" | "terkirim" | "dinilai" | "kedaluwarsa";
  mode: "async_text" | "async_recording" | "realtime_voice";
  questions: PublicQuestion[];
  expires_at: string | null;
  consent_given: boolean;
  consent_version: string;
  consent_text: string;
  retention_days: number;
  data_withdrawn: boolean;
  recorded_answers: {
    question_id: string;
    status: "processing" | "ready" | "failed";
    attempts_used: number;
    transcript: string | null;
  }[];
  max_attempts: number;
  max_answer_seconds: number;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Interview AI</h1>
        {children}
      </div>
    </main>
  );
}

function ConsentCard({ session, token }: { session: PublicSession; token: string }) {
  const qc = useQueryClient();
  const [agreed, setAgreed] = useState(false);
  const [declined, setDeclined] = useState(false);
  const give = useMutation({
    mutationFn: () => api.post(`/ai-interview/session/${token}/consent`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-interview-session", token] }),
  });
  const lines = session.consent_text.split("\n").filter(Boolean);
  const [intro, ...rest] = lines;
  const legal = rest.filter((l) => l.startsWith("Dasar hukum"));
  const points = rest.filter((l) => !l.startsWith("Dasar hukum"));

  if (declined) {
    return (
      <div className="card space-y-2">
        <p className="text-sm text-[var(--text)]">
          Anda tidak menyetujui pemrosesan data, jadi interview AI tidak dimulai dan tidak ada data
          Anda yang diproses.
        </p>
        <p className="text-sm text-[var(--text-muted)]">
          Anda bisa menutup halaman ini. Hubungi tim rekrutmen bila ingin menempuh proses seleksi
          dengan cara lain.
        </p>
        <button type="button" onClick={() => setDeclined(false)} className="btn-secondary text-sm">
          Kembali ke persetujuan
        </button>
      </div>
    );
  }

  return (
    <section className="card space-y-4" aria-labelledby="consent-title">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 shrink-0" style={{ color: "var(--accent)" }} />
        <h2 id="consent-title" className="text-base font-semibold text-[var(--text)]">
          Persetujuan pemrosesan data
        </h2>
      </div>
      <p className="text-sm text-[var(--text)]">{intro}</p>
      <ol className="space-y-2 text-sm text-[var(--text)]">
        {points.map((line) => (
          <li key={line} className="leading-relaxed">
            {line}
          </li>
        ))}
      </ol>
      {legal.map((l) => (
        <p key={l} className="text-xs text-[var(--text-muted)]">
          {l} · Versi ketentuan {session.consent_version}
        </p>
      ))}
      <label className="flex items-start gap-2 text-sm text-[var(--text)]">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-0.5 h-4 w-4"
        />
        <span>Saya sudah membaca dan menyetujui ketentuan di atas.</span>
      </label>
      {give.error && (
        <p className="text-sm text-red-600 dark:text-red-400">{(give.error as Error).message}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={!agreed || give.isPending}
          onClick={() => give.mutate()}
          className="btn"
        >
          {give.isPending ? "Menyimpan…" : "Setuju & lanjutkan"}
        </button>
        <button type="button" onClick={() => setDeclined(true)} className="btn-secondary">
          Saya tidak setuju
        </button>
      </div>
    </section>
  );
}

/** Tarik persetujuan: konfirmasi dua langkah di halaman (tanpa dialog
 * browser), karena tindakannya menghapus data dan tidak bisa dibatalkan. */
function WithdrawConsent({ token }: { token: string }) {
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const withdraw = useMutation({
    mutationFn: () => api.post(`/ai-interview/session/${token}/withdraw-consent`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-interview-session", token] }),
  });
  if (!confirming) {
    return (
      <p className="text-center text-xs text-[var(--text-muted)]">
        Berubah pikiran?{" "}
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="font-medium underline hover:opacity-80"
          style={{ color: "var(--accent)" }}
        >
          Tarik persetujuan & hapus data saya
        </button>
      </p>
    );
  }
  return (
    <div className="card space-y-3" role="alertdialog" aria-labelledby="withdraw-title">
      <p id="withdraw-title" className="text-sm font-medium text-[var(--text)]">
        Tarik persetujuan?
      </p>
      <p className="text-sm text-[var(--text-muted)]">
        Seluruh jawaban, transkrip, dan hasil penilaian AI Anda akan dihapus permanen, dan link
        interview ini tidak bisa dipakai lagi.
      </p>
      {withdraw.error && (
        <p className="text-sm text-red-600 dark:text-red-400">{(withdraw.error as Error).message}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => withdraw.mutate()}
          disabled={withdraw.isPending}
          className="btn-danger"
        >
          {withdraw.isPending ? "Menghapus…" : "Ya, tarik & hapus data"}
        </button>
        <button type="button" onClick={() => setConfirming(false)} className="btn-secondary">
          Batal
        </button>
      </div>
    </div>
  );
}

export default function AIInterviewSession() {
  const { token } = useParams<{ token: string }>();
  const qc = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["ai-interview-session", token],
    queryFn: () => api.get<PublicSession>(`/ai-interview/session/${token}`),
    enabled: Boolean(token),
    retry: false,
    // Mode rekaman: pantau transkripsi latar belakang sampai selesai.
    refetchInterval: (q) =>
      q.state.data?.recorded_answers?.some((r) => r.status === "processing") ? 2500 : false,
  });

  const submit = useMutation({
    mutationFn: async () => {
      await api.post(`/ai-interview/session/${token}/start`);
      for (const q of data?.questions ?? []) {
        const text = (answers[q.id] ?? "").trim();
        if (!text) continue;
        await api.post(`/ai-interview/session/${token}/answer`, {
          question_id: q.id,
          answer_text: text,
        });
      }
      return api.post<PublicSession>(`/ai-interview/session/${token}/submit`);
    },
    onSuccess: () => {
      setSubmitted(true);
      qc.invalidateQueries({ queryKey: ["ai-interview-session", token] });
    },
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    submit.mutate();
  }

  if (isLoading) {
    return (
      <Shell>
        <p className="text-sm text-[var(--text-muted)]">Memuat...</p>
      </Shell>
    );
  }

  if (error) {
    const status = error instanceof ApiError ? error.status : 0;
    return (
      <Shell>
        <div className="card">
          <p className="text-sm text-red-600 dark:text-red-400">
            {status === 410
              ? "Link interview ini sudah kedaluwarsa. Hubungi tim rekrutmen untuk link baru."
              : status === 404
                ? "Link interview tidak ditemukan. Periksa kembali link yang Anda terima."
                : (error as Error).message}
          </p>
        </div>
      </Shell>
    );
  }

  if (!data) return null;

  if (data.data_withdrawn) {
    return (
      <Shell>
        <div className="card space-y-1">
          <p className="text-sm font-medium text-[var(--text)]">Persetujuan Anda sudah ditarik.</p>
          <p className="text-sm text-[var(--text-muted)]">
            Seluruh jawaban, transkrip, dan hasil penilaian AI untuk interview ini sudah dihapus.
            Hubungi tim rekrutmen bila ada pertanyaan.
          </p>
        </div>
      </Shell>
    );
  }

  const alreadyDone = data.status === "terkirim" || data.status === "dinilai";

  return (
    <Shell>
      <div className="card space-y-2">
        <h2 className="text-lg font-semibold text-[var(--text)]">{data.title}</h2>
        {data.objective && <p className="text-sm text-[var(--text-muted)]">{data.objective}</p>}
        {data.expires_at && (
          <p className="text-xs text-[var(--text-muted)]">
            Berlaku sampai {new Date(data.expires_at).toLocaleString("id-ID")}
          </p>
        )}
      </div>

      {!data.consent_given && !alreadyDone ? (
        <ConsentCard session={data} token={token!} />
      ) : submitted || alreadyDone ? (
        <div className="card border-emerald-600">
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            Terima kasih, jawaban Anda sudah kami terima. Tim rekrutmen akan meninjau hasilnya dan
            menghubungi Anda untuk langkah berikutnya.
          </p>
        </div>
      ) : data.mode === "async_recording" ? (
        <AIInterviewRecording
          token={token!}
          questions={data.questions}
          recorded={data.recorded_answers}
          maxAttempts={data.max_attempts}
          maxSeconds={data.max_answer_seconds}
          onSubmitted={() => {
            setSubmitted(true);
            qc.invalidateQueries({ queryKey: ["ai-interview-session", token] });
          }}
        />
      ) : data.mode === "realtime_voice" ? (
        <AIInterviewVoiceCall
          token={token!}
          onEnded={() => {
            setSubmitted(true);
            qc.invalidateQueries({ queryKey: ["ai-interview-session", token] });
          }}
        />
      ) : (
        <form onSubmit={handleSubmit} className="card space-y-4">
          {data.questions.map((q, idx) => (
            <div key={q.id}>
              <label htmlFor={`answer-${q.id}`} className="text-sm font-medium text-[var(--text)]">
                {idx + 1}. {q.prompt}
              </label>
              <textarea
                id={`answer-${q.id}`}
                required
                rows={4}
                value={answers[q.id] ?? ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                className="input mt-1 w-full"
                placeholder="Ketik jawaban Anda di sini..."
              />
            </div>
          ))}
          {submit.error && <p className="text-sm text-red-600 dark:text-red-400">{(submit.error as Error).message}</p>}
          <button type="submit" disabled={submit.isPending} className="btn w-full">
            {submit.isPending ? "Mengirim..." : "Kirim Jawaban"}
          </button>
        </form>
      )}

      {(data.consent_given || alreadyDone) && <WithdrawConsent token={token!} />}
    </Shell>
  );
}
