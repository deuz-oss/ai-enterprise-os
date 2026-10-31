import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createTypingStore, formatTypers, TYPING_CLIENT_TTL_MS } from "./typingStore";

const start = (user_id: string, parent_id: string | null = null, user_name = user_id.toUpperCase()) => ({
  channel_id: "c1",
  parent_id,
  user_id,
  user_name,
  state: "start" as const,
});

describe("typingStore", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("start kedaluwarsa sendiri tanpa stop (fallback klien)", () => {
    const s = createTypingStore();
    s.apply(start("a"));
    expect(s.get("c1", null).map((t) => t.userId)).toEqual(["a"]);
    vi.advanceTimersByTime(TYPING_CLIENT_TTL_MS + 1000);
    expect(s.get("c1", null)).toEqual([]);
  });

  it("start ulang memperpanjang TTL tanpa memicu render", () => {
    const s = createTypingStore();
    const l = vi.fn();
    s.subscribe(l);
    s.apply(start("a"));
    vi.advanceTimersByTime(5000);
    s.apply(start("a"));
    expect(l).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5000);
    expect(s.get("c1", null)).toHaveLength(1);
  });

  it("stop menghapus; key thread terpisah dari root channel", () => {
    const s = createTypingStore();
    s.apply(start("a"));
    s.apply(start("b", "p1"));
    expect(s.get("c1", null).map((t) => t.userId)).toEqual(["a"]);
    expect(s.get("c1", "p1").map((t) => t.userId)).toEqual(["b"]);
    s.apply({ ...start("a"), state: "stop" });
    expect(s.get("c1", null)).toEqual([]);
    expect(s.get("c1", "p1")).toHaveLength(1);
  });

  it("referensi daftar stabil selama komposisi sama (aman untuk useSyncExternalStore)", () => {
    const s = createTypingStore();
    s.apply(start("a"));
    const first = s.get("c1", null);
    s.apply(start("a"));
    expect(s.get("c1", null)).toBe(first);
    expect(s.get("zz", null)).toBe(s.get("yy", null));
  });

  it("reset mengosongkan semua", () => {
    const s = createTypingStore();
    s.apply(start("a"));
    s.reset();
    expect(s.get("c1", null)).toEqual([]);
  });
});

describe("formatTypers", () => {
  it("1, 2, dan banyak pengetik", () => {
    expect(formatTypers([])).toBe("");
    expect(formatTypers(["Budi"])).toBe("Budi sedang mengetik…");
    expect(formatTypers(["Budi", "Sari"])).toBe("Budi dan Sari sedang mengetik…");
    expect(formatTypers(["A", "B", "C"])).toBe("3 orang sedang mengetik…");
  });
});
