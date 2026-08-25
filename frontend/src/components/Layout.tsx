import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, clearToken, getToken } from "../api/client";
import CommandPalette, { type PaletteItem } from "./CommandPalette";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  roles?: string[];
  app?: AppKey;
  apps?: AppKey[];
}

type AppKey =
  | "sales_crm"
  | "recruitment"
  | "hr_payroll"
  | "operations_billing"
  | "finance_accounting";

const APP_META: Record<AppKey, { label: string; emoji: string; accent: string }> = {
  sales_crm: { label: "Sales CRM", emoji: "🎯", accent: "#2383e2" },
  recruitment: { label: "Recruitment", emoji: "🧲", accent: "#9065b0" },
  hr_payroll: { label: "HR & Payroll", emoji: "💼", accent: "#0f7b6c" },
  operations_billing: { label: "Operations & Billing", emoji: "🏗️", accent: "#d9730d" },
  finance_accounting: { label: "Finance & Accounting", emoji: "📊", accent: "#cb912f" },
};

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/leads", label: "Pipeline", app: "sales_crm" },
  { to: "/clients", label: "Klien", app: "sales_crm" },
  { to: "/job-orders", label: "Job Orders", app: "recruitment" },
  { to: "/candidates", label: "Kandidat", app: "recruitment" },
  { to: "/employees", label: "Karyawan", app: "hr_payroll" },
  { to: "/attendance", label: "Absensi", apps: ["hr_payroll", "operations_billing"] },
  { to: "/payroll", label: "Payroll", app: "hr_payroll" },
  { to: "/portal-saya", label: "Portal Saya", roles: ["karyawan"], app: "hr_payroll" },
  { to: "/finance", label: "Finance", app: "operations_billing" },
  { to: "/accounting", label: "Akunting", app: "finance_accounting" },
  // Jejak audit sensitif — disembunyikan dari role non-management.
  { to: "/audit", label: "Audit", roles: ["admin", "management"] },
];

const APP_ORDER: AppKey[] = [
  "sales_crm",
  "recruitment",
  "hr_payroll",
  "operations_billing",
  "finance_accounting",
];

interface AppEntitlement {
  key: string;
  name: string;
  emoji: string;
  licensed: boolean;
}

// Emoji + judul halaman untuk topbar & command palette.
const PAGE_EMOJI: Record<string, string> = {
  "/": "🏠",
  "/apps": "🚀",
  "/leads": "🎯",
  "/clients": "🎯",
  "/job-orders": "🧲",
  "/candidates": "🧲",
  "/employees": "💼",
  "/attendance": "📅",
  "/payroll": "💼",
  "/portal-saya": "🙋",
  "/finance": "🏗️",
  "/accounting": "📊",
  "/audit": "🛡️",
};

function useDarkMode() {
  const [dark, setDark] = useState<boolean>(
    () => localStorage.getItem("aeos_theme") === "dark"
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("aeos_theme", dark ? "dark" : "light");
  }, [dark]);
  return { dark, toggle: () => setDark((d) => !d) };
}

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { dark, toggle } = useDarkMode();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
    enabled: Boolean(getToken()),
    retry: false,
  });
  // Entitlement Fase 7: nav dinamis mengikuti lisensi aplikasi tenant.
  const apps = useQuery({
    queryKey: ["apps"],
    queryFn: () => api.get<AppEntitlement[]>("/apps"),
    enabled: Boolean(getToken()) && me.data?.role !== "platform_admin",
  });

  // Ctrl/Cmd+K membuka command palette dari mana saja.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (!getToken()) return <Navigate to="/login" replace />;

  const isPlatform = me.data?.role === "platform_admin";
  const isKaryawan = me.data?.role === "karyawan";
  // Platform admin tidak punya dashboard bisnis — langsung ke halaman tenant.
  if (isPlatform && location.pathname === "/") {
    return <Navigate to="/platform" replace />;
  }
  // Karyawan hanya butuh portal self-service — tanpa dashboard internal.
  if (isKaryawan && location.pathname === "/") {
    return <Navigate to="/portal-saya" replace />;
  }

  const licensedSet = new Set(
    (apps.data ?? []).filter((a) => a.licensed).map((a) => a.key)
  );

  function licensedFor(item: NavItem): boolean {
    const keys: AppKey[] = item.apps ?? (item.app ? [item.app] : []);
    if (!keys.length) return true;
    return keys.some((k) => licensedSet.has(k));
  }

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.roles && !(me.data && item.roles.includes(me.data.role))) return false;
    // Selama entitlement belum termuat, tampilkan dulu (hindari kedipan).
    if (!item.apps && !item.app) return true;
    if (!apps.data) return true;
    return licensedFor(item);
  });

  // Grup ala Notion: Umum → satu grup per aplikasi berlisensi → Lainnya.
  const groups: { label: string; emoji?: string; accent?: string; items: NavItem[] }[] = [];
  const umum = visibleItems.filter((i) => !i.app && !i.apps && i.to !== "/audit");
  if (umum.length) groups.push({ label: "Umum", emoji: "🗂️", items: umum });
  for (const key of APP_ORDER) {
    // Item milik App ini jika app/apps mengandung key tersebut.
    const inApp = visibleItems.filter(
      (i) => i.app === key || (i.apps && i.apps.includes(key))
    );
    if (!inApp.length || !licensedSet.has(key)) continue;
    // Hindari duplikasi: attendance masuk di dua app → tetapkan ke HR & Payroll.
    const unique = inApp.filter((i) => {
      if (!i.apps || i.apps.length === 1) return true;
      return key === "hr_payroll";
    });
    if (!unique.length) continue;
    groups.push({
      label: APP_META[key].label,
      emoji: APP_META[key].emoji,
      accent: APP_META[key].accent,
      items: unique,
    });
  }
  const lainnya = visibleItems.filter((i) => i.to === "/audit");
  if (lainnya.length) groups.push({ label: "Lainnya", items: lainnya });

  const paletteItems: PaletteItem[] = [
    ...groups.flatMap((g) =>
      g.items.map((i) => ({
        id: i.to,
        label: i.label,
        emoji: PAGE_EMOJI[i.to] ?? g.emoji,
        group: g.label,
        to: i.to,
      }))
    ),
    ...(showAppsMenu()
      ? [{ id: "/apps", label: "Aplikasi", emoji: "🚀", group: "Platform", to: "/apps" }]
      : []),
    {
      id: "theme",
      label: dark ? "Mode Terang" : "Mode Gelap",
      emoji: dark ? "☀️" : "🌙",
      group: "Preferensi",
      action: toggle,
    },
  ];

  function showAppsMenu(): boolean {
    return Boolean(getToken()) && !isPlatform && !isKaryawan;
  }

  // Judul halaman aktif untuk topbar.
  const activeItem =
    [...visibleItems]
      .sort((a, b) => b.to.length - a.to.length)
      .find(
        (i) =>
          location.pathname === i.to ||
          (i.to !== "/" && location.pathname.startsWith(i.to))
      ) ?? null;
  const pageTitle = showAppsMenu() && location.pathname === "/apps"
    ? "Aplikasi"
    : activeItem?.label ?? "";
  const pageEmoji =
    PAGE_EMOJI[location.pathname] ??
    (activeItem?.app ? APP_META[activeItem.app].emoji : "📄");
  const crumbApp =
    activeItem?.app != null
      ? APP_META[activeItem.app].label
      : activeItem?.apps?.[0] != null
        ? APP_META[activeItem.apps[0]].label
        : null;

  return (
    <div className="flex min-h-screen">
      {/* ===== Sidebar workspace ===== */}
      <aside
        className="flex w-64 shrink-0 flex-col"
        style={{ backgroundColor: "var(--n-sidebar)", borderRight: "1px solid var(--n-border)" }}
      >
        <div className="px-4 py-4">
          <button
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors hover:bg-[var(--n-hover)]"
            onClick={() => navigate("/")}
          >
            <span className="text-xl">🏢</span>
            <span>
              <span className="block text-sm font-semibold" style={{ color: "var(--n-text)" }}>
                AEOS Workspace
              </span>
              <span className="block text-xs" style={{ color: "var(--n-text-muted)" }}>
                Outsourcing Operations
              </span>
            </span>
          </button>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-4">
          {showAppsMenu() && (
            <SidebarLink to="/apps" emoji="🚀" label="Aplikasi" active={location.pathname === "/apps"} />
          )}
          {groups.map((g) => (
            <div key={g.label}>
              <p className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--n-text-muted)" }}>
                {g.emoji ? `${g.emoji} ` : ""}{g.label}
              </p>
              <div className="space-y-0.5">
                {g.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `flex items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors ${
                        isActive ? "font-medium" : ""
                      }`
                    }
                    style={({ isActive }) => ({
                      color: isActive ? "var(--n-text)" : "var(--n-text-muted)",
                      backgroundColor: isActive ? "var(--n-hover)" : undefined,
                      boxShadow: isActive && g.accent ? `inset 3px 0 0 ${g.accent}` : undefined,
                    })}
                  >
                    <span>{PAGE_EMOJI[item.to] ?? "•"}</span>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div
          className="p-4 text-sm"
          style={{ borderTop: "1px solid var(--n-border)", color: "var(--n-text-muted)" }}
        >
          <p className="truncate" style={{ color: "var(--n-text)" }}>
            {me.data?.full_name ?? "..."}
          </p>
          <div className="mt-2 flex items-center justify-between">
            <button
              className="text-xs hover:underline"
              onClick={() => {
                clearToken();
                navigate("/login");
              }}
            >
              Keluar
            </button>
            <button
              className="rounded px-1.5 py-1 text-xs transition-colors hover:bg-[var(--n-hover)]"
              onClick={toggle}
              title={dark ? "Mode terang" : "Mode gelap"}
            >
              {dark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>
      </aside>

      {/* ===== Konten ===== */}
      <main className="flex min-h-screen flex-1 flex-col overflow-x-auto">
        {/* Topbar breadcrumb */}
        <header
          className="sticky top-0 z-10 flex h-12 items-center justify-between gap-3 px-6"
          style={{ backgroundColor: "var(--n-bg)", borderBottom: "1px solid var(--n-border)" }}
        >
          <div className="flex min-w-0 items-center gap-1.5 text-sm" style={{ color: "var(--n-text-muted)" }}>
            <span>🏢 AEOS</span>
            {crumbApp && (
              <>
                <span>/</span>
                <span className="truncate">{crumbApp}</span>
              </>
            )}
            {pageTitle && (
              <>
                <span>/</span>
                <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>
                  {pageEmoji} {pageTitle}
                </span>
              </>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              onClick={() => setPaletteOpen(true)}
              className="flex items-center gap-2 rounded px-2.5 py-1 text-xs transition-colors hover:bg-[var(--n-hover)]"
              style={{
                border: "1px solid var(--n-border)",
                color: "var(--n-text-muted)",
              }}
              title="Command palette"
            >
              Cari... <kbd className="font-mono">⌘K</kbd>
            </button>
          </div>
        </header>

        <div className="flex-1 p-8">
          <Outlet />
        </div>
      </main>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={paletteItems} />
    </div>
  );
}

function SidebarLink({
  to,
  emoji,
  label,
  active,
}: {
  to: string;
  emoji: string;
  label: string;
  active: boolean;
}) {
  return (
    <NavLink
      to={to}
      end
      className="mb-2 flex items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors"
      style={{
        backgroundColor: active ? "var(--n-hover)" : undefined,
        color: "var(--n-text)",
      }}
    >
      <span>{emoji}</span>
      {label}
    </NavLink>
  );
}
