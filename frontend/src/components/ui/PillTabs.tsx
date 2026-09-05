/**
 * Tab/Pill Filter Row — component-implementation-spec.md §1.5. Tab aktif
 * pill solid warna aksen teks putih, tab lain teks abu tanpa background.
 * Count SELALU dari data asli yang sudah di-fetch caller, bukan estimasi.
 */

export interface PillTab {
  key: string;
  label: string;
  count?: number;
}

interface PillTabsProps {
  tabs: PillTab[];
  value: string;
  onChange: (key: string) => void;
}

export function PillTabs({ tabs, value, onChange }: PillTabsProps) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={`cursor-pointer whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
              active ? "bg-[var(--accent)] text-white" : "text-[var(--text-muted)] hover:bg-[var(--hover)]"
            }`}
          >
            {t.label}
            {t.count !== undefined && <span className="ml-1 opacity-80">({t.count})</span>}
          </button>
        );
      })}
    </div>
  );
}
