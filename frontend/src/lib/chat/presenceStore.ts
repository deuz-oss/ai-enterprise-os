// Store presence (external store untuk useSyncExternalStore). Scope siapa
// yang terlihat sepenuhnya ditegakkan server -- store ini hanya mencerminkan
// apa yang diterima, tanpa menyaring atau menebak.

export type PresenceStatus = "online" | "away";

export interface PresenceStore {
  subscribe(listener: () => void): () => void;
  get(userId: string): PresenceStatus | undefined;
  /** `presence.snapshot`: ganti penuh -- user yang tidak tercantum dihapus. */
  applySnapshot(users: { user_id: string; status: string }[]): void;
  /** `presence.updated`; `offline` (atau status tak dikenal) menghapus entri. */
  applyUpdate(userId: string, status: string): void;
  /** Koneksi putus: status jadi "tidak diketahui" (tanpa dot), bukan offline. */
  reset(): void;
  size(): number;
}

function isStatus(s: unknown): s is PresenceStatus {
  return s === "online" || s === "away";
}

export function createPresenceStore(): PresenceStore {
  let map = new Map<string, PresenceStatus>();
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach((l) => l());

  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    get(userId) {
      return map.get(userId);
    },
    applySnapshot(users) {
      const next = new Map<string, PresenceStatus>();
      for (const u of users ?? []) {
        if (u && typeof u.user_id === "string" && isStatus(u.status)) next.set(u.user_id, u.status);
      }
      let same = next.size === map.size;
      if (same) {
        for (const [id, s] of next) {
          if (map.get(id) !== s) {
            same = false;
            break;
          }
        }
      }
      if (same) return;
      map = next;
      emit();
    },
    applyUpdate(userId, status) {
      if (typeof userId !== "string") return;
      if (isStatus(status)) {
        if (map.get(userId) === status) return;
        map = new Map(map);
        map.set(userId, status);
      } else {
        if (!map.has(userId)) return;
        map = new Map(map);
        map.delete(userId);
      }
      emit();
    },
    reset() {
      if (map.size === 0) return;
      map = new Map();
      emit();
    },
    size() {
      return map.size;
    },
  };
}
