// Deteksi away di sisi klien: tab tersembunyi ATAU tanpa aktivitas selama
// 5 menit -> "away"; aktivitas atau tab terlihat lagi -> "online".
// Hanya memanggil onChange saat status benar-benar berubah.

import type { PresenceStatus } from "./presenceStore";

export const AWAY_IDLE_MS = 5 * 60_000;
const ACTIVITY_THROTTLE_MS = 1_000;
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart", "mousemove"] as const;

interface ListenerTarget {
  addEventListener(type: string, fn: () => void, opts?: AddEventListenerOptions | boolean): void;
  removeEventListener(type: string, fn: () => void, opts?: EventListenerOptions | boolean): void;
}

export interface AwayDetector {
  start(): void;
  stop(): void;
  current(): PresenceStatus;
}

export function createAwayDetector(opts: {
  onChange: (status: PresenceStatus) => void;
  doc?: ListenerTarget & { hidden: boolean };
  win?: ListenerTarget;
  now?: () => number;
  idleMs?: number;
}): AwayDetector {
  const doc = opts.doc ?? (document as unknown as ListenerTarget & { hidden: boolean });
  const win = opts.win ?? (window as unknown as ListenerTarget);
  const now = opts.now ?? (() => Date.now());
  const idleMs = opts.idleMs ?? AWAY_IDLE_MS;

  let lastActivity = now();
  let lastActivityHandled = -Infinity;
  let status: PresenceStatus = "online";
  let idleTimer: ReturnType<typeof setTimeout> | null = null;
  let running = false;

  function compute(): PresenceStatus {
    if (doc.hidden) return "away";
    return now() - lastActivity >= idleMs ? "away" : "online";
  }

  function update() {
    const next = compute();
    if (next !== status) {
      status = next;
      opts.onChange(next);
    }
  }

  function scheduleIdle() {
    if (idleTimer) clearTimeout(idleTimer);
    const remaining = Math.max(0, lastActivity + idleMs - now());
    idleTimer = setTimeout(() => {
      idleTimer = null;
      if (!running) return;
      if (now() - lastActivity >= idleMs) update();
      else scheduleIdle();
    }, remaining);
  }

  const onActivity = () => {
    const t = now();
    if (t - lastActivityHandled < ACTIVITY_THROTTLE_MS) return;
    lastActivityHandled = t;
    lastActivity = t;
    if (!idleTimer) scheduleIdle();
    if (status === "away") update();
  };

  const onVisibility = () => {
    if (!doc.hidden) {
      lastActivity = now();
      scheduleIdle();
    }
    update();
  };

  return {
    start() {
      if (running) return;
      running = true;
      lastActivity = now();
      status = compute();
      ACTIVITY_EVENTS.forEach((ev) => win.addEventListener(ev, onActivity, { passive: true }));
      doc.addEventListener("visibilitychange", onVisibility);
      scheduleIdle();
    },
    stop() {
      running = false;
      if (idleTimer) clearTimeout(idleTimer);
      idleTimer = null;
      ACTIVITY_EVENTS.forEach((ev) => win.removeEventListener(ev, onActivity));
      doc.removeEventListener("visibilitychange", onVisibility);
    },
    current() {
      return status;
    },
  };
}
