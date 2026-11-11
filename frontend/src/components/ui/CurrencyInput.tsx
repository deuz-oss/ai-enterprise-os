import type { InputHTMLAttributes } from "react";
import { digitsToAmount, formatAmountInput } from "../../lib/salary";

/**
 * Kolom nominal rupiah dengan pemisah ribuan saat diketik ("6.600.000").
 *
 * Audit 2026-11-11 (§9): nominal diketik di `<input type="number">` polos --
 * "6600000" dan "66000000" nyaris tak terbedakan, jadi salah satu nol mudah
 * lolos. Rupiah bulat saja (tanpa desimal). `value` null = kosong; pemanggil
 * yang memutuskan apakah kosong boleh.
 */
type Props = {
  value: number | null;
  onChange: (value: number | null) => void;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "inputMode">;

export function CurrencyInput({ value, onChange, className = "input", ...rest }: Props) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-xs" style={{ color: "var(--text-muted)" }} aria-hidden="true">
        Rp
      </span>
      <input
        {...rest}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        className={`${className} num`}
        value={formatAmountInput(value)}
        onChange={(e) => onChange(digitsToAmount(e.target.value))}
      />
    </span>
  );
}
