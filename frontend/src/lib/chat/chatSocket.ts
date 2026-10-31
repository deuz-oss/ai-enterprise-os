// Koneksi WebSocket chat bersama (presence + typing + event pesan).
// Murni TypeScript tanpa React supaya bisa dites di Vitest (env node) dengan
// WebSocket palsu dan fake timers. Dibungkus React di
// components/chat/ChatRealtimeProvider.tsx.

export type ConnectionState = "idle" | "connecting" | "open" | "closed";

/** Frame server->klien. Kunci `event` selalu ada; sisanya per jenis event. */
export interface ChatServerEvent {
  event: string;
  [key: string]: unknown;
}

export type ChatClientFrame =
  | { type: "hello"; features: string[] }
  | { type: "ping" }
  | { type: "presence.set"; status: "online" | "away" }
  | { type: "typing.start" | "typing.stop"; channel_id: string; parent_id: string | null };

/** Bentuk minimal WebSocket yang dipakai (memudahkan WebSocket palsu di test). */
export interface WebSocketLike {
  readyState: number;
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: { code: number }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  send(data: string): void;
  close(code?: number): void;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export const PING_INTERVAL_MS = 25_000;
/** Tanpa frame masuk selama ini (pong ikut dihitung) -> anggap koneksi mati. */
export const WATCHDOG_MS = 60_000;
export const BACKOFF_BASE_MS = 1_000;
export const BACKOFF_MAX_MS = 30_000;
/** Close 1008 bisa berarti rate limit -- jangan langsung menyerbu lagi. */
export const POLICY_CLOSE_MIN_DELAY_MS = 5_000;
/** Koneksi dianggap stabil (backoff di-reset) setelah terbuka selama ini. */
export const STABLE_AFTER_MS = 10_000;
/** Gagal sebelum open sebanyak ini berturut-turut -> cek sesi lewat /auth/me. */
export const PROBE_AFTER_FAILURES = 3;
/** Anggaran klien: di bawah batas server (20 frame / 10 dtk) supaya tidak kena 1008. */
export const BUCKET_CAPACITY = 15;
export const BUCKET_WINDOW_MS = 10_000;

const WS_OPEN = 1;

/**
 * URL WS dibentuk dari API_URL (relatif `/api/v1` atau absolut termasuk path
 * prefix-nya). Dulu path `/api/v1` di-hardcode dan prefix pada VITE_API_URL
 * absolut terbuang.
 */
export function buildChatWsUrl(
  apiUrl: string,
  token: string,
  loc: { protocol: string; host: string }
): string {
  const base = new URL(apiUrl, `${loc.protocol}//${loc.host}`);
  const proto = base.protocol === "https:" ? "wss:" : "ws:";
  const path = base.pathname.replace(/\/+$/, "");
  return `${proto}//${base.host}${path}/chat/ws?token=${encodeURIComponent(token)}`;
}

/** Token bucket sederhana; `now` disuntikkan supaya deterministik di test. */
export class TokenBucket {
  private tokens: number;
  private last: number;
  constructor(
    private readonly capacity: number,
    private readonly windowMs: number,
    private readonly now: () => number
  ) {
    this.tokens = capacity;
    this.last = now();
  }

  private refill() {
    const t = this.now();
    this.tokens = Math.min(this.capacity, this.tokens + ((t - this.last) * this.capacity) / this.windowMs);
    this.last = t;
  }

  /** `force` = frame wajib (ping/hello/presence): tetap dihitung, tidak ditolak. */
  take(force: boolean): boolean {
    this.refill();
    if (this.tokens < 1 && !force) return false;
    this.tokens -= 1;
    return true;
  }
}

export interface ChatSocketOptions {
  /** URL lengkap, atau null bila tidak ada token (tidak menyambung). */
  getUrl: () => string | null;
  createSocket?: WebSocketFactory;
  /** Cek sesi; 401 di sana memicu alur sesi-habis milik api client. */
  probeAuth: () => Promise<unknown>;
  onEvent: (event: ChatServerEvent) => void;
  onOpen?: () => void;
  onStateChange?: (state: ConnectionState) => void;
  now?: () => number;
  random?: () => number;
}

export class ChatSocket {
  private ws: WebSocketLike | null = null;
  private state: ConnectionState = "idle";
  private stopped = true;
  private attempt = 0;
  private failuresBeforeOpen = 0;
  private openedAt: number | null = null;
  private lastRx = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private readonly now: () => number;
  private readonly random: () => number;
  private readonly createSocket: WebSocketFactory;
  private bucket: TokenBucket;

  constructor(private readonly opts: ChatSocketOptions) {
    this.now = opts.now ?? (() => Date.now());
    this.random = opts.random ?? Math.random;
    this.createSocket = opts.createSocket ?? ((url) => new WebSocket(url) as unknown as WebSocketLike);
    this.bucket = new TokenBucket(BUCKET_CAPACITY, BUCKET_WINDOW_MS, this.now);
  }

  getState(): ConnectionState {
    return this.state;
  }

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    this.attempt = 0;
    this.failuresBeforeOpen = 0;
    this.connect();
  }

  stop() {
    this.stopped = true;
    this.clearReconnect();
    this.clearPing();
    const ws = this.ws;
    this.ws = null;
    if (ws) {
      try {
        ws.close(1000);
      } catch {
        // abaikan
      }
    }
    this.setState("idle");
  }

  /** Dipanggil saat `online` / tab kembali terlihat: jangan tunggu backoff. */
  reconnectNow() {
    if (this.stopped || this.ws) return;
    this.clearReconnect();
    this.attempt = 0;
    this.connect();
  }

  /**
   * Kirim frame. `droppable` (typing) boleh dibuang saat anggaran habis;
   * frame lain selalu dikirim. Mengembalikan false bila tidak terkirim.
   */
  send(frame: ChatClientFrame, options: { droppable?: boolean } = {}): boolean {
    const ws = this.ws;
    if (!ws || this.state !== "open" || ws.readyState !== WS_OPEN) return false;
    if (!this.bucket.take(!options.droppable)) return false;
    try {
      ws.send(JSON.stringify(frame));
      return true;
    } catch {
      return false;
    }
  }

  private setState(next: ConnectionState) {
    if (this.state === next) return;
    this.state = next;
    this.opts.onStateChange?.(next);
  }

  private connect() {
    if (this.stopped) return;
    const url = this.opts.getUrl();
    if (!url) {
      this.setState("closed");
      return;
    }
    this.openedAt = null;
    this.setState("connecting");
    let ws: WebSocketLike;
    try {
      ws = this.createSocket(url);
    } catch {
      this.handleClose(1006);
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      if (this.ws !== ws) return;
      this.openedAt = this.now();
      this.lastRx = this.now();
      this.failuresBeforeOpen = 0;
      this.bucket = new TokenBucket(BUCKET_CAPACITY, BUCKET_WINDOW_MS, this.now);
      this.setState("open");
      this.send({ type: "hello", features: ["presence", "typing"] });
      this.startPing(ws);
      this.opts.onOpen?.();
    };
    ws.onmessage = (ev) => {
      if (this.ws !== ws) return;
      this.lastRx = this.now();
      if (typeof ev.data !== "string") return;
      let parsed: unknown;
      try {
        parsed = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (parsed && typeof parsed === "object" && typeof (parsed as ChatServerEvent).event === "string") {
        this.opts.onEvent(parsed as ChatServerEvent);
      }
    };
    ws.onerror = () => {
      // onclose selalu menyusul; penanganan di sana.
    };
    ws.onclose = (ev) => {
      if (this.ws !== ws) return;
      this.ws = null;
      this.handleClose(ev.code);
    };
  }

  private handleClose(code: number) {
    this.clearPing();
    const wasOpen = this.openedAt !== null;
    const stable = wasOpen && this.now() - (this.openedAt as number) >= STABLE_AFTER_MS;
    this.openedAt = null;
    this.setState("closed");
    if (this.stopped) return;

    if (stable) this.attempt = 0;
    if (!wasOpen) this.failuresBeforeOpen += 1;

    // Handshake yang ditolak terlihat sebagai 1006 di browser (tidak bisa
    // dibedakan dari gangguan jaringan); 1008 setelah open bisa token
    // dicabut atau rate limit. Keduanya: tanya /auth/me -- kalau 401, api
    // client sendiri yang mengarahkan ke login.
    const probe =
      code === 1008 ||
      (!wasOpen && this.failuresBeforeOpen > 0 && this.failuresBeforeOpen % PROBE_AFTER_FAILURES === 0);
    if (probe) this.opts.probeAuth().catch(() => undefined);

    const base = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** this.attempt);
    // "Equal jitter": separuh tetap + separuh acak -- tidak pernah ~0 dtk.
    let delay = base / 2 + this.random() * (base / 2);
    if (code === 1008) delay = Math.max(delay, POLICY_CLOSE_MIN_DELAY_MS);
    this.attempt += 1;
    this.clearReconnect();
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private startPing(ws: WebSocketLike) {
    this.clearPing();
    this.pingTimer = setInterval(() => {
      if (this.ws !== ws) return;
      if (this.now() - this.lastRx > WATCHDOG_MS) {
        // Koneksi "setengah mati" (mis. laptop tidur) -- tutup & sambung ulang.
        this.ws = null;
        try {
          ws.close();
        } catch {
          // abaikan
        }
        this.handleClose(1006);
        return;
      }
      this.send({ type: "ping" });
    }, PING_INTERVAL_MS);
  }

  private clearPing() {
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.pingTimer = null;
  }

  private clearReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }
}
