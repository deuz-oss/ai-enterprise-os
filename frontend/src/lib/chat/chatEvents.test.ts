import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { coalesce, routeChatEvent, type ChatEventDeps } from "./chatEvents";

function makeDeps(active: string | null) {
  const deps: ChatEventDeps = {
    activeChannel: { current: active },
    invalidateChannels: vi.fn(),
    mergeActive: vi.fn(),
    markActiveRead: vi.fn(),
  };
  return deps;
}

describe("routeChatEvent", () => {
  it("tidak refetch/merge/markRead untuk event non-message (pong, presence, typing, error)", () => {
    const deps = makeDeps("c1");
    routeChatEvent({ event: "pong" }, deps);
    routeChatEvent({ event: "presence.snapshot", users: [] }, deps);
    routeChatEvent({ event: "presence.updated", user_id: "u1", status: "online" }, deps);
    routeChatEvent(
      { event: "typing", channel_id: "c1", parent_id: null, user_id: "u1", user_name: "Budi", state: "start" },
      deps
    );
    routeChatEvent({ event: "error", code: "rate_limited" }, deps);
    expect(deps.invalidateChannels).not.toHaveBeenCalled();
    expect(deps.mergeActive).not.toHaveBeenCalled();
    expect(deps.markActiveRead).not.toHaveBeenCalled();
  });

  it("message.* di channel aktif: invalidate daftar channel + merge + markRead", () => {
    const deps = makeDeps("c1");
    routeChatEvent({ event: "message.created", channel_id: "c1" }, deps);
    expect(deps.invalidateChannels).toHaveBeenCalledTimes(1);
    expect(deps.mergeActive).toHaveBeenCalledTimes(1);
    expect(deps.markActiveRead).toHaveBeenCalledTimes(1);
  });

  it("message.* di channel lain hanya invalidate daftar channel", () => {
    const deps = makeDeps("c1");
    routeChatEvent({ event: "message.reaction", channel_id: "c2" }, deps);
    expect(deps.invalidateChannels).toHaveBeenCalledTimes(1);
    expect(deps.mergeActive).not.toHaveBeenCalled();
    expect(deps.markActiveRead).not.toHaveBeenCalled();
  });

  it("tanpa channel aktif tidak merge/markRead", () => {
    const deps = makeDeps(null);
    routeChatEvent({ event: "message.created", channel_id: "c1" }, deps);
    expect(deps.mergeActive).not.toHaveBeenCalled();
    expect(deps.markActiveRead).not.toHaveBeenCalled();
  });

  it("membaca ref TERBARU (channel berganti setelah handler dipasang)", () => {
    const deps = makeDeps("c1");
    const handler = (e: { event: string; channel_id?: string }) => routeChatEvent(e, deps);
    deps.activeChannel.current = "c2";
    handler({ event: "message.created", channel_id: "c1" });
    expect(deps.mergeActive).not.toHaveBeenCalled();
    handler({ event: "message.created", channel_id: "c2" });
    expect(deps.mergeActive).toHaveBeenCalledTimes(1);
  });
});

describe("coalesce", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("panggilan pertama langsung, rentetan dalam jendela digabung jadi satu di akhir", () => {
    const fn = vi.fn();
    const run = coalesce(fn, 500);
    run();
    expect(fn).toHaveBeenCalledTimes(1);
    for (let i = 0; i < 10; i++) run();
    expect(fn).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(2000);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("cancel membuang panggilan tertunda", () => {
    const fn = vi.fn();
    const run = coalesce(fn, 500);
    run();
    run();
    run.cancel();
    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
