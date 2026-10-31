import { Ban } from "lucide-react";
import type { UserRole } from "../../api/auth";
import { Badge } from "./Badge";

/**
 * Penanda kandidat yang masuk daftar Blacklist berstatus "disetujui" (Fase 29:
 * blacklist jadi blocking check). Sengaja TIDAK menampilkan alasan blacklist —
 * alasan cuma boleh dilihat di halaman Blacklist sendiri.
 *
 * Tidak mengandalkan warna saja: teks "Blacklist" + ikon selalu terlihat, dan
 * penjelasan lengkap dibacakan screen reader lewat teks `sr-only` (atribut
 * `aria-label` pada <span> generik tidak diandalkan pembaca layar).
 */
export const BLACKLIST_BADGE_DESCRIPTION = "Kandidat masuk daftar Blacklist (disetujui)";

interface BlacklistBadgeProps {
  /** "sm" untuk kartu padat (Kanban, daftar lookup). */
  size?: "sm" | "md";
}

export function BlacklistBadge({ size = "md" }: BlacklistBadgeProps) {
  return (
    <Badge
      tone="danger"
      title={BLACKLIST_BADGE_DESCRIPTION}
      className={`gap-1 ${size === "sm" ? "text-[10px]" : ""}`}
    >
      <Ban className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} aria-hidden="true" />
      Blacklist
      <span className="sr-only">: {BLACKLIST_BADGE_DESCRIPTION}</span>
    </Badge>
  );
}

/**
 * Role yang boleh meminta `include_blacklisted=true` (selain itu backend 403).
 * `admin` ikut karena `require_roles` backend selalu meloloskan admin.
 */
const BLACKLIST_VIEWER_ROLES: readonly UserRole[] = ["admin", "recruiter", "management"];

export function canIncludeBlacklisted(role: UserRole | undefined | null): boolean {
  return role != null && BLACKLIST_VIEWER_ROLES.includes(role);
}

interface BlacklistToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/** Toggle "Tampilkan kandidat blacklist" — secara default kandidat
 * ter-blacklist tidak ikut hasil matching/talent pool. Render hanya untuk
 * role yang lolos `canIncludeBlacklisted`. */
export function BlacklistToggle({ checked, onChange }: BlacklistToggleProps) {
  return (
    <label
      className="inline-flex cursor-pointer items-center gap-1.5 text-xs"
      style={{ color: "var(--text-muted)" }}
      title="Secara default kandidat yang masuk daftar Blacklist (disetujui) disembunyikan"
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      Tampilkan kandidat blacklist
    </label>
  );
}
