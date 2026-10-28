import { useEffect, useRef, useState } from "react";
import {
  type Participant,
  type RemoteTrack,
  Room,
  RoomEvent,
  Track,
} from "livekit-client";
import { api } from "../api/client";

/** Panggilan suara real-time AI Interview (Fase 2, self-hosted: LiveKit +
 * Whisper + LLM yang sama (core/llm.py) + facebook/mms-tts-ind). Backend
 * cuma mint kredensial + dispatch agent — audio benar-benar mengalir
 * langsung browser↔LiveKit↔agent lewat WebRTC, bukan lewat backend REST.
 *
 * Avatar video PoC (avatar-worker/): bila agen memakai avatar, wajah AI
 * datang dari peserta terpisah yang ditandai atribut resmi LiveKit
 * `lk.publish_on_behalf`. Tanpa avatar (voice-only / fallback) tampilan
 * tetap seperti panggilan suara biasa. Kamera kandidat tidak pernah
 * dinyalakan -- video kandidat tidak diambil apalagi dinilai. */

const ATTRIBUTE_PUBLISH_ON_BEHALF = "lk.publish_on_behalf";

function isAvatar(participant: Participant): boolean {
  return Boolean(participant.attributes?.[ATTRIBUTE_PUBLISH_ON_BEHALF]);
}

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
  // Panggilan pernah benar-benar tersambung (audio mengalir)? Dulu setiap
  // Disconnected dianggap "interview selesai" -- koneksi WebRTC yang gagal
  // (mis. LiveKit Docker mengiklankan IP internal) menampilkan "Terima kasih,
  // jawaban Anda sudah kami terima" padahal kandidat belum bicara sama sekali.
  const connectedRef = useRef(false);
  const audioContainerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [avatarTrack, setAvatarTrack] = useState<RemoteTrack | null>(null);

  // `callState` ikut jadi dependensi: track avatar sering sudah tersubscribe
  // saat startCall masih menunggu izin mikrofon (state "connecting"), ketika
  // <video> belum dirender. Tanpa itu effect tidak jalan ulang setelah
  // <video> muncul -> kotak avatar hitam selamanya.
  useEffect(() => {
    const el = videoRef.current;
    if (!avatarTrack || !el) return;
    avatarTrack.attach(el);
    return () => {
      avatarTrack.detach(el);
    };
  }, [avatarTrack, callState]);

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

      room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          audioContainerRef.current?.appendChild(el);
        } else if (track.kind === Track.Kind.Video && isAvatar(participant)) {
          setAvatarTrack(track);
        }
      });
      // Avatar keluar (worker mati): agen melanjutkan dengan suara saja,
      // jadi UI kembali ke tampilan panggilan suara.
      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        setAvatarTrack((cur) => (cur === track ? null : cur));
      });
      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        if (isAvatar(participant)) setAvatarTrack(null);
      });
      room.on(RoomEvent.Disconnected, () => {
        if (!connectedRef.current) return; // gagal tersambung -> ditangani catch
        setCallState("ended");
        onEnded();
      });

      await room.connect(session.url, session.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      connectedRef.current = true;
      setCallState("connected");
    } catch (err) {
      roomRef.current?.disconnect();
      const name = err instanceof Error ? err.name : "";
      setErrorMsg(
        name === "NotAllowedError"
          ? "Akses mikrofon ditolak. Izinkan mikrofon untuk situs ini (ikon gembok di samping alamat), lalu coba lagi."
          : "Panggilan tidak dapat tersambung. Periksa koneksi internet Anda lalu coba lagi; bila tetap gagal, hubungi tim rekrutmen."
      );
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
            Ini interview suara langsung dengan AI — pewawancara dapat tampil sebagai avatar
            video buatan AI. Pastikan mikrofon Anda aktif dan Anda berada di tempat yang tenang.
            Klik tombol di bawah untuk mulai.
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
          {avatarTrack && (
            <figure className="space-y-2">
              <div className="mx-auto aspect-square w-full max-w-xs overflow-hidden rounded-lg border border-[var(--border)] bg-black">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="h-full w-full object-cover"
                  aria-label="Video avatar pewawancara AI"
                />
              </div>
              <figcaption className="text-center text-xs text-[var(--text-muted)]">
                Pewawancara ini avatar video buatan AI, bukan orang sungguhan. Kamera Anda tidak
                digunakan.
              </figcaption>
            </figure>
          )}
          <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
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
          <p className="text-sm text-red-600 dark:text-red-400">{errorMsg}</p>
          <button className="btn-secondary w-full" onClick={startCall}>
            Coba Lagi
          </button>
        </>
      )}
    </div>
  );
}
