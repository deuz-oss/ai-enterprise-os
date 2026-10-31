import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AWAY_IDLE_MS, createAwayDetector } from "./awayDetector";

class FakeTarget {
  listeners = new Map<string, Set<() => void>>();
  hidden = false;
  addEventListener(type: string, fn: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(fn);
  }
  removeEventListener(type: string, fn: () => void) {
    this.listeners.get(type)?.delete(fn);
  }
  fire(type: string) {
    this.listeners.get(type)?.forEach((fn) => fn());
  }
}

function setup() {
  const doc = new FakeTarget();
  const win = new FakeTarget();
  const changes: string[] = [];
  const det = createAwayDetector({ onChange: (s) => changes.push(s), doc, win });
  return { doc, win, changes, det };
}

describe("awayDetector", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("tab tersembunyi -> away; terlihat lagi -> online", () => {
    const { doc, changes, det } = setup();
    det.start();
    doc.hidden = true;
    doc.fire("visibilitychange");
    doc.hidden = false;
    doc.fire("visibilitychange");
    expect(changes).toEqual(["away", "online"]);
  });

  it("idle 5 menit -> away; aktivitas -> online", () => {
    const { win, changes, det } = setup();
    det.start();
    vi.advanceTimersByTime(AWAY_IDLE_MS - 1);
    expect(changes).toEqual([]);
    vi.advanceTimersByTime(1);
    expect(changes).toEqual(["away"]);
    win.fire("keydown");
    expect(changes).toEqual(["away", "online"]);
    expect(det.current()).toBe("online");
  });

  it("aktivitas menunda away; tidak ada notifikasi duplikat", () => {
    const { win, changes, det } = setup();
    det.start();
    vi.advanceTimersByTime(AWAY_IDLE_MS - 1000);
    win.fire("pointerdown");
    vi.advanceTimersByTime(AWAY_IDLE_MS - 1000);
    expect(changes).toEqual([]);
    vi.advanceTimersByTime(1000);
    win.fire("visibilitychange");
    vi.advanceTimersByTime(AWAY_IDLE_MS);
    expect(changes).toEqual(["away"]);
  });

  it("stop melepas listener", () => {
    const { win, doc, det } = setup();
    det.start();
    det.stop();
    expect([...win.listeners.values()].every((s) => s.size === 0)).toBe(true);
    expect(doc.listeners.get("visibilitychange")?.size).toBe(0);
  });
});
