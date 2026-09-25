import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, ChevronRight, Loader2, Mic, RotateCcw, Square, Upload } from "lucide-react";
import { api, API_URL, ApiError } from "../api/client";

/** Mode rekaman jawaban AI Interview (roadmap Fase 3) -- halaman publik
 * kandidat. Satu pertanyaan per layar: rekam -> dengar ulang -> kirim ->
 * sistem menyalin jadi teks (latar belakang) -> kandidat melihat teks yang
 * tertangkap. Rekaman yang hampir hening ditolak sebelum diunggah (diukur
 * lewat Web Audio AnalyserNode), dan server juga menolak bila transkrip
 * kosong. */

interface Question {
  id: string;
  prompt: string;
}

interface RecordedAnswer {
  question_id: string;
  status: "processing" | "ready" | "failed";
  attempts_used: number;
  transcript: string | null;
}

interface Props {
  token: string;
  questions: Question[];
  recorded: RecordedAnswer[];
  maxAttempts: number;
  maxSeconds: number;
  onSubmitted: () => void;
}

// Minimal suara terdeteksi sebelum rekaman boleh dikirim.
const MIN_VOICED_SECONDS = 1.5;
// Ambang RMS (0..1) yang dianggap "ada suara" -- di atas derau ruangan umum.
const VOICE_RMS = 0.02;

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

function fmt(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

type RecState = "idle" | "recording" | "recorded";

export function AIInterviewRecording({ token, questions, recorded, maxAttempts, maxSeconds, onSubmitted }: Props) {
  const qc = useQueryClient();
  const [index, setIndex] = useState(0);
  const [rec, setRec] = useState<RecState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const [voiced, setVoiced] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [micError, setMicError] = useState("");

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number>(0);
  const startedRef = useRef(0);
  const voicedRef = useRef(0);

  const question = questions[index];
  const byQ = new Map(recorded.map((r) => [r.question_id, r]));
  const current = question ? byQ.get(question.id) : undefined;
  const attemptsLeft = maxAttempts - (current?.attempts_used ?? 0);
  const allReady = questions.every((q) => byQ.get(q.id)?.status === "ready");
  const anyProcessing = recorded.some((r) => r.status === "processing");

  function stopTracks() {
    cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
  }

  useEffect(() => () => stopTracks(), []);
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  // Pindah pertanyaan = buang rekaman lokal yang belum dikirim.
  useEffect(() => {
    resetLocal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  function resetLocal() {
    setRec("idle");
    setBlob(null);
    setPreviewUrl(null);
    setElapsed(0);
    setVoiced(0);
    setLevel(0);
  }

  async function startRecording() {
    setMicError("");
    const mime = pickMime();
    if (!navigator.mediaDevices?.getUserMedia || !mime) {
      setMicError("Browser ini tidak mendukung perekaman suara. Coba Chrome, Edge, Firefox, atau Safari versi terbaru.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (e) {
      const name = (e as DOMException).name;
      setMicError(
        name === "NotAllowedError"
          ? "Akses mikrofon ditolak. Izinkan mikrofon untuk situs ini (ikon gembok di address bar), lalu coba lagi."
          : name === "NotFoundError"
            ? "Mikrofon tidak ditemukan. Sambungkan mikrofon atau headset, lalu coba lagi."
            : "Mikrofon tidak bisa dipakai. Tutup aplikasi lain yang memakai mikrofon, lalu coba lagi."
      );
      return;
    }
    streamRef.current = stream;

    // Meter level & hitung detik bersuara (Web Audio, tanpa pustaka).
    const ctx = new AudioContext();
    audioCtxRef.current = ctx;
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Float32Array(analyser.fftSize);
    voicedRef.current = 0;
    let last = performance.now();
    const tick = () => {
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) sum += v * v;
      const rms = Math.sqrt(sum / buf.length);
      const now = performance.now();
      if (rms > VOICE_RMS) voicedRef.current += (now - last) / 1000;
      last = now;
      setLevel(Math.min(1, rms * 8));
      const secs = (now - startedRef.current) / 1000;
      setElapsed(secs);
      if (secs >= maxSeconds) {
        stopRecording();
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    const chunks: Blob[] = [];
    const recorder = new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 32000 });
    recorder.ondataavailable = (ev) => ev.data.size > 0 && chunks.push(ev.data);
    recorder.onstop = () => {
      const b = new Blob(chunks, { type: recorder.mimeType || mime });
      setBlob(b);
      setPreviewUrl(URL.createObjectURL(b));
      setVoiced(voicedRef.current);
      setRec("recorded");
      stopTracks();
    };
    recorderRef.current = recorder;
    startedRef.current = performance.now();
    recorder.start(1000);
    setRec("recording");
    rafRef.current = requestAnimationFrame(tick);
  }

  function stopRecording() {
    cancelAnimationFrame(rafRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  const upload = useMutation({
    mutationFn: async () => {
      if (!blob || !question) return;
      const res = await fetch(
        `${API_URL}/ai-interview/session/${token}/answers/${question.id}/audio?duration_sec=${elapsed.toFixed(1)}`,
        { method: "POST", body: blob, headers: { "Content-Type": blob.type } }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new ApiError(res.status, body.detail ?? "Gagal mengunggah rekaman");
      }
    },
    onSuccess: () => {
      resetLocal();
      qc.invalidateQueries({ queryKey: ["ai-interview-session", token] });
    },
  });

  const submit = useMutation({
    mutationFn: () => api.post(`/ai-interview/session/${token}/submit`),
    onSuccess: onSubmitted,
  });

  if (!question) return null;
  const tooQuiet = rec === "recorded" && voiced < MIN_VOICED_SECONDS;

  return (
    <section className="card space-y-5" aria-labelledby="rec-q-title">
      {/* Progres */}
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-[var(--text-muted)]">
          Pertanyaan {index + 1} dari {questions.length}
        </p>
        <ol className="flex gap-1.5" aria-label="Status jawaban">
          {questions.map((q, i) => {
            const st = byQ.get(q.id)?.status;
            return (
              <li key={q.id}>
                <button
                  type="button"
                  onClick={() => setIndex(i)}
                  disabled={rec === "recording"}
                  aria-label={`Pertanyaan ${i + 1}${st === "ready" ? " (sudah dijawab)" : ""}`}
                  aria-current={i === index ? "step" : undefined}
                  className="h-2.5 w-6 rounded-full transition-colors"
                  style={{
                    backgroundColor:
                      st === "ready" ? "var(--accent)" : i === index ? "var(--text-muted)" : "var(--border)",
                  }}
                />
              </li>
            );
          })}
        </ol>
      </div>

      <h2 id="rec-q-title" className="text-base font-semibold leading-relaxed text-[var(--text)]">
        {question.prompt}
      </h2>

      {/* Status jawaban yang sudah terkirim */}
      <div aria-live="polite">
        {current?.status === "processing" && (
          <p className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
            <Loader2 className="h-4 w-4 animate-spin" /> Menyalin rekaman Anda menjadi teks…
          </p>
        )}
        {current?.status === "ready" && rec === "idle" && (
          <div className="rounded-lg p-3" style={{ backgroundColor: "var(--accent-tint)" }}>
            <p className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--accent)" }}>
              <CheckCircle2 className="h-4 w-4" /> Jawaban tersimpan. Yang tertangkap sistem:
            </p>
            <p className="mt-1 text-sm text-[var(--text)]">“{current.transcript}”</p>
          </div>
        )}
        {current?.status === "failed" && rec === "idle" && (
          <p className="text-sm text-red-600 dark:text-red-400">
            Suara tidak tertangkap dari rekaman terakhir. Silakan rekam ulang lebih dekat ke mikrofon.
          </p>
        )}
      </div>

      {/* Perekam */}
      {rec === "recording" ? (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-red-600" />
            </span>
            <span className="text-sm font-medium tabular-nums text-[var(--text)]">
              Merekam {fmt(elapsed)} / {fmt(maxSeconds)}
            </span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full"
            style={{ backgroundColor: "var(--hover)" }}
            role="meter"
            aria-label="Level suara mikrofon"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(level * 100)}
          >
            <div
              className="h-full rounded-full transition-[width] duration-75"
              style={{ width: `${level * 100}%`, backgroundColor: "var(--accent)" }}
            />
          </div>
          <button type="button" onClick={stopRecording} className="btn flex items-center gap-2">
            <Square className="h-4 w-4" /> Selesai merekam
          </button>
        </div>
      ) : rec === "recorded" && previewUrl ? (
        <div className="space-y-3">
          <p className="text-sm text-[var(--text)]">Dengarkan dulu rekaman Anda ({fmt(elapsed)}):</p>
          <audio src={previewUrl} controls className="w-full" />
          {tooQuiet && (
            <p className="text-sm text-red-600 dark:text-red-400">
              Suara Anda hampir tidak terdengar di rekaman ini. Rekam ulang lebih dekat ke mikrofon.
            </p>
          )}
          {upload.error && (
            <p className="text-sm text-red-600 dark:text-red-400">{(upload.error as Error).message}</p>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => upload.mutate()}
              disabled={tooQuiet || upload.isPending}
              className="btn flex items-center gap-2"
            >
              {upload.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              Kirim jawaban ini
            </button>
            <button type="button" onClick={resetLocal} className="btn-secondary flex items-center gap-2">
              <RotateCcw className="h-4 w-4" /> Buang & rekam lagi
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <button
            type="button"
            onClick={startRecording}
            disabled={attemptsLeft <= 0 || current?.status === "processing"}
            className="btn flex items-center gap-2"
          >
            <Mic className="h-4 w-4" />
            {current ? "Rekam ulang jawaban" : "Mulai merekam jawaban"}
          </button>
          <p className="text-xs text-[var(--text-muted)]">
            Maksimal {fmt(maxSeconds)} per jawaban · sisa kesempatan kirim {Math.max(0, attemptsLeft)} dari{" "}
            {maxAttempts}
          </p>
          {micError && <p className="text-sm text-red-600 dark:text-red-400">{micError}</p>}
        </div>
      )}

      {/* Navigasi & kirim */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-4" style={{ borderColor: "var(--border)" }}>
        <button
          type="button"
          onClick={() => setIndex((i) => Math.max(0, i - 1))}
          disabled={index === 0 || rec === "recording"}
          className="btn-secondary flex items-center gap-1"
        >
          <ChevronLeft className="h-4 w-4" /> Sebelumnya
        </button>
        {index < questions.length - 1 ? (
          <button
            type="button"
            onClick={() => setIndex((i) => i + 1)}
            disabled={rec === "recording"}
            className="btn-secondary flex items-center gap-1"
          >
            Berikutnya <ChevronRight className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => submit.mutate()}
            disabled={!allReady || submit.isPending || rec === "recording"}
            className="btn"
            title={allReady ? undefined : "Jawab semua pertanyaan dulu"}
          >
            {submit.isPending ? "Mengirim…" : "Kirim interview"}
          </button>
        )}
      </div>
      {!allReady && index === questions.length - 1 && (
        <p className="text-xs text-[var(--text-muted)]">
          {anyProcessing
            ? "Menunggu semua rekaman selesai disalin…"
            : "Semua pertanyaan harus dijawab sebelum interview dikirim."}
        </p>
      )}
      {submit.error && <p className="text-sm text-red-600 dark:text-red-400">{(submit.error as Error).message}</p>}
    </section>
  );
}
