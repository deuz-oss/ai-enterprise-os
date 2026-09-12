import { type ReactNode } from "react";
import { ArrowDown, ArrowUp, type LucideIcon } from "lucide-react";
import { Badge } from "./Badge";

/**
 * KPI Card presisi — component-implementation-spec.md §1.3, ikon lingkaran +
 * delta indicator ditambah 2026-09-12 (pola dashboard baru, docs/design/
 * design.md §"Component Spec — Dashboard Pattern"). Badge kontekstual,
 * progress bar, dan delta HANYA dirender kalau prop-nya diisi oleh caller —
 * caller yang bertanggung jawab memastikan datanya asli (§0, JANGAN kirim
 * angka delta karangan kalau backend belum menyediakan perbandingan periode
 * sungguhan), komponen ini murni presentasi.
 */

type KpiTone = "neutral" | "info" | "success" | "warning" | "danger" | "accent";

// Sama persis pemetaan di Badge.tsx (p-gray/p-blue/dst dari index.css) --
// duplikasi kecil supaya ikon KPI & badge status tetap konsisten warnanya
// tanpa membuat Badge.tsx mengekspor detail internalnya.
const ICON_TONE_CLASS: Record<KpiTone, string> = {
  neutral: "p-gray",
  info: "p-blue",
  success: "p-green",
  warning: "p-yellow",
  danger: "p-red",
  accent: "p-violet",
};

interface KpiDelta {
  /** Persen vs periode sebelumnya. Positif = naik, negatif = turun. Arah panah
   * & warna murni dari tanda angka -- tidak ada asumsi "naik selalu baik"
   * (caller yang tahu konteksnya, mis. "Outstanding" naik itu buruk; kalau
   * makna itu perlu dibalik, balik tanda `value`-nya di pemanggil, bukan di sini). */
  value: number;
  /** Default "vs periode lalu" -- override kalau perlu lebih spesifik (mis. "vs bulan lalu"). */
  label?: string;
}

interface KpiCardProps {
  label: string;
  value: ReactNode;
  icon?: LucideIcon;
  iconTone?: KpiTone;
  context?: ReactNode;
  badge?: { label: string; tone: "neutral" | "info" | "success" | "warning" | "danger" };
  /** 0-100. Cuma render mini progress bar kalau KPI ini punya makna porsi dari total/kuota. */
  progressPct?: number;
  delta?: KpiDelta;
}

export function KpiCard({
  label,
  value,
  icon: Icon,
  iconTone = "neutral",
  context,
  badge,
  progressPct,
  delta,
}: KpiCardProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {label}
        </p>
        {Icon && (
          <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${ICON_TONE_CLASS[iconTone]}`}>
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
      <div className="mt-1.5 flex items-baseline gap-2">
        <p className="text-2xl font-semibold tabular-nums" style={{ color: "var(--text)" }}>
          {value}
        </p>
        {delta && (
          <span
            className={`flex items-center gap-0.5 text-xs font-semibold tabular-nums ${
              delta.value >= 0 ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300"
            }`}
          >
            {delta.value >= 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
            {Math.abs(delta.value)}%
          </span>
        )}
      </div>
      {(context || badge || delta) && (
        <div className="mt-1 flex items-center justify-between gap-2">
          {context && (
            <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
              {context}
            </p>
          )}
          {!context && delta && (
            <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
              {delta.label ?? "vs periode lalu"}
            </p>
          )}
          {badge && <Badge tone={badge.tone}>{badge.label}</Badge>}
        </div>
      )}
      {progressPct !== undefined && (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--hover)" }}>
          <div
            className="h-full rounded-full"
            style={{ width: `${Math.min(100, Math.max(0, progressPct))}%`, backgroundColor: "var(--accent)" }}
          />
        </div>
      )}
    </div>
  );
}
