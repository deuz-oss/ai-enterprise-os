import { createContext, ReactNode, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { API_URL, api, getToken } from "../../api/client";
import { buildChatWsUrl, type ChatServerEvent, type ConnectionState } from "../../lib/chat/chatSocket";
import type { PresenceStatus } from "../../lib/chat/presenceStore";
import { createChatRuntime, type ChatRuntime } from "../../lib/chat/runtime";
import { formatTypers, type Typer } from "../../lib/chat/typingStore";

// Satu koneksi WS chat untuk seluruh app (dipasang di Layout), supaya
// presence tidak berkedip saat pindah halaman/channel. Hook di bawah aman
// dipakai di luar provider: semuanya jadi no-op / "tidak diketahui".

const ChatRealtimeContext = createContext<ChatRuntime | null>(null);

const noopSubscribe = () => () => undefined;
const EMPTY_TYPERS: Typer[] = [];

export function ChatRealtimeProvider({
  enabled,
  selfId,
  children,
}: {
  enabled: boolean;
  selfId: string | null;
  children: ReactNode;
}) {
  const [runtime] = useState(() =>
    createChatRuntime({
      getUrl: () => {
        const token = getToken();
        return token ? buildChatWsUrl(API_URL, token, window.location) : null;
      },
      // 401 di sini memicu alur sesi-habis bawaan api client (redirect login).
      probeAuth: () => api.get("/auth/me"),
    })
  );

  useEffect(() => {
    runtime.setSelfId(selfId);
  }, [runtime, selfId]);

  useEffect(() => {
    if (!enabled) return;
    runtime.start();
    return () => runtime.stop();
  }, [runtime, enabled]);

  return <ChatRealtimeContext.Provider value={enabled ? runtime : null}>{children}</ChatRealtimeContext.Provider>;
}

export function useChatConnection(): ConnectionState {
  const rt = useContext(ChatRealtimeContext);
  return useSyncExternalStore(
    rt ? rt.connection.subscribe : noopSubscribe,
    () => (rt ? rt.connection.get() : "idle")
  );
}

/** Status presence user; `undefined` = offline atau tidak diketahui. */
export function usePresence(userId: string | null | undefined): PresenceStatus | undefined {
  const rt = useContext(ChatRealtimeContext);
  return useSyncExternalStore(
    rt ? rt.presence.subscribe : noopSubscribe,
    () => (rt && userId ? rt.presence.get(userId) : undefined)
  );
}

export function useTypers(channelId: string | null, parentId: string | null): Typer[] {
  const rt = useContext(ChatRealtimeContext);
  return useSyncExternalStore(
    rt ? rt.typing.subscribe : noopSubscribe,
    () => (rt && channelId ? rt.typing.get(channelId, parentId) : EMPTY_TYPERS)
  );
}

/** Langganan event `message.*` saja; handler selalu versi terbaru (via ref). */
export function useChatMessageEvents(handler: (e: ChatServerEvent) => void) {
  const rt = useContext(ChatRealtimeContext);
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (!rt) return;
    return rt.onMessageEvent((e) => ref.current(e));
  }, [rt]);
}

/** Pengirim typing untuk composer channel/thread; stop otomatis saat target berganti. */
export function useTypingSender(channelId: string | null, parentId: string | null) {
  const rt = useContext(ChatRealtimeContext);
  useEffect(() => {
    return () => rt?.sender.stop();
  }, [rt, channelId, parentId]);
  return useMemo(
    () => ({
      onInput(text: string) {
        if (rt && channelId) rt.sender.input({ channelId, parentId }, text);
      },
      stop() {
        rt?.sender.stop();
      },
    }),
    [rt, channelId, parentId]
  );
}

export function presenceLabel(status: PresenceStatus | undefined, connected: boolean): string | null {
  if (status === "online") return "Online";
  if (status === "away") return "Tidak aktif";
  // Server tidak mencantumkan user offline; hanya bisa disimpulkan saat tersambung.
  return connected ? "Offline" : null;
}

/**
 * Titik presence di pojok avatar. Dibedakan lewat BENTUK, bukan hanya warna:
 * online = bulatan penuh, tidak aktif = cincin berongga. Dekoratif
 * (aria-hidden) -- teks statusnya wajib disediakan pemanggil (sr-only/label).
 * Induknya harus `position: relative` (kecuali `inline`).
 */
export function PresenceDot({
  status,
  size = 10,
  ringColor = "var(--sidebar)",
  inline = false,
}: {
  status: PresenceStatus | undefined;
  size?: number;
  /** Warna permukaan di belakang avatar, supaya titik terpisah jelas. */
  ringColor?: string;
  /** true = titik sebaris teks (header), bukan menempel di pojok avatar. */
  inline?: boolean;
}) {
  if (!status) return null;
  const online = status === "online";
  return (
    <span
      aria-hidden
      title={online ? "Online" : "Tidak aktif"}
      className={`shrink-0 rounded-full ${inline ? "inline-block" : "absolute -bottom-0.5 -right-0.5"}`}
      style={{
        width: size,
        height: size,
        backgroundColor: online ? "var(--success)" : "var(--bg-elevated)",
        boxShadow: online
          ? `0 0 0 2px ${ringColor}`
          : `inset 0 0 0 2px var(--text-muted), 0 0 0 2px ${ringColor}`,
      }}
    />
  );
}

/** Baris "X sedang mengetik…" di atas composer; tinggi tetap supaya layout tidak loncat. */
export function TypingIndicator({ channelId, parentId }: { channelId: string | null; parentId: string | null }) {
  const typers = useTypers(channelId, parentId);
  const text = formatTypers(typers.map((t) => t.userName));
  return (
    <p
      aria-live="polite"
      aria-atomic="true"
      className="h-5 truncate px-1 text-xs"
      style={{ color: "var(--text-muted)" }}
    >
      {text}
    </p>
  );
}
