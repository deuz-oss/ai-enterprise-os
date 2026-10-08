export interface Period {
  year: number;
  month: number;
}

const MONTHS = [
  "Januari",
  "Februari",
  "Maret",
  "April",
  "Mei",
  "Juni",
  "Juli",
  "Agustus",
  "September",
  "Oktober",
  "November",
  "Desember",
];

/** Bulan berjalan -- default periode, jangan hardcode tahun/bulan. */
export function currentPeriod(): Period {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

/**
 * Pemilih periode bulanan: bulan sebagai <select> bernama (bukan input angka
 * yang menerima 0/13) + tahun. Audit 2026-10-08 §9: dulu lima tempat memakai
 * dua `type="number"` mentah.
 */
export function PeriodPicker({
  value,
  onChange,
  label,
}: {
  value: Period;
  onChange: (next: Period) => void;
  /** Konteks untuk screen reader, mis. "periode payroll". */
  label: string;
}) {
  return (
    <div role="group" aria-label={`Pilih ${label}`} className="flex items-center gap-2">
      <select
        className="input w-auto"
        value={value.month}
        onChange={(e) => onChange({ ...value, month: Number(e.target.value) })}
        aria-label={`Bulan ${label}`}
      >
        {MONTHS.map((name, i) => (
          <option key={name} value={i + 1}>
            {name}
          </option>
        ))}
      </select>
      <input
        type="number"
        className="input w-24"
        min={2000}
        max={2100}
        value={value.year}
        onChange={(e) => {
          const year = Number(e.target.value);
          if (Number.isInteger(year) && year > 0) onChange({ ...value, year });
        }}
        aria-label={`Tahun ${label}`}
      />
    </div>
  );
}
