// Store "sedang mengetik" per (channel, thread). Server sudah mengirim stop
// setelah TTL 6 dtk; klien tetap punya kedaluwarsa sendiri sebagai fallback
// (mis. frame stop hilang karena koneksi putus).

export const TYPING_CLIENT_TTL_MS = 7_000;
const SWEEP_INTERVAL_MS = 1_000;

export interface Typer {
  userId: string;
  userName: string;
}

export interface TypingEvent {
  channel_id: string;
  parent_id: string | null;
  user_id: string;
  user_name?: string;
  state: "start" | "stop";
}

export interface TypingStore {
  subscribe(listener: () => void): () => void;
  /** Daftar pengetik; referensi stabil selama komposisinya tidak berubah. */
  get(channelId: string, parentId: string | null): Typer[];
  apply(event: TypingEvent): void;
  sweep(): void;
  reset(): void;
}

const EMPTY: Typer[] = [];

export function typingKey(channelId: string, parentId: string | null): string {
  return `${channelId}:${parentId ?? "root"}`;
}

export function createTypingStore(now: () => number = () => Date.now()): TypingStore {
  // key -> userId -> { name, expiresAt }
  const entries = new Map<string, Map<string, { userName: string; expiresAt: number }>>();
  const views = new Map<string, Typer[]>();
  const listeners = new Set<() => void>();
  let sweepTimer: ReturnType<typeof setInterval> | null = null;

  const emit = () => listeners.forEach((l) => l());

  function rebuild(key: string) {
    const m = entries.get(key);
    if (!m || m.size === 0) {
      entries.delete(key);
      views.delete(key);
      return;
    }
    views.set(
      key,
      [...m.entries()].map(([userId, v]) => ({ userId, userName: v.userName }))
    );
  }

  function ensureSweep() {
    if (entries.size > 0 && !sweepTimer) {
      sweepTimer = setInterval(() => store.sweep(), SWEEP_INTERVAL_MS);
    } else if (entries.size === 0 && sweepTimer) {
      clearInterval(sweepTimer);
      sweepTimer = null;
    }
  }

  const store: TypingStore = {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    get(channelId, parentId) {
      return views.get(typingKey(channelId, parentId)) ?? EMPTY;
    },
    apply(e) {
      if (!e || typeof e.channel_id !== "string" || typeof e.user_id !== "string") return;
      const key = typingKey(e.channel_id, e.parent_id ?? null);
      let m = entries.get(key);
      if (e.state === "start") {
        const userName = e.user_name || "Seseorang";
        if (!m) {
          m = new Map();
          entries.set(key, m);
        }
        const prev = m.get(e.user_id);
        m.set(e.user_id, { userName, expiresAt: now() + TYPING_CLIENT_TTL_MS });
        // Perpanjangan TTL saja tidak memicu render (komposisi sama).
        if (!prev || prev.userName !== userName) {
          rebuild(key);
          emit();
        }
      } else if (e.state === "stop") {
        if (!m || !m.delete(e.user_id)) return;
        rebuild(key);
        emit();
      }
      ensureSweep();
    },
    sweep() {
      const t = now();
      let changed = false;
      for (const [key, m] of [...entries]) {
        let keyChanged = false;
        for (const [uid, v] of [...m]) {
          if (v.expiresAt <= t) {
            m.delete(uid);
            keyChanged = true;
          }
        }
        if (keyChanged) {
          rebuild(key);
          changed = true;
        }
      }
      ensureSweep();
      if (changed) emit();
    },
    reset() {
      const had = entries.size > 0;
      entries.clear();
      views.clear();
      ensureSweep();
      if (had) emit();
    },
  };
  return store;
}

/** "Budi sedang mengetik…", "Budi dan Sari sedang mengetik…", "3 orang sedang mengetik…". */
export function formatTypers(names: string[]): string {
  if (names.length === 0) return "";
  if (names.length === 1) return `${names[0]} sedang mengetik…`;
  if (names.length === 2) return `${names[0]} dan ${names[1]} sedang mengetik…`;
  return `${names.length} orang sedang mengetik…`;
}
