/**
 * Ringkasan perubahan gaji untuk dialog konfirmasi (audit 2026-11-11 Top-20
 * #5): dulu Rp 6.600.000 bisa jadi Rp 66.000.000 dengan satu klik tanpa
 * tanda apa pun. `large` menandai perubahan yang patut dicurigai salah ketik
 * (naik >= 50% atau turun >= 30%) supaya dialognya memberi peringatan.
 */
export interface SalaryChange {
  /** "naik 6,1%", "turun 25%", atau "gaji awal" bila sebelumnya 0. */
  summary: string;
  large: boolean;
}

const LARGE_INCREASE = 0.5;
const LARGE_DECREASE = 0.3;

export function describeSalaryChange(previous: number, next: number): SalaryChange {
  if (previous <= 0) return { summary: "gaji awal", large: false };
  const ratio = (next - previous) / previous;
  const percent = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(
    Math.abs(ratio) * 100
  );
  return {
    summary: `${ratio >= 0 ? "naik" : "turun"} ${percent}%`,
    large: ratio >= LARGE_INCREASE || ratio <= -LARGE_DECREASE,
  };
}

/** Digit saja -> angka rupiah bulat; kosong -> null (bukan 0 diam-diam). */
export function digitsToAmount(raw: string): number | null {
  const digits = raw.replace(/\D/g, "");
  if (digits === "") return null;
  const value = Number(digits);
  return Number.isSafeInteger(value) ? value : null;
}

/** 6600000 -> "6.600.000" (tanpa "Rp", untuk isi kolom input). */
export function formatAmountInput(value: number | null): string {
  // Dibulatkan dulu: 3500.5 kalau diformat apa adanya menjadi "3.500,5", lalu
  // saat diketik ulang terbaca 35005 (koma ikut terbuang sebagai non-digit).
  return value === null ? "" : new Intl.NumberFormat("id-ID").format(Math.round(value));
}
