import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { Loader2, Pause, Play } from "lucide-react";
import { api } from "../api/client";

/** Pemutar rekaman sesi AI Interview (roadmap Fase 2).
 *
 * File ogg 2 kanal dari agent (0 = kandidat, 1 = pewawancara AI) ditampilkan
 * sebagai dua gelombang terpisah, supaya reviewer langsung melihat siapa
 * bicara kapan. Rekaman baru dimuat saat tombol diklik: link-nya
 * kedaluwarsa 15 menit dan setiap permintaan link tercatat di audit log
 * (data biometrik) -- jangan diambil otomatis hanya karena kartu dibuka. */

interface RecordingUrl {
  url: string;
  expires_in_seconds: number;
  channels: string[];
}

function cssVar(name: string, fallback: string): string {
  // Canvas tidak mengerti `var(--x)` -- ambil nilai token yang sudah dihitung
  // (otomatis ikut light/dark mode saat pemutar dimuat).
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function fmt(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function RecordingPlayer({
  responseId,
  urlPath,
  title = "Rekaman sesi",
}: {
  responseId: string;
  /** Endpoint link rekaman; default = rekaman sesi suara real-time. */
  urlPath?: string;
  title?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState({ cur: 0, dur: 0 });
  const [channels, setChannels] = useState<string[]>(["Kandidat", "Pewawancara AI"]);

  useEffect(() => () => wsRef.current?.destroy(), []);

  async function load() {
    if (!containerRef.current) return;
    setState("loading");
    setError("");
    try {
      const rec = await api.get<RecordingUrl>(
        urlPath ?? `/ai-interview/responses/${responseId}/recording-url`
      );
      setChannels(rec.channels);
      const accent = cssVar("--accent", "#0F6E56");
      const muted = cssVar("--text-muted", "#64748B");
      const ws = WaveSurfer.create({
        container: containerRef.current,
        url: rec.url,
        height: 40,
        normalize: true,
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        cursorColor: cssVar("--text", "#0F172A"),
        splitChannels: [
          { waveColor: accent, progressColor: accent, overlay: false },
          { waveColor: muted, progressColor: muted, overlay: false },
        ],
      });
      ws.on("ready", (dur) => {
        setTime({ cur: 0, dur });
        setState("ready");
      });
      ws.on("timeupdate", (cur) => setTime((t) => ({ ...t, cur })));
      ws.on("play", () => setPlaying(true));
      ws.on("pause", () => setPlaying(false));
      ws.on("finish", () => setPlaying(false));
      ws.on("error", (e) => {
        setError(String(e));
        setState("error");
      });
      wsRef.current = ws;
    } catch (e) {
      setError((e as Error).message);
      setState("error");
    }
  }

  return (
    <div
      className="mt-2 rounded-lg p-3"
      style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => (state === "ready" ? wsRef.current?.playPause() : load())}
          disabled={state === "loading"}
          className="btn flex h-8 w-8 shrink-0 items-center justify-center p-0"
          aria-label={playing ? "Jeda rekaman" : state === "ready" ? "Putar rekaman" : "Muat & putar rekaman"}
        >
          {state === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : playing ? (
            <Pause className="h-4 w-4" />
          ) : (
            <Play className="h-4 w-4" />
          )}
        </button>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-[var(--text)]">{title}</p>
          <p className="text-[11px] tabular-nums text-[var(--text-muted)]">
            {state === "idle"
              ? "Klik putar untuk memuat (akses rekaman tercatat di audit log)"
              : state === "ready"
                ? `${fmt(time.cur)} / ${fmt(time.dur)}`
                : state === "loading"
                  ? "Memuat rekaman…"
                  : `Gagal memuat rekaman: ${error}`}
          </p>
        </div>
      </div>
      <div className={state === "idle" ? "hidden" : "mt-3 flex gap-2"}>
        <div className="flex w-32 shrink-0 flex-col justify-around text-[11px] text-[var(--text-muted)]">
          {channels.map((c, i) => (
            <span key={c} className="flex items-center gap-1.5" style={{ height: 40 }}>
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: i === 0 ? "var(--accent)" : "var(--text-muted)" }}
              />
              {c}
            </span>
          ))}
        </div>
        <div ref={containerRef} className="min-w-0 flex-1" />
      </div>
    </div>
  );
}
