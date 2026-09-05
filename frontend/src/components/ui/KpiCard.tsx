import { type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "./Badge";

/**
 * KPI Card presisi — component-implementation-spec.md §1.3. Badge kontekstual
 * dan progress bar HANYA dirender kalau prop-nya diisi oleh caller — caller
 * yang bertanggung jawab memastikan datanya asli (§0), komponen ini murni
 * presentasi.
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

interface KpiCardProps {
  label: string;
  value: ReactNode;
  icon?: LucideIcon;
  iconTone?: KpiTone;
  context?: ReactNode;
  badge?: { label: string; tone: "neutral" | "info" | "success" | "warning" | "danger" };
  /** 0-100. Cuma render mini progress bar kalau KPI ini punya makna porsi dari total/kuota. */
  progressPct?: number;
}

export function KpiCard({ label, value, icon: Icon, iconTone = "neutral", context, badge, progressPct }: KpiCardProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {label}
        </p>
        {Icon && (
          <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md ${ICON_TONE_CLASS[iconTone]}`}>
            <Icon className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums" style={{ color: "var(--text)" }}>
        {value}
      </p>
      {(context || badge) && (
        <div className="mt-1 flex items-center justify-between gap-2">
          {context && (
            <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
              {context}
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
