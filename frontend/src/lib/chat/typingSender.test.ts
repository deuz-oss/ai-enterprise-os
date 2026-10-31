import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createTypingSender, TYPING_IDLE_MS, TYPING_START_INTERVAL_MS } from "./typingSender";

const ch1 = { channelId: "c1", parentId: null };
const ch2 = { channelId: "c2", parentId: null };

function setup() {
  const sent: [string, string, string | null][] = [];
  const sender = createTypingSender({
    send: (type, t) => sent.push([type, t.channelId, t.parentId]),
  });
  return { sent, sender };
}

describe("typingSender", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("start paling sering 1x per 2,5 dtk selama mengetik terus", () => {
    const { sent, sender } = setup();
    // Ketik 1 karakter tiap 200 ms selama 6 dtk.
    for (let t = 0; t < 6000; t += 200) {
      sender.input(ch1, "halo" + t);
      vi.advanceTimersByTime(200);
    }
    const starts = sent.filter((s) => s[0] === "typing.start");
    expect(starts).toHaveLength(Math.ceil(6000 / TYPING_START_INTERVAL_MS));
    expect(sent.some((s) => s[0] === "typing.stop")).toBe(false);
  });

  it("stop otomatis setelah idle 3 dtk", () => {
    const { sent, sender } = setup();
    sender.input(ch1, "a");
    vi.advanceTimersByTime(TYPING_IDLE_MS - 1);
    expect(sent).toEqual([["typing.start", "c1", null]]);
    vi.advanceTimersByTime(1);
    expect(sent[sent.length - 1]).toEqual(["typing.stop", "c1", null]);
  });

  it("stop eksplisit (kirim pesan / blur) hanya bila start sudah terkirim", () => {
    const { sent, sender } = setup();
    sender.stop();
    expect(sent).toEqual([]);
    sender.input(ch1, "a");
    sender.stop();
    sender.stop();
    expect(sent).toEqual([
      ["typing.start", "c1", null],
      ["typing.stop", "c1", null],
    ]);
  });

  it("ganti channel: stop untuk channel lama lalu start di channel baru", () => {
    const { sent, sender } = setup();
    sender.input(ch1, "a");
    sender.input(ch2, "b");
    expect(sent).toEqual([
      ["typing.start", "c1", null],
      ["typing.stop", "c1", null],
      ["typing.start", "c2", null],
    ]);
  });

  it("teks kosong atau slash command tidak dianggap mengetik", () => {
    const { sent, sender } = setup();
    sender.input(ch1, "   ");
    sender.input(ch1, "/help");
    expect(sent).toEqual([]);
  });

  it("reset (koneksi putus) melupakan state tanpa mengirim apa pun", () => {
    const { sent, sender } = setup();
    sender.input(ch1, "a");
    sender.reset();
    vi.advanceTimersByTime(TYPING_IDLE_MS * 2);
    expect(sent).toEqual([["typing.start", "c1", null]]);
  });
});
