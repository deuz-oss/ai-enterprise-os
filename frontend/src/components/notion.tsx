import { ReactNode } from "react";

/** Judul halaman ala Notion: emoji 56px + H1 38px bold (parity B2, mockup L145–147). */
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
    <div className="mb-1">
      <h1
        className="flex items-center gap-3 text-[38px] font-bold leading-[1.15] tracking-[-0.02em]"
        style={{ color: "var(--n-text)" }}
      >
        <span className="text-[56px] leading-none">{emoji}</span>
        {title}
      </h1>
      {subtitle && (
        <p className="mt-1 text-[15px]" style={{ color: "var(--n-text-muted)" }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}

const CALLOUT_TONES: Record<string, { bg: string; border: string }> = {
  // B3: tone info mengikuti aksen aplikasi aktif via token --accent.
  info: { bg: "var(--accent-tint)", border: "color-mix(in srgb, var(--accent) 38%, transparent)" },
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

/** Satu baris properti ala Notion: ikon + label 168px, nilai di kanan (parity B2). */
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
    <div className="flex min-h-[30px] items-center gap-2 py-1">
      <span className="w-5 shrink-0 text-center text-sm">{icon}</span>
      <span
        className="w-[168px] shrink-0 text-[13.5px]"
        style={{ color: "var(--n-text-muted)" }}
      >
        {label}
      </span>
      <span className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5 text-[13.5px]">
        {children}
      </span>
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
