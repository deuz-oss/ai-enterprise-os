import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatRupiah, parseRupiahInput, safeNextPath } from "./client";

describe("formatDate", () => {
  it("memformat tanggal Indonesia", () => {
    expect(formatDate("2026-08-17")).toBe("17 Agu 2026");
  });

  it("parse YYYY-MM-DD sebagai tanggal lokal (tidak mundur sehari)", () => {
    // new Date("2026-01-01") = tengah malam UTC; di zona negatif jadi 31 Des.
    const d = formatDate("2026-01-01");
    expect(d).toBe("1 Jan 2026");
  });

  it("kosong -> '-', nilai tak valid dikembalikan apa adanya", () => {
    expect(formatDate(null)).toBe("-");
    expect(formatDate(undefined)).toBe("-");
    expect(formatDate("")).toBe("-");
    expect(formatDate("bukan-tanggal")).toBe("bukan-tanggal");
  });

  it("formatDateTime menyertakan jam", () => {
    const out = formatDateTime(new Date(2026, 9, 9, 14, 5));
    expect(out).toContain("9 Okt 2026");
    expect(out).toMatch(/14[.:]05/);
  });
});

describe("formatRupiah", () => {
  it("titik ribuan, tanpa desimal", () => {
    expect(formatRupiah(4357602000).replace(/\s/g, " ")).toBe("Rp 4.357.602.000");
  });
  it("null/undefined -> '-'", () => {
    expect(formatRupiah(null)).toBe("-");
    expect(formatRupiah(undefined)).toBe("-");
  });
});

describe("safeNextPath (open redirect setelah login)", () => {
  it("menerima path internal beserta query", () => {
    expect(safeNextPath("/payroll?tab=x")).toBe("/payroll?tab=x");
  });
  it.each(["//evil.com", "https://evil.com", "payroll", "/login", "/login?next=/x", null, ""])(
    "menolak %s",
    (value) => {
      expect(safeNextPath(value as string | null)).toBeNull();
    }
  );
});

describe("parseRupiahInput", () => {
  it.each([
    ["Rp 1.500.000", 1500000],
    ["1.500.000,50", 1500001], // dibulatkan ke rupiah
    ["1.500.000,49", 1500000],
    ["1,500,000.00", 1500000],
    ["1500000", 1500000],
    ["1.500", 1500],
    ["2500,5", 2501],
    ["", 0],
    ["  ", 0],
  ])("%s -> %d", (raw, expected) => {
    expect(parseRupiahInput(raw)).toBe(expected);
  });

  it.each(["abc", "1.50.000", "1,5,0", "-500", "1.500.000,505", "12.34.56"])("menolak %s", (raw) => {
    expect(parseRupiahInput(raw)).toBeNull();
  });
});
