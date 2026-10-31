import { describe, expect, it, vi } from "vitest";
import type { WebSocketLike } from "./chatSocket";
import { createChatRuntime } from "./runtime";

function setup() {
  const sockets: (WebSocketLike & { sent: unknown[]; open(): void; drop(code: number): void })[] = [];
  let awayStatus: "online" | "away" = "away";
  const rt = createChatRuntime({
    getUrl: () => "ws://x",
    probeAuth: () => Promise.resolve(),
    createSocket: () => {
      const ws = {
        readyState: 0,
        onopen: null as WebSocketLike["onopen"],
        onmessage: null as WebSocketLike["onmessage"],
        onclose: null as WebSocketLike["onclose"],
        onerror: null as WebSocketLike["onerror"],
        sent: [] as unknown[],
        send(d: string) {
          this.sent.push(JSON.parse(d));
        },
        close() {
          this.readyState = 3;
        },
        open() {
          this.readyState = 1;
          this.onopen?.({});
        },
        drop(code: number) {
          this.readyState = 3;
          this.onclose?.({ code });
        },
      };
      sockets.push(ws);
      return ws;
    },
    away: () => ({ start() {}, stop() {}, current: () => awayStatus }),
  });
  return { rt, sockets, setAway: (s: "online" | "away") => (awayStatus = s) };
}

describe("chat runtime", () => {
  it("setelah hello mengirim status presence klien saat ini", () => {
    const { rt, sockets } = setup();
    rt.start();
    sockets[0].open();
    expect(sockets[0].sent).toEqual([
      { type: "hello", features: ["presence", "typing"] },
      { type: "presence.set", status: "away" },
    ]);
    rt.stop();
  });

  it("hanya event message.* yang diteruskan ke listener halaman", () => {
    const { rt } = setup();
    const l = vi.fn();
    rt.onMessageEvent(l);
    rt.dispatch({ event: "pong" });
    rt.dispatch({ event: "presence.updated", user_id: "u", status: "online" });
    rt.dispatch({ event: "typing", channel_id: "c", parent_id: null, user_id: "u", user_name: "U", state: "start" });
    rt.dispatch({ event: "message.created", channel_id: "c" });
    expect(l).toHaveBeenCalledTimes(1);
    expect(rt.presence.get("u")).toBe("online");
  });

  it("typing dari diri sendiri diabaikan", () => {
    const { rt } = setup();
    rt.setSelfId("me");
    rt.dispatch({ event: "typing", channel_id: "c", parent_id: null, user_id: "me", user_name: "Saya", state: "start" });
    expect(rt.typing.get("c", null)).toEqual([]);
  });

  it("koneksi putus: presence & typing dikosongkan (tidak diketahui)", () => {
    const { rt, sockets } = setup();
    rt.start();
    sockets[0].open();
    rt.dispatch({ event: "presence.snapshot", users: [{ user_id: "u", status: "online" }] });
    rt.dispatch({ event: "typing", channel_id: "c", parent_id: null, user_id: "u", user_name: "U", state: "start" });
    sockets[0].drop(1006);
    expect(rt.presence.get("u")).toBeUndefined();
    expect(rt.typing.get("c", null)).toEqual([]);
    expect(rt.connection.get()).toBe("closed");
    rt.stop();
  });
});
