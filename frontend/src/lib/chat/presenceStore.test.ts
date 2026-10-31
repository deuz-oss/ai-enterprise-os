import { describe, expect, it, vi } from "vitest";
import { createPresenceStore } from "./presenceStore";

describe("presenceStore", () => {
  it("snapshot mengganti penuh: user yang hilang dari scope ikut terhapus", () => {
    const s = createPresenceStore();
    s.applySnapshot([
      { user_id: "a", status: "online" },
      { user_id: "b", status: "away" },
    ]);
    expect(s.get("a")).toBe("online");
    expect(s.get("b")).toBe("away");
    s.applySnapshot([{ user_id: "b", status: "online" }]);
    expect(s.get("a")).toBeUndefined();
    expect(s.get("b")).toBe("online");
    expect(s.size()).toBe(1);
  });

  it("presence.updated offline menghapus entri; status tak dikenal juga", () => {
    const s = createPresenceStore();
    s.applyUpdate("a", "online");
    s.applyUpdate("b", "away");
    s.applyUpdate("a", "offline");
    s.applyUpdate("b", "aneh");
    expect(s.get("a")).toBeUndefined();
    expect(s.get("b")).toBeUndefined();
  });

  it("reset (koneksi putus) membuat semua status tidak diketahui", () => {
    const s = createPresenceStore();
    s.applySnapshot([{ user_id: "a", status: "online" }]);
    s.reset();
    expect(s.get("a")).toBeUndefined();
  });

  it("listener hanya dipanggil saat state benar-benar berubah", () => {
    const s = createPresenceStore();
    const l = vi.fn();
    s.subscribe(l);
    s.applySnapshot([{ user_id: "a", status: "online" }]);
    s.applySnapshot([{ user_id: "a", status: "online" }]);
    s.applyUpdate("a", "online");
    s.applyUpdate("x", "offline");
    s.reset();
    s.reset();
    expect(l).toHaveBeenCalledTimes(2);
  });
});
