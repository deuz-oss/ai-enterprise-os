import { describe, expect, it } from "vitest";
import { canOpenPath, guardedAreaOf } from "./navAccess";

describe("guardedAreaOf", () => {
  it("segmen pertama path, termasuk halaman detail", () => {
    expect(guardedAreaOf("/clients")).toBe("clients");
    expect(guardedAreaOf("/clients/abc-123")).toBe("clients");
    expect(guardedAreaOf("/job-orders/1")).toBe("job-orders");
  });

  it("halaman terbuka -> null", () => {
    for (const p of ["/", "/chat", "/pages/1", "/portal-saya", "/platform"]) {
      expect(guardedAreaOf(p)).toBeNull();
    }
  });
});

describe("canOpenPath", () => {
  const finance = ["payment-requests", "finance", "accounting", "rates", "billing"];

  it("mengikuti allowed_areas dari backend", () => {
    expect(canOpenPath("/finance", finance)).toBe(true);
    expect(canOpenPath("/payroll", finance)).toBe(false);
    expect(canOpenPath("/employees/1", finance)).toBe(false);
  });

  it("halaman terbuka selalu boleh", () => {
    expect(canOpenPath("/", [])).toBe(true);
    expect(canOpenPath("/chat", [])).toBe(true);
  });

  it("allowed_areas belum diketahui -> tidak memblokir", () => {
    expect(canOpenPath("/payroll", undefined)).toBe(true);
  });
});
