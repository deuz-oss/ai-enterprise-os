import { ReactNode } from "react";

/** Judul halaman ala Notion: emoji besar + judul tebal. */
export function PageHeader({
  emoji,
  title,
  subtitle,
}: {
  emoji: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div>
      <h1 className="flex items-center gap-3 text-2xl font-bold text-notion">
        <span className="text-4xl leading-none">{emoji}</span>
        {title}
      </h1>
      {subtitle && <p className="mt-1 text-sm" style={{ color: "var(--n-text-muted)" }}>{subtitle}</p>}
    </div>
  );
}

const CALLOUT_TONES: Record<string, { bg: string; border: string }> = {
  info: { bg: "rgba(35,131,226,0.10)", border: "rgba(35,131,226,0.35)" },
  success: { bg: "rgba(15,123,108,0.10)", border: "rgba(15,123,108,0.35)" },
  warning: { bg: "rgba(217,115,13,0.12)", border: "rgba(217,115,13,0.40)" },
  danger: { bg: "rgba(224,62,62,0.10)", border: "rgba(224,62,62,0.38)" },
};

/** Callout block ala Notion: ikon + latar berwarna lembut untuk penekanan. */
export function CalloutBlock({
  emoji = "💡",
  tone = "info",
  children,
}: {
  emoji?: string;
  tone?: "info" | "success" | "warning" | "danger";
  children: ReactNode;
}) {
  const t = CALLOUT_TONES[tone];
  return (
    <div
      className="flex items-start gap-3 rounded-md px-4 py-3 text-sm"
      style={{ backgroundColor: t.bg, border: `1px solid ${t.border}`, color: "var(--n-text)" }}
    >
      <span className="text-lg leading-none">{emoji}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}

/** Satu baris properti ala Notion: ikon + label di kiri, nilai di kanan. */
export function PropertyRow({
  icon,
  label,
  children,
}: {
  icon: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 py-1.5">
      <span className="w-5 shrink-0 text-center text-sm">{icon}</span>
      <span className="w-36 shrink-0 pt-0.5 text-xs uppercase tracking-wide" style={{ color: "var(--n-text-muted)" }}>
        {label}
      </span>
      <span className="min-w-0 flex-1 pt-0.5 text-sm">{children}</span>
    </div>
  );
}

/** Panel properti ala Notion dengan pemisah titik-titik halus. */
export function PropertiesPanel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`divide-y divide-dashed ${className}`} style={{ borderColor: "var(--n-border)" }}>
      {children}
    </div>
  );
}
