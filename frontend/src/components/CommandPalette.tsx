import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

export interface PaletteItem {
  id: string;
  label: string;
  emoji?: string;
  group?: string;
  to?: string;
  action?: () => void;
}

/** Command palette ala Notion: Ctrl/Cmd+K, filter, panah, Enter. */
export default function CommandPalette({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: PaletteItem[];
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        i.label.toLowerCase().includes(q) ||
        (i.group ?? "").toLowerCase().includes(q)
    );
  }, [items, query]);

  useEffect(() => {
    if (active >= results.length) setActive(0);
  }, [results, active]);

  if (!open) return null;

  function choose(item: PaletteItem) {
    onClose();
    if (item.to) navigate(item.to);
    item.action?.();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh]"
      style={{ background: "rgba(15,15,15,0.45)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-md"
        style={{
          backgroundColor: "var(--n-bg-elevated)",
          boxShadow: "0 12px 40px rgba(15,15,15,0.25)",
          border: "1px solid var(--n-border)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && results[active]) {
              choose(results[active]);
            }
          }}
          placeholder="Cari halaman atau aplikasi..."
          className="w-full px-4 py-3 text-sm focus:outline-none"
          style={{
            backgroundColor: "transparent",
            color: "var(--n-text)",
            borderBottom: "1px solid var(--n-border)",
          }}
        />
        <ul className="max-h-[50vh] overflow-y-auto py-1">
          {results.map((item, i) => (
            <li key={item.id}>
              <button
                onClick={() => choose(item)}
                onMouseEnter={() => setActive(i)}
                className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm"
                style={{
                  backgroundColor:
                    i === active ? "var(--n-hover)" : "transparent",
                  color: "var(--n-text)",
                }}
              >
                <span className="w-5">{item.emoji ?? "•"}</span>
                <span className="flex-1 truncate">{item.label}</span>
                {item.group && (
                  <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                    {item.group}
                  </span>
                )}
              </button>
            </li>
          ))}
          {results.length === 0 && (
            <li className="px-4 py-6 text-center text-sm" style={{ color: "var(--n-text-muted)" }}>
              Tidak ada hasil.
            </li>
          )}
        </ul>
        <div
          className="flex items-center justify-between px-4 py-2 text-[11px]"
          style={{
            borderTop: "1px solid var(--n-border)",
            color: "var(--n-text-muted)",
          }}
        >
          <span>↑↓ navigasi · Enter buka · Esc tutup</span>
          <span>⌘K</span>
        </div>
      </div>
    </div>
  );
}
