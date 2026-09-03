import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export interface PaletteItem {
  id: string;
  label: string;
  emoji?: string;
  group?: string;
  to?: string;
  action?: () => void;
}

interface EntityHit {
  id: string;
  label: string;
  emoji: string;
  group: string;
  to: string;
}

const QUICK_ACTIONS = (navigate: ReturnType<typeof useNavigate>): PaletteItem[] => [
  {
    id: "qa-new-page",
    label: "Buat halaman baru",
    emoji: "➕",
    group: "Aksi cepat",
    action: async () => {
      const created = await api.post<{ id: string }>("/pages", { title: "Tanpa judul" });
      navigate(`/pages/${created.id}`);
    },
  },
  { id: "qa-chat", label: "Buka Chat (Tanya @AEOS)", emoji: "💬", group: "Aksi cepat", to: "/chat" },
  { id: "qa-attendance", label: "Absensi hari ini", emoji: "📅", group: "Aksi cepat", to: "/attendance" },
  {
    id: "qa-pr",
    label: "Payment Request",
    emoji: "🧾",
    group: "Aksi cepat",
    to: "/payment-requests",
  },
  {
    id: "qa-talent",
    label: "Talent Pool",
    emoji: "🧬",
    group: "Aksi cepat",
    to: "/talent-pool",
  },
];

/** C1: pencarian entitas lintas app (debounce) → hit navigasi ke section. */
function useEntitySearch(query: string, enabled: boolean): EntityHit[] {
  const [hits, setHits] = useState<EntityHit[]>([]);

  useEffect(() => {
    const q = query.trim().toLowerCase();
    if (!enabled || q.length < 2) {
      setHits([]);
      return;
    }
    let alive = true;
    const timer = window.setTimeout(async () => {
      const [clients, candidates, jos, pages] = await Promise.all([
        api
          .get<{ id: string; name: string }[]>("/clients")
          .catch(() => []),
        api
          .get<{ id: string; full_name: string }[]>("/candidates")
          .catch(() => []),
        api
          .get<{ id: string; title: string }[]>("/recruitment/job-orders")
          .catch(() => []),
        api
          .get<{ id: string; title: string; icon: string }[]>("/pages")
          .catch(() => []),
      ]);
      if (!alive) return;
      const out: EntityHit[] = [];
      for (const c of clients) {
        if (c.name?.toLowerCase().includes(q))
          out.push({ id: `cl-${c.id}`, label: c.name, emoji: "🏢", group: "Klien", to: "/clients" });
      }
      for (const c of candidates) {
        if (c.full_name?.toLowerCase().includes(q))
          out.push({
            id: `cd-${c.id}`,
            label: c.full_name,
            emoji: "🧑‍💻",
            group: "Kandidat",
            to: "/candidates",
          });
      }
      for (const j of jos) {
        if (j.title?.toLowerCase().includes(q))
          out.push({ id: `jo-${j.id}`, label: j.title, emoji: "📋", group: "Job Order", to: "/job-orders" });
      }
      for (const p of pages) {
        if (p.title?.toLowerCase().includes(q))
          out.push({
            id: `pg-${p.id}`,
            label: p.title,
            emoji: p.icon || "📄",
            group: "Workspace",
            to: `/pages/${p.id}`,
          });
      }
      setHits(out.slice(0, 12));
    }, 250);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [query, enabled]);

  return hits;
}

/** Command palette: Ctrl/Cmd+K, filter, entitas, panah, Enter. */
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

  const entityHits = useEntitySearch(query, open);
  const quickActions = useMemo(() => QUICK_ACTIONS(navigate), [navigate]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const match = (i: PaletteItem) =>
      !q ||
      i.label.toLowerCase().includes(q) ||
      (i.group ?? "").toLowerCase().includes(q);
    return [
      ...quickActions.filter(match),
      ...items.filter(match),
      ...(q.length >= 2 ? entityHits : []),
    ];
  }, [items, query, quickActions, entityHits]);

  useEffect(() => {
    if (active >= results.length) setActive(0);
  }, [results, active]);

  if (!open) return null;

  function choose(item: PaletteItem) {
    onClose();
    if (item.to) navigate(item.to);
    const maybe = item.action?.() as unknown;
    if (maybe instanceof Promise) (maybe as Promise<void>).catch(() => undefined);
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
          backgroundColor: "var(--bg-elevated)",
          boxShadow: "0 12px 40px rgba(15,15,15,0.25)",
          border: "1px solid var(--border)",
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
          placeholder="Cari halaman, aplikasi, atau entitas (klien/kandidat/JO)..."
          className="w-full px-4 py-3 text-sm focus:outline-none"
          style={{
            backgroundColor: "transparent",
            color: "var(--text)",
            borderBottom: "1px solid var(--border)",
          }}
        />
        <ul className="max-h-[50vh] overflow-y-auto py-1">
          {results.map((item, i) => (
            <li key={item.id}>
              <button
                onClick={() => choose(item)}
                onMouseEnter={() => setActive(i)}
                className="flex w-full cursor-pointer items-center gap-2 px-4 py-2 text-left text-sm"
                style={{
                  backgroundColor:
                    i === active ? "var(--hover)" : "transparent",
                  color: "var(--text)",
                }}
              >
                <span className="w-5">{item.emoji ?? "•"}</span>
                <span className="flex-1 truncate">{item.label}</span>
                {item.group && (
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {item.group}
                  </span>
                )}
              </button>
            </li>
          ))}
          {results.length === 0 && (
            <li className="px-4 py-6 text-center text-sm" style={{ color: "var(--text-muted)" }}>
              Tidak ada hasil.
            </li>
          )}
        </ul>
        <div
          className="flex items-center justify-between px-4 py-2 text-[11px]"
          style={{
            borderTop: "1px solid var(--border)",
            color: "var(--text-muted)",
          }}
        >
          <span>↑↓ navigasi · Enter buka · Esc tutup</span>
          <span>⌘K</span>
        </div>
      </div>
    </div>
  );
}
