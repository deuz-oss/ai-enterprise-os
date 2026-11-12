import { describe, expect, it } from "vitest";
import { describeSalaryChange, digitsToAmount, formatAmountInput } from "./salary";

describe("describeSalaryChange", () => {
  it("kenaikan wajar tidak ditandai besar", () => {
    expect(describeSalaryChange(6_600_000, 7_000_000)).toEqual({ summary: "naik 6,1%", large: false });
  });

  it("salah ketik 10x ditandai besar", () => {
    expect(describeSalaryChange(6_600_000, 66_000_000)).toEqual({ summary: "naik 900%", large: true });
  });

  it("penurunan besar ditandai (mis. kurang satu nol)", () => {
    expect(describeSalaryChange(6_600_000, 660_000)).toEqual({ summary: "turun 90%", large: true });
    expect(describeSalaryChange(6_000_000, 5_000_000).large).toBe(false);
  });

  it("gaji sebelumnya 0 -> gaji awal", () => {
    expect(describeSalaryChange(0, 5_000_000)).toEqual({ summary: "gaji awal", large: false });
  });
});

describe("input nominal", () => {
  it("membaca digit dan mengabaikan pemisah", () => {
    expect(digitsToAmount("6.600.000")).toBe(6_600_000);
    expect(digitsToAmount("Rp 6.600.000")).toBe(6_600_000);
  });

  it("kosong -> null, bukan 0", () => {
    expect(digitsToAmount("")).toBeNull();
    expect(digitsToAmount("abc")).toBeNull();
  });

  it("format ribuan Indonesia", () => {
    expect(formatAmountInput(6_600_000)).toBe("6.600.000");
    expect(formatAmountInput(null)).toBe("");
  });

  it("nilai desimal dibulatkan, tidak menjadi 10x saat dibaca ulang", () => {
    expect(formatAmountInput(3500.5)).toBe("3.501");
    expect(digitsToAmount(formatAmountInput(3500.5))).toBe(3501);
  });
});
