import { AlertTriangle, CheckCircle2, Info, type LucideIcon, XCircle } from "lucide-react";
import { ReactNode } from "react";
import { Link } from "react-router-dom";

/** Judul halaman ala mockup dashboard.html: ikon lucide beraksen + judul ringkas. */
export function PageHeader({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-1 flex items-center gap-3">
      <span
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: "var(--accent-tint)", color: "var(--accent)" }}
      >
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0">
        <h1 className="truncate text-2xl font-semibold leading-tight" style={{ color: "var(--text)" }}>
          {title}
        </h1>
        {subtitle && (
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
}

const CALLOUT_TONES: Record<string, string> = {
  info: "bg-blue-50 border-blue-200 text-blue-600 dark:bg-blue-500/10 dark:border-blue-500/30",
  success: "bg-emerald-50 border-emerald-200 text-emerald-600 dark:bg-emerald-500/10 dark:border-emerald-500/30",
  warning: "bg-amber-50 border-amber-200 text-amber-600 dark:bg-amber-500/10 dark:border-amber-500/30",
  danger: "bg-red-50 border-red-200 text-red-600 dark:bg-red-500/10 dark:border-red-500/30",
};

// Ikon default per tone — sama seperti mockup (mis. alert-triangle utk kotak
// "Expiry Alert" bertone warning di dashboard.html).
const CALLOUT_ICONS: Record<string, LucideIcon> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
};

/** Callout/alert box ala mockup: ikon lucide + latar lembut berwarna per tone. */
export function CalloutBlock({
  icon,
  tone = "info",
  children,
}: {
  icon?: LucideIcon;
  tone?: "info" | "success" | "warning" | "danger";
  children: ReactNode;
}) {
  const Icon = icon ?? CALLOUT_ICONS[tone];
  return (
    <div
      className={`flex items-start gap-3 rounded-lg border px-3.5 py-3 text-sm ${CALLOUT_TONES[tone]}`}
    >
      <Icon className="h-[18px] w-[18px] shrink-0" />
      <div className="flex-1" style={{ color: "var(--text)" }}>
        {children}
      </div>
    </div>
  );
}

/** Satu baris properti ringkas: ikon + label kecil, nilai di kanan. */
export function PropertyRow({
  icon: Icon,
  label,
  children,
}: {
  icon: LucideIcon;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-[34px] items-center gap-3 py-1.5">
      <Icon className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
      <span
        className="w-36 shrink-0 text-xs font-medium uppercase tracking-wide"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </span>
      <span className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5 text-sm" style={{ color: "var(--text)" }}>
        {children}
      </span>
    </div>
  );
}

/** Panel properti dengan pemisah tipis antar baris. */
export function PropertiesPanel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`divide-y ${className}`} style={{ borderColor: "var(--border)" }}>
      {children}
    </div>
  );
}

/** Badge ikon berwarna ala mockup talent-cloud.html/workforce-cloud.html (mis.
 * ikon "Klien Aktif" emerald, "Leads" violet, dst) — "accent" pakai token
 * tema (--accent/--accent-tint) yang sama dengan PageHeader supaya tetap
 * ganti warna otomatis kalau tenant override warna aksennya. */
export function IconBadge({
  icon: Icon,
  tone,
  shape = "square",
}: {
  icon: LucideIcon;
  tone: "accent" | "green" | "violet" | "orange";
  shape?: "square" | "circle";
}) {
  const shapeCls = shape === "circle" ? "rounded-full" : "rounded-lg";
  if (tone === "accent") {
    return (
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center ${shapeCls}`}
        style={{ backgroundColor: "var(--accent-tint)", color: "var(--accent)" }}
      >
        <Icon className="h-4 w-4" />
      </span>
    );
  }
  const toneCls =
    tone === "green"
      ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400"
      : tone === "violet"
        ? "bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400"
        : "bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400";
  return (
    <span className={`flex h-8 w-8 shrink-0 items-center justify-center ${shapeCls} ${toneCls}`}>
      <Icon className="h-4 w-4" />
    </span>
  );
}

/** Frame tipis ala baris "Job Orders Aktif"/"Klien Aktif"/dst di mockup —
 * dipakai bungkus tiap baris list supaya ada border, bukan teks polos. */
export function RowFrame({ children }: { children: ReactNode }) {
  return (
    <div
      className="rounded-lg border p-2.5 transition-colors hover:bg-[var(--hover)]"
      style={{ borderColor: "var(--border)" }}
    >
      {children}
    </div>
  );
}

/** Tombol "Lihat semua X →" full-width berbingkai, ala mockup — bukan
 * sekadar tautan teks. */
export function SeeAllLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="btn-secondary block w-full text-center text-xs">
      {children}
    </Link>
  );
}

/** Inisial 1-2 huruf dari nama asli — dipakai sebagai avatar bulat pengganti
 * foto (tidak ada fitur upload foto kandidat/karyawan di app ini, jadi
 * jangan pakai foto acak dari layanan pihak ketiga seperti di mockup). */
export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}
