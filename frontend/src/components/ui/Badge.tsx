import { type ReactNode } from "react";

/**
 * Komponen dasar #2 — reuse `.pill` + `.p-*` yang sudah ada di index.css
 * (dipakai puluhan tempat sebagai className manual sebelum ini — lihat
 * temuan audit design-system: 32/41 file bypass token). Tujuan komponen
 * ini: satu tempat pemetaan makna->warna, supaya "approved" SELALU hijau
 * di mana pun dipakai, bukan diputuskan ulang tiap developer per halaman.
 */

type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger" | "accent";

interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
}

// Pemetaan tone->kelas warna existing (.p-gray, .p-blue, dst di index.css).
// TIDAK memakai var(--accent) — warna badge status sengaja independen dari
// warna aksen brand, supaya ganti teal/coral/dll tidak mengubah arti warna
// status (hijau tetap "approved", bukan ikut jadi warna aksen baru).
const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: "p-gray",
  info: "p-blue",
  success: "p-green",
  warning: "p-yellow",
  danger: "p-red",
  accent: "p-violet",
};

export function Badge({ tone = "neutral", children }: BadgeProps) {
  return <span className={`pill ${TONE_CLASS[tone]}`}>{children}</span>;
}
