import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

/**
 * DonutChart — docs/design/design.md §4a. Total di tengah cincin
 * (center-label, dirender manual lewat <div> absolute, BUKAN fitur
 * recharts -- recharts tidak punya center-label bawaan) + legend list di
 * samping (dot warna + label + persentase). Library: recharts (dipilih
 * via skill /pick-ui-library 2026-09-12 -- kategori "General charts",
 * bukan Liveline karena data di sini bukan streaming real-time).
 *
 * SENGAJA tidak pakai <Legend> bawaan recharts -- legend custom di sini
 * supaya bisa ikut var(--...) token tema (recharts <Legend> lebih susah
 * di-style penuh lewat CSS custom property untuk teks/warna per item).
 */

export interface DonutSlice {
  label: string;
  value: number;
  /** Hex/rgb warna dot+slice. Kalau tidak diisi, fallback ke urutan token --cat-*. */
  color?: string;
}

const FALLBACK_COLORS = [
  "var(--cat-crm)",
  "var(--cat-recruitment)",
  "var(--cat-workforce)",
  "var(--cat-finance)",
  "var(--cat-administration)",
];

interface DonutChartProps {
  data: DonutSlice[];
  /** Label kecil di bawah angka total tengah, mis. "Total Lead". */
  centerLabel?: string;
  /** Format tampilan angka total (mis. formatRupiah). Default: angka mentah. */
  formatTotal?: (total: number) => string;
  size?: number;
}

export function DonutChart({ data, centerLabel, formatTotal, size = 160 }: DonutChartProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  const coloredData = data.map((d, i) => ({ ...d, color: d.color ?? FALLBACK_COLORS[i % FALLBACK_COLORS.length] }));

  if (total === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
        Belum ada data.
      </p>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-6">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={coloredData}
              dataKey="value"
              nameKey="label"
              innerRadius="70%"
              outerRadius="100%"
              paddingAngle={coloredData.length > 1 ? 2 : 0}
              stroke="none"
              isAnimationActive={false}
            >
              {coloredData.map((d, i) => (
                <Cell key={i} fill={d.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Center-label -- recharts tidak render ini, murni overlay absolute. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-semibold tabular-nums" style={{ color: "var(--text)" }}>
            {formatTotal ? formatTotal(total) : total}
          </span>
          {centerLabel && (
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              {centerLabel}
            </span>
          )}
        </div>
      </div>

      <ul className="min-w-0 flex-1 space-y-1.5">
        {coloredData.map((d, i) => {
          const pct = Math.round((d.value / total) * 100);
          return (
            <li key={i} className="flex items-center gap-2 text-sm">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: d.color }} />
              <span className="min-w-0 flex-1 truncate" style={{ color: "var(--text)" }}>
                {d.label}
              </span>
              <span className="shrink-0 tabular-nums" style={{ color: "var(--text-muted)" }}>
                {d.value} · {pct}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
