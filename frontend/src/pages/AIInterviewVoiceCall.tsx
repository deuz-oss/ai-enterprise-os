import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { api } from "../api/client";

/** Panggilan suara real-time AI Interview (Fase 2, self-hosted: LiveKit +
 * Whisper + LLM yang sama (core/llm.py) + facebook/mms-tts-ind). Backend
 * cuma mint kredensial + dispatch agent — audio benar-benar mengalir
 * langsung browser↔LiveKit↔agent lewat WebRTC, bukan lewat backend REST. */

interface VoiceSession {
  url: string;
  token: string;
}

type CallState = "idle" | "connecting" | "connected" | "ended" | "error";

export function AIInterviewVoiceCall({
  token,
  onEnded,
}: {
  token: string;
  onEnded: () => void;
}) {
  const [callState, setCallState] = useState<CallState>("idle");
  const [micEnabled, setMicEnabled] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const roomRef = useRef<Room | null>(null);
  const audioContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return () => {
      roomRef.current?.disconnect();
    };
  }, []);

  async function startCall() {
    setCallState("connecting");
    setErrorMsg(null);
    try {
      const session = await api.post<VoiceSession>(`/ai-interview/session/${token}/voice/start`);
      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          audioContainerRef.current?.appendChild(el);
        }
      });
      room.on(RoomEvent.Disconnected, () => {
        setCallState("ended");
        onEnded();
      });

      await room.connect(session.url, session.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setCallState("connected");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Gagal memulai panggilan.");
      setCallState("error");
    }
  }

  function endCall() {
    roomRef.current?.disconnect();
  }

  async function toggleMic() {
    const next = !micEnabled;
    await roomRef.current?.localParticipant.setMicrophoneEnabled(next);
    setMicEnabled(next);
  }

  return (
    <div className="card space-y-4">
      <div ref={audioContainerRef} className="hidden" />

      {callState === "idle" && (
        <>
          <p className="text-sm text-[var(--text-muted)]">
            Ini interview suara langsung dengan AI — pastikan mikrofon Anda aktif dan Anda berada
            di tempat yang tenang. Klik tombol di bawah untuk mulai.
          </p>
          <button className="btn w-full" onClick={startCall}>
            Mulai Panggilan
          </button>
        </>
      )}

      {callState === "connecting" && (
        <p className="text-sm text-[var(--text-muted)]">Menyambungkan panggilan...</p>
      )}

      {callState === "connected" && (
        <>
          <p className="text-sm font-medium text-emerald-700">
            🔴 Panggilan berlangsung — AI sedang mendengarkan.
          </p>
          <div className="flex gap-2">
            <button className="btn-secondary flex-1" onClick={toggleMic}>
              {micEnabled ? "Matikan Mic" : "Nyalakan Mic"}
            </button>
            <button className="btn flex-1" onClick={endCall}>
              Akhiri Panggilan
            </button>
          </div>
        </>
      )}

      {callState === "ended" && (
        <p className="text-sm text-[var(--text-muted)]">Panggilan selesai, memproses hasil...</p>
      )}

      {callState === "error" && (
        <>
          <p className="text-sm text-red-600">{errorMsg}</p>
          <button className="btn-secondary w-full" onClick={startCall}>
            Coba Lagi
          </button>
        </>
      )}
    </div>
  );
}
