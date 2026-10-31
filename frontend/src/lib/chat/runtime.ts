// Merangkai socket + store + detektor away + pengirim typing menjadi satu
// runtime per sesi. Tanpa React; provider di components/chat hanya memanggil
// start()/stop() dan mengekspos store-nya lewat hook.

import { createAwayDetector, type AwayDetector } from "./awayDetector";
import {
  ChatSocket,
  type ChatServerEvent,
  type ConnectionState,
  type WebSocketFactory,
} from "./chatSocket";
import { createPresenceStore, type PresenceStore } from "./presenceStore";
import { createTypingSender, type TypingSender } from "./typingSender";
import { createTypingStore, type TypingEvent, type TypingStore } from "./typingStore";

export interface ValueStore<T> {
  subscribe(listener: () => void): () => void;
  get(): T;
  set(value: T): void;
}

export function createValueStore<T>(initial: T): ValueStore<T> {
  let value = initial;
  const listeners = new Set<() => void>();
  return {
    subscribe(l) {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    get: () => value,
    set(next) {
      if (Object.is(next, value)) return;
      value = next;
      listeners.forEach((l) => l());
    },
  };
}

export interface ChatRuntime {
  presence: PresenceStore;
  typing: TypingStore;
  connection: ValueStore<ConnectionState>;
  sender: TypingSender;
  onMessageEvent(listener: (e: ChatServerEvent) => void): () => void;
  /** Dipakai juga oleh test untuk menyuntik event. */
  dispatch(e: ChatServerEvent): void;
  setSelfId(id: string | null): void;
  start(): void;
  stop(): void;
}

export function createChatRuntime(opts: {
  getUrl: () => string | null;
  probeAuth: () => Promise<unknown>;
  tokenKey?: string;
  createSocket?: WebSocketFactory;
  away?: (onChange: (s: "online" | "away") => void) => AwayDetector;
}): ChatRuntime {
  const presence = createPresenceStore();
  const typing = createTypingStore();
  const connection = createValueStore<ConnectionState>("idle");
  const messageListeners = new Set<(e: ChatServerEvent) => void>();
  let selfId: string | null = null;
  let running = false;

  const away = (opts.away ?? ((onChange) => createAwayDetector({ onChange })))((status) => {
    socket.send({ type: "presence.set", status });
  });

  const socket: ChatSocket = new ChatSocket({
    getUrl: opts.getUrl,
    probeAuth: opts.probeAuth,
    createSocket: opts.createSocket,
    onEvent: (e) => runtime.dispatch(e),
    onOpen: () => {
      socket.send({ type: "presence.set", status: away.current() });
    },
    onStateChange: (state) => {
      connection.set(state);
      if (state !== "open") {
        // Tanpa koneksi, presence & typing tidak diketahui -- jangan tampilkan basi.
        presence.reset();
        typing.reset();
        sender.reset();
      }
    },
  });

  const sender = createTypingSender({
    send: (type, target) =>
      socket.send(
        { type, channel_id: target.channelId, parent_id: target.parentId },
        { droppable: true }
      ),
  });

  const onOnline = () => socket.reconnectNow();
  const onVisible = () => {
    if (!document.hidden) socket.reconnectNow();
  };
  const onPageHide = () => sender.stop();
  const tokenKey = opts.tokenKey ?? "aeos_token";
  const onStorage = (e: StorageEvent) => {
    // Logout di tab lain -> hentikan koneksi tab ini juga.
    if (e.key === tokenKey && !e.newValue) runtime.stop();
  };

  const runtime: ChatRuntime = {
    presence,
    typing,
    connection,
    sender,
    onMessageEvent(listener) {
      messageListeners.add(listener);
      return () => messageListeners.delete(listener);
    },
    dispatch(e) {
      switch (e.event) {
        case "presence.snapshot":
          presence.applySnapshot(Array.isArray(e.users) ? (e.users as { user_id: string; status: string }[]) : []);
          return;
        case "presence.updated":
          presence.applyUpdate(e.user_id as string, e.status as string);
          return;
        case "typing":
          if (e.user_id === selfId) return;
          typing.apply(e as unknown as TypingEvent);
          return;
        case "pong":
        case "error":
          return;
        default:
          if (e.event.startsWith("message.")) messageListeners.forEach((l) => l(e));
      }
    },
    setSelfId(id) {
      selfId = id;
    },
    start() {
      if (running) return;
      running = true;
      socket.start();
      away.start();
      if (typeof window !== "undefined") {
        window.addEventListener("online", onOnline);
        window.addEventListener("pagehide", onPageHide);
        window.addEventListener("storage", onStorage);
        document.addEventListener("visibilitychange", onVisible);
      }
    },
    stop() {
      if (!running) return;
      running = false;
      sender.stop();
      socket.stop();
      away.stop();
      if (typeof window !== "undefined") {
        window.removeEventListener("online", onOnline);
        window.removeEventListener("pagehide", onPageHide);
        window.removeEventListener("storage", onStorage);
        document.removeEventListener("visibilitychange", onVisible);
      }
      presence.reset();
      typing.reset();
    },
  };
  return runtime;
}
