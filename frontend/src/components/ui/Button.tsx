import { type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2 } from "lucide-react";

/**
 * Komponen dasar #1 dari component library (rencana audit design-system,
 * 2026-09-03) — reuse class `.btn`/`.btn-secondary` yang sudah ada di
 * index.css, TIDAK hardcode warna di sini. Ganti token `--accent` di
 * index.css otomatis mengubah semua Button di seluruh app, tanpa sentuh
 * file ini.
 */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "btn",
  secondary: "btn-secondary",
  // Ghost & danger belum ada tokennya di index.css — didefinisikan inline
  // di sini untuk sementara, TAPI tetap lewat var(--...) supaya ikut
  // berubah kalau token akhirnya ditambahkan resmi ke index.css.
  ghost: "btn-ghost",
  danger: "btn-danger",
};

const SIZE_CLASS: Record<ButtonSize, string> = {
  sm: "text-xs px-2.5 py-1.5",
  md: "text-sm px-4 py-2",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  disabled,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      className={`${VARIANT_CLASS[variant]} inline-flex items-center justify-center gap-1.5 ${SIZE_CLASS[size]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      {children}
    </button>
  );
}
