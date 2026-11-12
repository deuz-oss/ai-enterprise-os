import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";
import { digitsToAmount, formatAmountInput } from "../../lib/salary";

/**
 * Kolom nominal rupiah dengan pemisah ribuan saat diketik ("6.600.000").
 *
 * Audit 2026-11-11 (§9): nominal diketik di `<input type="number">` polos --
 * "6600000" dan "66000000" nyaris tak terbedakan, jadi salah satu nol mudah
 * lolos. Rupiah bulat saja (tanpa desimal).
 *
 * Dua cara pakai:
 * - Terkontrol: `value` + `onChange` (null = kosong; pemanggil memutuskan
 *   apakah kosong boleh).
 * - Di dalam form berbasis FormData: `name` (+ `defaultValue`). Angka polos
 *   dikirim lewat input tersembunyi bernama `name`, jadi
 *   `Number(form.get("amount"))` di pemanggil tetap bekerja tanpa diubah, dan
 *   `form.reset()` mengembalikannya ke `defaultValue`.
 *
 * `block`: pembungkus selebar wadah (sel grid). Tanpa itu lebar mengikuti
 * kelas pada input (mis. "input w-32").
 */
type Props = {
  value?: number | null;
  onChange?: (value: number | null) => void;
  defaultValue?: number | null;
  block?: boolean;
} & Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "defaultValue" | "onChange" | "type" | "inputMode"
>;

export function CurrencyInput({
  value,
  onChange,
  defaultValue = null,
  name,
  block = false,
  className = "input",
  ...rest
}: Props) {
  const controlled = value !== undefined;
  const [inner, setInner] = useState<number | null>(defaultValue);
  const amount = controlled ? value : inner;
  const hiddenRef = useRef<HTMLInputElement>(null);

  // `form.reset()` tidak menyentuh state React -- ikuti event reset form-nya.
  useEffect(() => {
    const form = hiddenRef.current?.form;
    if (controlled || !form) return;
    const onReset = () => setInner(defaultValue);
    form.addEventListener("reset", onReset);
    return () => form.removeEventListener("reset", onReset);
  }, [controlled, defaultValue]);

  return (
    <span className={`${block ? "flex w-full" : "inline-flex"} items-center gap-1.5`}>
      <span className="text-xs" style={{ color: "var(--text-muted)" }} aria-hidden="true">
        Rp
      </span>
      <input
        {...rest}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        className={`${className} num ${block ? "min-w-0 flex-1" : ""}`}
        value={formatAmountInput(amount)}
        onChange={(e) => {
          const next = digitsToAmount(e.target.value);
          if (!controlled) setInner(next);
          onChange?.(next);
        }}
      />
      {name && <input ref={hiddenRef} type="hidden" name={name} value={amount ?? ""} />}
    </span>
  );
}
