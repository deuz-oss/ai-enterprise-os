import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  BUCKET_CAPACITY,
  ChatSocket,
  PING_INTERVAL_MS,
  POLICY_CLOSE_MIN_DELAY_MS,
  WATCHDOG_MS,
  buildChatWsUrl,
  type ChatServerEvent,
  type WebSocketLike,
} from "./chatSocket";

class FakeWS implements WebSocketLike {
  readyState = 0;
  onopen: ((ev: unknown) => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  sent: Record<string, unknown>[] = [];
  closedWith: number | undefined | null = null;
  constructor(public url: string) {}
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close(code?: number) {
    this.closedWith = code;
    this.readyState = 3;
  }
  // --- helper test ---
  open() {
    this.readyState = 1;
    this.onopen?.({});
  }
  receive(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
  serverClose(code: number) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

function setup(overrides: { token?: string | null } = {}) {
  const sockets: FakeWS[] = [];
  const events: ChatServerEvent[] = [];
  const states: string[] = [];
  const probeAuth = vi.fn(() => Promise.resolve());
  const onOpen = vi.fn();
  const token = overrides.token === undefined ? "tok" : overrides.token;
  const socket = new ChatSocket({
    getUrl: () => (token ? `ws://x/api/v1/chat/ws?token=${token}` : null),
    createSocket: (url) => {
      const ws = new FakeWS(url);
      sockets.push(ws);
      return ws;
    },
    probeAuth,
    onEvent: (e) => events.push(e),
    onOpen,
    onStateChange: (s) => states.push(s),
    random: () => 0, // jitter minimum -> delay = base/2
  });
  return { socket, sockets, events, states, probeAuth, onOpen };
}

describe("buildChatWsUrl", () => {
  const loc = { protocol: "http:", host: "app.local:5173" };
  it("API_URL relatif memakai host halaman", () => {
    expect(buildChatWsUrl("/api/v1", "a b", loc)).toBe("ws://app.local:5173/api/v1/chat/ws?token=a%20b");
  });
  it("API_URL absolut mempertahankan host, skema, dan path prefix", () => {
    expect(buildChatWsUrl("https://api.contoh.id/aeos/api/v1/", "t", loc)).toBe(
      "wss://api.contoh.id/aeos/api/v1/chat/ws?token=t"
    );
  });
  it("halaman https -> wss", () => {
    expect(buildChatWsUrl("/api/v1", "t", { protocol: "https:", host: "h" })).toBe("wss://h/api/v1/chat/ws?token=t");
  });
});

describe("ChatSocket", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("kirim hello saat open lalu panggil onOpen; event diteruskan", () => {
    const { socket, sockets, events, onOpen } = setup();
    socket.start();
    sockets[0].open();
    expect(sockets[0].sent[0]).toEqual({ type: "hello", features: ["presence", "typing"] });
    expect(onOpen).toHaveBeenCalledTimes(1);
    sockets[0].receive({ event: "pong" });
    sockets[0].onmessage?.({ data: "bukan json" });
    expect(events).toEqual([{ event: "pong" }]);
  });

  it("ping tiap 25 dtk selama server menjawab", () => {
    const { socket, sockets } = setup();
    socket.start();
    sockets[0].open();
    for (let i = 0; i < 3; i++) {
      vi.advanceTimersByTime(PING_INTERVAL_MS);
      sockets[0].receive({ event: "pong" });
    }
    expect(sockets[0].sent.filter((f) => f.type === "ping")).toHaveLength(3);
    expect(sockets).toHaveLength(1);
  });

  it("watchdog: tanpa frame masuk > 60 dtk -> tutup dan sambung ulang", () => {
    const { socket, sockets } = setup();
    socket.start();
    sockets[0].open();
    vi.advanceTimersByTime(WATCHDOG_MS + PING_INTERVAL_MS);
    expect(sockets[0].closedWith).not.toBeNull();
    vi.advanceTimersByTime(1000);
    expect(sockets.length).toBe(2);
  });

  it("backoff eksponensial 1/2/4/... dtk (maks 30) saat gagal tersambung", () => {
    const { socket, sockets } = setup();
    socket.start();
    const expected = [1000, 2000, 4000, 8000, 16000, 30000, 30000];
    for (const base of expected) {
      const n = sockets.length;
      sockets[n - 1].serverClose(1006);
      vi.advanceTimersByTime(base / 2 - 1);
      expect(sockets.length).toBe(n);
      vi.advanceTimersByTime(1);
      expect(sockets.length).toBe(n + 1);
    }
  });

  it("backoff di-reset setelah koneksi stabil >= 10 dtk", () => {
    const { socket, sockets } = setup();
    socket.start();
    sockets[0].serverClose(1006);
    vi.advanceTimersByTime(500);
    sockets[1].serverClose(1006);
    vi.advanceTimersByTime(1000);
    sockets[2].open();
    vi.advanceTimersByTime(10_000);
    sockets[2].receive({ event: "pong" });
    sockets[2].serverClose(1001);
    vi.advanceTimersByTime(500);
    expect(sockets.length).toBe(4);
  });

  it("probe /auth/me setiap 3 kegagalan handshake berturut-turut", () => {
    const { socket, sockets, probeAuth } = setup();
    socket.start();
    sockets[0].serverClose(1006);
    vi.advanceTimersByTime(500);
    sockets[1].serverClose(1006);
    expect(probeAuth).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    sockets[2].serverClose(1006);
    expect(probeAuth).toHaveBeenCalledTimes(1);
  });

  it("close 1008 setelah open: probe /auth/me dan tunggu minimal 5 dtk", () => {
    const { socket, sockets, probeAuth } = setup();
    socket.start();
    sockets[0].open();
    sockets[0].serverClose(1008);
    expect(probeAuth).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(POLICY_CLOSE_MIN_DELAY_MS - 1);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(2);
  });

  it("anggaran frame: typing dibuang saat habis, ping/presence tetap terkirim", () => {
    const { socket, sockets } = setup();
    socket.start();
    sockets[0].open(); // hello = 1 token
    let typingSent = 0;
    for (let i = 0; i < 30; i++) {
      if (socket.send({ type: "typing.start", channel_id: "c", parent_id: null }, { droppable: true })) typingSent++;
    }
    expect(typingSent).toBe(BUCKET_CAPACITY - 1);
    expect(socket.send({ type: "presence.set", status: "away" })).toBe(true);
    expect(socket.send({ type: "ping" })).toBe(true);
  });

  it("tanpa token tidak menyambung; stop() menutup dan menghentikan reconnect", () => {
    const none = setup({ token: null });
    none.socket.start();
    expect(none.sockets).toHaveLength(0);

    const { socket, sockets, states } = setup();
    socket.start();
    sockets[0].open();
    socket.stop();
    expect(sockets[0].closedWith).toBe(1000);
    vi.advanceTimersByTime(60_000);
    expect(sockets).toHaveLength(1);
    expect(states[states.length - 1]).toBe("idle");
  });

  it("send gagal saat belum open", () => {
    const { socket } = setup();
    socket.start();
    expect(socket.send({ type: "ping" })).toBe(false);
  });
});
