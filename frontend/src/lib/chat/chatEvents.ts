// Routing event WS ke halaman Chat. Hanya `message.*` yang boleh memicu
// refetch/merge/markRead -- dulu SETIAP frame (termasuk yang tanpa
// channel_id) memicu GET pesan + POST read-all, jadi presence/typing/pong
// akan menjadi badai request.

import type { ChatServerEvent } from "./chatSocket";

export interface ChatEventDeps {
  /** Ref ke channel aktif TERBARU (bukan nilai yang tertangkap closure). */
  activeChannel: { current: string | null };
  invalidateChannels: () => void;
  mergeActive: () => void;
  markActiveRead: () => void;
}

export function isMessageEvent(e: ChatServerEvent): boolean {
  return typeof e.event === "string" && e.event.startsWith("message.");
}

export function routeChatEvent(e: ChatServerEvent, deps: ChatEventDeps): void {
  if (!isMessageEvent(e)) return;
  deps.invalidateChannels();
  const channelId = typeof e.channel_id === "string" ? e.channel_id : null;
  const active = deps.activeChannel.current;
  if (active && (!channelId || channelId === active)) {
    deps.mergeActive();
    deps.markActiveRead();
  }
}

/**
 * Leading + trailing throttle: panggilan pertama langsung jalan, panggilan
 * berikutnya dalam jendela `ms` digabung jadi SATU panggilan di akhir
 * jendela. Event beruntun (mis. 10 reaksi sekaligus) -> paling banyak 2 request.
 */
export function coalesce(fn: () => void, ms: number): (() => void) & { cancel(): void } {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pending = false;
  const run = () => {
    if (timer) {
      pending = true;
      return;
    }
    fn();
    const tick = () => {
      if (pending) {
        pending = false;
        fn();
        timer = setTimeout(tick, ms);
      } else {
        timer = null;
      }
    };
    timer = setTimeout(tick, ms);
  };
  return Object.assign(run, {
    cancel() {
      if (timer) clearTimeout(timer);
      timer = null;
      pending = false;
    },
  });
}
