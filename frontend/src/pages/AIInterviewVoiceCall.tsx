import { useEffect, useRef, useState } from "react";
import {
  type Participant,
  ParticipantKind,
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

/* Suara latar (TV/orang lain) terbaca sebagai jawaban -- uji browser
 * 2026-10-29: semenit siaran di dekat mikrofon dinilai sebagai jawaban.
 * Tiga lapis: cek ruangan sebelum panggilan, teks "yang kami dengar" +
 * tombol "Bukan suara saya" selama & sesudah panggilan, dan penanda untuk
 * reviewer (backend audio_flags). */

// Transkrip yang dikirim agen LiveKit (room_io): giliran kandidat ditandai
// lk.transcribed_track_id = track mikrofon kandidat sendiri.
const TOPIC_TRANSCRIPTION = "lk.transcription";
const ATTR_TRANSCRIBED_TRACK = "lk.transcribed_track_id";
const ATTR_FINAL = "lk.transcription_final";
// Harus sama dengan DISOWN_RPC_METHOD di agent/main.py.
const DISOWN_RPC = "aeos.disown_last_answer";

// Cek ruangan: kandidat diminta diam CHECK_SECONDS; bila suara di atas
// ROOM_VOICE_RMS terdengar lebih dari ROOM_MAX_VOICED detik, ada suara lain
// di sekitar. Ambang di bawah VOICE_RMS mode rekaman (0.02): siaran di uji
// 2026-10-29 berada di RMS ~0.006-0.045. Belum dikalibrasi dengan banyak
// ruangan sungguhan -- pengaman, bukan detektor pasti.
const CHECK_SECONDS = 5;
const ROOM_VOICE_RMS = 0.012;
const ROOM_MAX_VOICED = 1.0;

type RoomCheck = "ok" | "noisy" | "skipped";

/** Ukur suara di sekitar selama CHECK_SECONDS. Suara yang baru muncul di
 * tengah sesi tidak tertangkap di sini (itu tugas tombol "Bukan suara saya"). */
async function measureRoom(
  onLevel: (v: number) => void
): Promise<{ result: RoomCheck; voiced: number }> {
  if (!navigator.mediaDevices?.getUserMedia || typeof AudioContext === "undefined") {
    return { result: "skipped", voiced: 0 };
  }
  // Batasan audio sama dengan default livekit-client -> yang diukur mirip
  // dengan yang nanti sampai ke STT.
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const ctx = new AudioContext();
  try {
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Float32Array(analyser.fftSize);
    let voiced = 0;
    const start = performance.now();
    let last = start;
    await new Promise<void>((resolve) => {
      const tick = () => {
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += v * v;
        const rms = Math.sqrt(sum / buf.length);
        const now = performance.now();
        if (rms > ROOM_VOICE_RMS) voiced += (now - last) / 1000;
        last = now;
        onLevel(Math.min(1, rms * 8));
        if (now - start >= CHECK_SECONDS * 1000) resolve();
        else requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    return {
      result: voiced > ROOM_MAX_VOICED ? "noisy" : "ok",
      voiced: Math.round(voiced * 10) / 10,
    };
  } finally {
    stream.getTracks().forEach((t) => t.stop());
    void ctx.close();
  }
}

/** "Bukan suara saya": catat ke backend (sinyal untuk reviewer). */
async function disownToBackend(token: string, text: string, duringCall: boolean): Promise<boolean> {
  try {
    await api.post(`/ai-interview/session/${token}/voice/disown`, {
      text,
      during_call: duringCall,
    });
    return true;
  } catch {
    return false;
  }
}

/** Setelah panggilan: agen bisa menutup interview tepat setelah giliran
 * terakhir, sebelum kandidat sempat menandainya. Dipasang di layar
 * "terima kasih". Skor sudah dihitung -- catatan ini untuk reviewer. */
export function VoiceLastAnswerCheck({ token, text }: { token: string; text: string }) {
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  return (
    <div className="mt-3 space-y-2 border-t border-[var(--border)] pt-3 text-sm">
      <p className="text-[var(--text-muted)]">Jawaban terakhir yang kami tangkap:</p>
      <blockquote className="rounded border border-[var(--border)] p-2 italic">{text}</blockquote>
      {state === "done" ? (
        <p className="text-[var(--text-muted)]">
          Dicatat: bagian itu bukan suara Anda. Tim rekrutmen akan melihat catatan ini.
        </p>
      ) : (
        <>
          <button
            className="btn-secondary"
            disabled={state === "sending"}
            onClick={async () => {
              setState("sending");
              setState((await disownToBackend(token, text, false)) ? "done" : "error");
            }}
          >
            Bukan suara saya
          </button>
          {state === "error" && (
            <p className="text-red-600 dark:text-red-400">Gagal mengirim, coba lagi.</p>
          )}
        </>
      )}
    </div>
  );
}

function isAvatar(participant: Participant): boolean {
  return Boolean(participant.attributes?.[ATTRIBUTE_PUBLISH_ON_BEHALF]);
}

interface VoiceSession {
  url: string;
  token: string;
}

type CallState = "idle" | "checking" | "noisy" | "connecting" | "connected" | "ended" | "error";

interface Heard {
  text: string;
  // Giliran kandidat sudah ditutup (pewawancara bicara lagi) -> teks
  // berikutnya giliran baru, bukan lanjutan.
  closed: boolean;
  disowned: boolean;
}

export function AIInterviewVoiceCall({
  token,
  onEnded,
}: {
  token: string;
  onEnded: (lastHeard: string | null) => void;
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
  const [level, setLevel] = useState(0);
  const [roomVoiced, setRoomVoiced] = useState(0);
  const [heard, setHeard] = useState<Heard | null>(null);
  // Salinan untuk handler LiveKit (closure tidak melihat state terbaru).
  const heardRef = useRef<Heard | null>(null);
  heardRef.current = heard;
  const [disownError, setDisownError] = useState(false);

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

  async function checkRoom() {
    setCallState("checking");
    setErrorMsg(null);
    try {
      const { result, voiced } = await measureRoom(setLevel);
      setRoomVoiced(voiced);
      if (result === "noisy") setCallState("noisy");
      else await startCall(result, voiced);
    } catch (err) {
      showStartError(err);
    }
  }

  function showStartError(err: unknown) {
    roomRef.current?.disconnect();
    const name = err instanceof Error ? err.name : "";
    setErrorMsg(
      name === "NotAllowedError"
        ? "Akses mikrofon ditolak. Izinkan mikrofon untuk situs ini (ikon gembok di samping alamat), lalu coba lagi."
        : "Panggilan tidak dapat tersambung. Periksa koneksi internet Anda lalu coba lagi; bila tetap gagal, hubungi tim rekrutmen."
    );
    setCallState("error");
  }

  async function startCall(roomCheck: RoomCheck, voiced: number) {
    setCallState("connecting");
    setErrorMsg(null);
    try {
      const session = await api.post<VoiceSession>(`/ai-interview/session/${token}/voice/start`, {
        room_check: roomCheck,
        voiced_sec: voiced,
      });
      const room = new Room();
      roomRef.current = room;

      // Elemen <audio> per track, untuk dicabut saat track berhenti.
      const audioEls = new Map<RemoteTrack, HTMLMediaElement>();

      room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          audioEls.set(track, el);
          audioContainerRef.current?.appendChild(el);
        } else if (track.kind === Track.Kind.Video && isAvatar(participant)) {
          setAvatarTrack(track);
        }
      });
      // Avatar keluar (worker mati): agen melanjutkan dengan suara saja,
      // jadi UI kembali ke tampilan panggilan suara.
      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        // livekit-client 2.22 men-detach elemen SEBELUM event ini (jadi
        // track.detach() di sini selalu kosong) tapi tidak mencabutnya dari
        // DOM. Tanpa ini, tiap avatar keluar (fallback di tengah sesi /
        // avatar yatim dihentikan) meninggalkan <audio> kosong -- terlihat
        // saat uji di browser 2026-10-29. Video dicabut oleh effect avatarTrack.
        audioEls.get(track)?.remove();
        audioEls.delete(track);
        setAvatarTrack((cur) => (cur === track ? null : cur));
      });
      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        if (isAvatar(participant)) setAvatarTrack(null);
      });
      room.on(RoomEvent.Disconnected, () => {
        if (!connectedRef.current) return; // gagal tersambung -> ditangani catch
        setCallState("ended");
        const last = heardRef.current;
        onEnded(last && !last.disowned ? last.text : null);
      });
      // "Yang kami dengar": transkrip final giliran kandidat sendiri.
      room.registerTextStreamHandler(TOPIC_TRANSCRIPTION, async (reader) => {
        const attrs = reader.info.attributes ?? {};
        const text = (await reader.readAll()).trim();
        const micSid = room.localParticipant.getTrackPublication(Track.Source.Microphone)?.trackSid;
        const mine = Boolean(micSid) && attrs[ATTR_TRANSCRIBED_TRACK] === micSid;
        if (!mine) {
          // Pewawancara bicara: giliran kandidat sebelumnya ditutup.
          setHeard((cur) => (cur ? { ...cur, closed: true } : cur));
          return;
        }
        if (attrs[ATTR_FINAL] !== "true" || !text) return;
        setDisownError(false);
        setHeard((cur) =>
          cur && !cur.closed && !cur.disowned
            ? { ...cur, text: `${cur.text} ${text}` }
            : { text, closed: false, disowned: false }
        );
      });

      await room.connect(session.url, session.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      connectedRef.current = true;
      setCallState("connected");
    } catch (err) {
      showStartError(err);
    }
  }

  async function disownHeard() {
    const room = roomRef.current;
    const current = heardRef.current;
    if (!room || !current || current.disowned) return;
    setHeard({ ...current, disowned: true });
    // Agen (bukan avatar) yang mengabaikan giliran itu & meminta jawaban ulang.
    const agent = [...room.remoteParticipants.values()].find(
      (p) => p.kind === ParticipantKind.AGENT && !isAvatar(p)
    );
    const [saved, told] = await Promise.all([
      disownToBackend(token, current.text, true),
      agent
        ? room.localParticipant
            .performRpc({ destinationIdentity: agent.identity, method: DISOWN_RPC, payload: "" })
            .then(
              () => true,
              () => false
            )
        : Promise.resolve(false),
    ]);
    setDisownError(!saved || !told);
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
          <button className="btn w-full" onClick={checkRoom}>
            Mulai Panggilan
          </button>
        </>
      )}

      {callState === "checking" && (
        <div className="space-y-2" role="status">
          <p className="text-sm">
            Mohon diam sebentar ({CHECK_SECONDS} detik) — kami mengecek suara di sekitar Anda.
          </p>
          <div className="h-2 w-full overflow-hidden rounded bg-[var(--border)]" aria-hidden="true">
            <div
              className="h-full bg-[var(--accent)] transition-[width]"
              style={{ width: `${level * 100}%` }}
            />
          </div>
        </div>
      )}

      {callState === "noisy" && (
        <div className="space-y-3">
          <p className="text-sm text-amber-700 dark:text-amber-400">
            Ada suara lain di sekitar Anda (mis. TV, musik, atau orang lain berbicara). Suara itu bisa
            ikut terbaca sebagai jawaban Anda. Sebaiknya pindah ke tempat yang lebih tenang atau
            matikan sumber suaranya, lalu cek ulang.
          </p>
          <div className="flex gap-2">
            <button className="btn flex-1" onClick={checkRoom}>
              Cek Ulang
            </button>
            <button className="btn-secondary flex-1" onClick={() => startCall("noisy", roomVoiced)}>
              Tetap Mulai
            </button>
          </div>
        </div>
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
          {heard && (
            <div className="space-y-2 rounded border border-[var(--border)] p-3 text-sm" aria-live="polite">
              <p className="text-xs text-[var(--text-muted)]">Yang kami dengar dari Anda:</p>
              <p className={heard.disowned ? "text-[var(--text-muted)] line-through" : ""}>{heard.text}</p>
              {heard.disowned ? (
                <p className="text-xs text-[var(--text-muted)]">
                  Diabaikan — pewawancara akan meminta Anda menjawab ulang.
                  {disownError && " (Catatan tidak terkirim sepenuhnya; tetap jawab ulang.)"}
                </p>
              ) : (
                <button className="btn-secondary text-xs" onClick={disownHeard}>
                  Bukan suara saya
                </button>
              )}
            </div>
          )}
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
          <button className="btn-secondary w-full" onClick={checkRoom}>
            Coba Lagi
          </button>
        </>
      )}
    </div>
  );
}
