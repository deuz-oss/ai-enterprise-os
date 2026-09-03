import { type ReactNode } from "react";

/** Komponen dasar #3 — reuse `.card` yang sudah ada di index.css. */

interface CardProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, subtitle, action, children, className = "" }: CardProps) {
  const hasHeader = title || subtitle || action;
  return (
    <div className={`card ${className}`}>
      {hasHeader && (
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            {title && <p className="text-sm font-medium">{title}</p>}
            {subtitle && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {subtitle}
              </p>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}
