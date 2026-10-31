// Pengirim typing.start/stop dengan throttle klien: start paling sering
// 1x / 2,5 dtk selama mengetik (cukup untuk menjaga TTL 6 dtk di server),
// stop saat idle 3 dtk, kirim pesan, ganti channel/thread, blur, atau pagehide.

export const TYPING_START_INTERVAL_MS = 2_500;
export const TYPING_IDLE_MS = 3_000;

export interface TypingTarget {
  channelId: string;
  parentId: string | null;
}

export interface TypingSender {
  /** Dipanggil tiap perubahan isi composer. */
  input(target: TypingTarget, text: string): void;
  /** Kirim stop bila sebelumnya start sudah terkirim. */
  stop(): void;
  /** Lupakan state tanpa mengirim apa pun (koneksi putus). */
  reset(): void;
}

export function createTypingSender(opts: {
  send: (type: "typing.start" | "typing.stop", target: TypingTarget) => void;
  now?: () => number;
}): TypingSender {
  const now = opts.now ?? (() => Date.now());
  let current: TypingTarget | null = null;
  let started = false;
  let lastStartAt = 0;
  let idleTimer: ReturnType<typeof setTimeout> | null = null;

  const clearIdle = () => {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = null;
  };

  const sender: TypingSender = {
    input(target, text) {
      const trimmed = text.trim();
      // Teks kosong atau slash command (/help dst.) bukan "mengetik pesan".
      if (!trimmed || trimmed.startsWith("/")) {
        sender.stop();
        return;
      }
      if (current && (current.channelId !== target.channelId || current.parentId !== target.parentId)) {
        sender.stop();
      }
      current = { channelId: target.channelId, parentId: target.parentId };
      const t = now();
      if (!started || t - lastStartAt >= TYPING_START_INTERVAL_MS) {
        opts.send("typing.start", current);
        started = true;
        lastStartAt = t;
      }
      clearIdle();
      idleTimer = setTimeout(() => sender.stop(), TYPING_IDLE_MS);
    },
    stop() {
      clearIdle();
      if (started && current) opts.send("typing.stop", current);
      started = false;
    },
    reset() {
      clearIdle();
      started = false;
      current = null;
    },
  };
  return sender;
}
