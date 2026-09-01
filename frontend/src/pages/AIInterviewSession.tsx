import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { AIInterviewVoiceCall } from "./AIInterviewVoiceCall";

/** Sesi kandidat AI Interview (PRD v3.1 Patch 4) — publik, TANPA Layout/login,
 * diakses via {token} di URL. Mirror pola CareerPortal.tsx. Mode `async_text`
 * = form jawaban teks (di bawah); mode `realtime_voice` (Fase 2) = panggilan
 * suara langsung lewat `AIInterviewVoiceCall`. */

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
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--n-bg)] px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold text-[var(--n-text)]">Interview AI</h1>
        {children}
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
        <p className="text-sm text-[var(--n-text-muted)]">Memuat...</p>
      </Shell>
    );
  }

  if (error) {
    const status = error instanceof ApiError ? error.status : 0;
    return (
      <Shell>
        <div className="card">
          <p className="text-sm text-red-600">
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

  const alreadyDone = data.status === "terkirim" || data.status === "dinilai";

  return (
    <Shell>
      <div className="card space-y-2">
        <h2 className="text-lg font-semibold text-[var(--n-text)]">{data.title}</h2>
        {data.objective && <p className="text-sm text-[var(--n-text-muted)]">{data.objective}</p>}
        {data.expires_at && (
          <p className="text-xs text-[var(--n-text-muted)]">
            Berlaku sampai {new Date(data.expires_at).toLocaleString("id-ID")}
          </p>
        )}
      </div>

      {submitted || alreadyDone ? (
        <div className="card border-emerald-600">
          <p className="text-sm text-emerald-700">
            Terima kasih, jawaban Anda sudah kami terima. Tim rekrutmen akan meninjau hasilnya dan
            menghubungi Anda untuk langkah berikutnya.
          </p>
        </div>
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
              <label className="text-sm font-medium text-[var(--n-text)]">
                {idx + 1}. {q.prompt}
              </label>
              <textarea
                required
                rows={4}
                value={answers[q.id] ?? ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                className="input mt-1 w-full"
                placeholder="Ketik jawaban Anda di sini..."
              />
            </div>
          ))}
          {submit.error && <p className="text-sm text-red-600">{(submit.error as Error).message}</p>}
          <button type="submit" disabled={submit.isPending} className="btn w-full">
            {submit.isPending ? "Mengirim..." : "Kirim Jawaban"}
          </button>
        </form>
      )}
    </Shell>
  );
}
