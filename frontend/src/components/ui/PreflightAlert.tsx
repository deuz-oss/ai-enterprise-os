import { AlertTriangle, X } from "lucide-react";

/**
 * Pre-flight / Compliance Alert Box — component-implementation-spec.md §1.4.
 * Warna dipatok persis dari spec (bukan lewat var(--...)), jadi SENGAJA sama
 * di light & dark mode -- ini kotak peringatan compliance, bukan elemen tema.
 */

interface PreflightAlertProps {
  title: string;
  summary: string;
  actionLabel?: string;
  onAction?: () => void;
  onDismiss?: () => void;
}

export function PreflightAlert({ title, summary, actionLabel, onAction, onDismiss }: PreflightAlertProps) {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border px-4 py-3 text-sm"
      style={{ backgroundColor: "#FFFBEB", borderColor: "#FDE68A", color: "#92400E" }}
    >
      <AlertTriangle className="mt-0.5 h-[18px] w-[18px] shrink-0" />
      <div className="min-w-0 flex-1">
        <span className="font-bold">{title}:</span> {summary}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {actionLabel && onAction && (
          <button
            onClick={onAction}
            className="cursor-pointer rounded-md border px-3 py-1 text-xs font-medium"
            style={{ borderColor: "#FDE68A", backgroundColor: "#ffffff", color: "#92400E" }}
          >
            {actionLabel}
          </button>
        )}
        {onDismiss && (
          <button onClick={onDismiss} className="cursor-pointer rounded p-0.5 hover:opacity-70" style={{ color: "#92400E" }}>
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
