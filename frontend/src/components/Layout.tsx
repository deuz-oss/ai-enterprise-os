import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, clearToken, getToken } from "../api/client";
import AppLauncherGrid from "./AppLauncherGrid";
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

/// B3: hex aksen per app → pasangan [accent, tint] untuk token --accent shell
/// (sumber: mockup `.shell[data-app=...]`).
const APP_ACCENT_TOKENS: Record<string, [string, string]> = {
  sales_crm: ["#2383e2", "rgba(35,131,226,.13)"],
  recruitment: ["#9065b0", "rgba(144,101,176,.14)"],
  hr_payroll: ["#0f7b6c", "rgba(15,123,109,.13)"],
  operations_billing: ["#d9730d", "rgba(217,115,13,.13)"],
  finance_accounting: ["#cb912f", "rgba(203,145,47,.16)"],
};

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/leads", label: "Pipeline", app: "sales_crm" },
  { to: "/clients", label: "Klien", app: "sales_crm" },
  { to: "/job-orders", label: "Job Orders", app: "recruitment" },
  { to: "/candidates", label: "Kandidat", app: "recruitment" },
  { to: "/talent-pool", label: "Talent Pool", app: "recruitment", roles: ["admin", "recruiter", "operations", "hr", "management"] },
  { to: "/employees", label: "Karyawan", app: "hr_payroll" },
  { to: "/attendance", label: "Absensi", apps: ["hr_payroll", "operations_billing"] },
  { to: "/chat", label: "Chat" },
  { to: "/payment-requests", label: "Payment Request", apps: ["hr_payroll", "operations_billing"], roles: ["admin", "operations", "hr", "finance", "management"] },
  { to: "/payroll", label: "Payroll", app: "hr_payroll" },
  { to: "/portal-saya", label: "Portal Saya", roles: ["karyawan"], app: "hr_payroll" },
  { to: "/finance", label: "Finance", app: "operations_billing" },
  { to: "/accounting", label: "Akunting", app: "finance_accounting" },
  // Kelola rate ber-versi — role finance ke atas.
  {
    to: "/rates",
    label: "Tarif & Rate",
    roles: ["admin", "finance", "management"],
    app: "finance_accounting",
  },
  // Jejak audit sensitif — disembunyikan dari role non-management.
  { to: "/audit", label: "Audit", roles: ["admin", "management"] },
];

const APP_ORDER: AppKey[] = [  "sales_crm",
  "recruitment",
  "hr_payroll",
  "operations_billing",
  "finance_accounting",
];

interface AppEntitlement {
  key: string;
  name: string;
  emoji: string;
  description?: string;
  status?: string | null;
  licensed: boolean;
}

// Fase A1: rute database/board/tabel lebar — di luar daftar ini konten center 900px.
const WIDE_PREFIXES = [
  "/leads",
  "/clients",
  "/job-orders",
  "/candidates",
  "/talent-pool",
  "/employees",
  "/attendance",
  "/payroll",
  "/payment-requests",
  "/finance",
  "/accounting",
  "/rates",
  "/chat",
  "/platform",
];

// Emoji + judul halaman untuk topbar & command palette.
const PAGE_EMOJI: Record<string, string> = {  "/": "🏠",
  "/apps": "🚀",
  "/leads": "🎯",
  "/clients": "🎯",
  "/job-orders": "🧲",
  "/candidates": "🧲",
  "/talent-pool": "🧬",
  "/pages": "📄",
  "/employees": "💼",
  "/attendance": "📅",
  "/chat": "💬",
  "/payment-requests": "🧾",
  "/payroll": "💼",
  "/portal-saya": "🙋",
  "/finance": "🏗️",
  "/accounting": "📊",
  "/rates": "🧮",
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
  const qc = useQueryClient();
  const { dark, toggle } = useDarkMode();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [launcherOpen, setLauncherOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
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
  // Fase A3: badge Kotak Masuk dari notifikasi in-app sungguhan.
  const unread = useQuery({
    queryKey: ["notif-unread"],
    queryFn: () => api.get<{ count: number }>("/notifications/unread-count"),
    enabled: Boolean(getToken()),
    refetchInterval: 30_000,
  });
  const startTrialSidebar = useMutation({
    mutationFn: (key: string) => api.post(`/apps/${key}/trial`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apps"] }),
  });

  const [favState, setFavState] = useState<Record<string, boolean>>(() =>
    JSON.parse(localStorage.getItem("aeos_favs") ?? "{}")
  );
  const favs = favState;
  function toggleFav() {
    setFavState((prev) => {
      const next = { ...prev, [location.pathname]: !prev[location.pathname] };
      localStorage.setItem("aeos_favs", JSON.stringify(next));
      return next;
    });
  }
  function copyLink() {
    void navigator.clipboard?.writeText(window.location.href);
    setShareCopied(true);
    window.setTimeout(() => setShareCopied(false), 1600);
  }

  // Ctrl/Cmd+K membuka command palette dari mana saja.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
      if (e.key === "Escape") {
        setMoreOpen(false);
        setLauncherOpen(false);
      }
    }
    function onCloseLauncher() {
      setLauncherOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("aeos:close-launcher", onCloseLauncher);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("aeos:close-launcher", onCloseLauncher);
    };
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
  // B3: aksen aktif mengikuti aplikasi halaman berjalan (default biru global).
  const accentTokens =
    activeItem?.app && APP_ACCENT_TOKENS[activeItem.app]
      ? APP_ACCENT_TOKENS[activeItem.app]
      : (["#2383e2", "rgba(35,131,226,.13)"] as [string, string]);

  return (
    <div
      className="flex min-h-screen"
      style={
        {
          "--accent": accentTokens[0],
          "--accent-tint": accentTokens[1],
        } as React.CSSProperties
      }
    >
      {/* ===== Sidebar workspace ===== */}
      <aside
        className="flex w-64 shrink-0 flex-col"
        style={{ backgroundColor: "var(--n-sidebar)", borderRight: "1px solid var(--n-border)" }}
      >
        <div className="px-4 py-4">
          <button
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors hover:bg-[var(--n-hover)]"
            onClick={() => setLauncherOpen(true)}
            title="Klik: buka App Launcher"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[#D9730D] text-[11px] font-bold text-white">
              AO
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold" style={{ color: "var(--n-text)" }}>
                AEOS Workspace
              </span>
              <span className="block truncate text-xs" style={{ color: "var(--n-text-muted)" }}>
                Outsourcing Operations ▾
              </span>
            </span>
          </button>
        </div>

        {/* Fase A3: Pencarian & Kotak Masuk */}
        <div className="space-y-0.5 px-3 pb-1">
          <SidebarAction
            emoji="🔍"
            label="Pencarian"
            onClick={() => setPaletteOpen(true)}
          />
          <SidebarAction
            emoji="🔔"
            label="Kotak Masuk"
            badge={unread.data && unread.data.count > 0 ? unread.data.count : undefined}
            onClick={() => setInboxOpen((v) => !v)}
          />
          {inboxOpen && <InboxPanel onDone={() => void unread.refetch()} />}
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-4">
          {showAppsMenu() && (
            <SidebarLink to="/apps" emoji="🚀" label="Aplikasi" active={location.pathname === "/apps"} />
          )}
          <PageTreeSection pathname={location.pathname} visible={showAppsMenu()} />
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

        {/* Fase A4: kartu upsell app belum terpasang */}
        {showAppsMenu() && (() => {
          const unlicensed = (apps.data ?? []).filter(
            (a) => !a.licensed && a.status !== "kedaluwarsa"
          );
          const pick =
            unlicensed.find((a) => a.key === "esign") ??
            unlicensed.find((a) => a.key === "ai_addon") ??
            unlicensed[0];
          if (!pick) return null;
          return (
            <div
              className="mx-3 mb-3 rounded-lg p-3 text-xs"
              style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg-elevated)" }}
            >
              <b style={{ color: "var(--n-text)" }}>
                {pick.emoji} Aktifkan {pick.name}?
              </b>
              <p className="mt-1 leading-relaxed" style={{ color: "var(--n-text-muted)" }}>
                {(pick.description ?? "").slice(0, 90)}
                {(pick.description ?? "").length > 90 ? "…" : ""} Gratis 14 hari.
              </p>
              <button
                onClick={() => startTrialSidebar.mutate(pick.key)}
                disabled={startTrialSidebar.isPending}
                className="mt-2 w-full rounded py-1.5 text-[12px] font-semibold text-white disabled:opacity-50"
                style={{ backgroundColor: "var(--accent)" }}
              >
                Coba sekarang
              </button>
            </div>
          );
        })()}

        <div
          className="flex items-center gap-2 p-4 pt-0"
        >
          <span
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
            style={{ backgroundColor: "#D9730D" }}
          >
            {(me.data?.full_name ?? "?")
              .split(" ")
              .map((w) => w[0])
              .slice(0, 2)
              .join("")
              .toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium" style={{ color: "var(--n-text)" }}>
              {me.data?.full_name ?? "..."}
            </p>
            <p className="truncate text-[11px]" style={{ color: "var(--n-text-muted)" }}>
              Owner · {me.data?.role ?? ""}
            </p>
          </div>
          <button
            className="rounded px-1.5 py-1 text-xs transition-colors hover:bg-[var(--n-hover)]"
            onClick={toggle}
            title={dark ? "Mode terang" : "Mode gelap"}
          >
            {dark ? "☀️" : "🌙"}
          </button>
          <button
            className="text-xs hover:underline"
            onClick={() => {
              clearToken();
              navigate("/login");
            }}
          >
            Keluar
          </button>
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
          <div className="flex shrink-0 items-center gap-0.5">
            {/* Fase A2: chrome ala Notion — ☆ · 💬 · 🌙 · ••• · Bagikan */}
            <button
              onClick={toggleFav}
              className="flex h-7 items-center rounded px-2 text-[13px] transition-colors hover:bg-[var(--n-hover)]"
              style={{ color: favs[location.pathname] ? "#CB912F" : "var(--n-text-muted)" }}
              title={favs[location.pathname] ? "Hapus favorit" : "Favoritkan halaman"}
            >
              {favs[location.pathname] ? "★" : "☆"}
            </button>
            <NavLink
              to="/chat"
              className="flex h-7 items-center rounded px-2 text-[13px] transition-colors hover:bg-[var(--n-hover)]"
              style={{ color: location.pathname === "/chat" ? "#2383E2" : "var(--n-text-muted)" }}
              title="Chat workspace"
            >
              💬
            </NavLink>
            <button
              onClick={toggle}
              className="flex h-7 items-center rounded px-2 text-[13px] transition-colors hover:bg-[var(--n-hover)]"
              style={{ color: "var(--n-text-muted)" }}
              title="Mode gelap/terang"
            >
              {dark ? "☀️" : "🌙"}
            </button>
            <div className="relative">
              <button
                onClick={() => setMoreOpen((v) => !v)}
                className="flex h-7 items-center rounded px-2 text-[13px] transition-colors hover:bg-[var(--n-hover)]"
                style={{ color: "var(--n-text-muted)", letterSpacing: 1 }}
                title="Menu lainnya"
              >
                •••
              </button>
              {moreOpen && (
                <>
                  <button
                    className="fixed inset-0 z-20 cursor-default"
                    onClick={() => setMoreOpen(false)}
                    aria-label="tutup menu"
                  />
                  <div
                    className="absolute right-0 z-30 mt-1 w-52 rounded-lg py-1 text-sm shadow-lg"
                    style={{
                      backgroundColor: "var(--n-bg-elevated)",
                      border: "1px solid var(--n-border)",
                    }}
                  >
                    <MoreItem
                      label={`⭐ ${favs[location.pathname] ? "Hapus dari favorit" : "Favoritkan"}`}
                      onClick={() => {
                        toggleFav();
                        setMoreOpen(false);
                      }}
                    />
                    <MoreItem
                      label="🔗 Salin tautan halaman"
                      onClick={() => {
                        copyLink();
                        setMoreOpen(false);
                      }}
                    />
                    <MoreItem
                      label={dark ? "☀️ Mode terang" : "🌙 Mode gelap"}
                      onClick={() => {
                        toggle();
                        setMoreOpen(false);
                      }}
                    />
                  </div>
                </>
              )}
            </div>
            <button
              onClick={copyLink}
              className="ml-1.5 flex h-7 items-center rounded px-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
              style={{ backgroundColor: "var(--accent)" }}
              title="Salin tautan halaman ini"
            >
              {shareCopied ? "✓ Tersalin" : "Bagikan"}
            </button>
          </div>
        </header>

        {/* Fase A1: kolom konten center ≤900px; rute data lebar opt-out */}
        <div className="flex-1 overflow-y-auto">
          <div
            className={
              WIDE_PREFIXES.some((p) => location.pathname.startsWith(p))
                ? "w-full px-6 py-6"
                : "mx-auto w-full max-w-[900px] px-8 py-8"
            }
          >
            <Outlet />
          </div>
        </div>
      </main>

      {/* Fase A5: App Launcher modal dari workspace switcher */}
      {launcherOpen && (
        <div
          className="fixed inset-0 z-40 flex items-start justify-center bg-black/35 pt-[10vh]"
          onClick={() => setLauncherOpen(false)}
        >
          <div
            className="max-h-[80vh] w-[720px] max-w-[92vw] overflow-hidden rounded-xl shadow-2xl"
            style={{ backgroundColor: "var(--n-bg-elevated)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-baseline gap-2.5 px-5 pt-4">
              <h2 className="text-lg font-bold" style={{ color: "var(--n-text)" }}>
                Aplikasi
              </h2>
              <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                {(apps.data ?? []).filter((a) => a.licensed).length} terpasang · trial 14 hari per app
              </span>
              <button
                className="ml-auto rounded px-2 py-1 text-xs hover:bg-[var(--n-hover)]"
                onClick={() => setLauncherOpen(false)}
                style={{ color: "var(--n-text-muted)" }}
              >
                ✕ Esc
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-5 pt-3">
              <AppLauncherGrid compact />
            </div>
            <div
              className="flex items-center gap-2 border-t px-5 py-3 text-[12.5px]"
              style={{ borderColor: "var(--n-border)", color: "var(--n-text-muted)" }}
            >
              💡 Ambil <b style={{ color: "var(--n-text)" }}>Full Package</b> (semua aplikasi +
              AI) dan hemat hingga 35% dibeli satuan.
            </div>
          </div>
        </div>
      )}

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

/// Page tree ala Notion (Fase 7 polish): daftar halaman buatan user
/// dari /pages, ditautkan ke editor /pages/{id}.
function PageTreeSection({
  pathname,
  visible,
}: {
  pathname: string;
  visible: boolean;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pages = useQuery({
    queryKey: ["pages"],
    queryFn: () => api.get<{ id: string; parent_id: string | null; title: string; icon: string }[]>("/pages"),
    enabled: visible,
  });
  const createPage = useMutation({
    mutationFn: () => api.post<{ id: string }>("/pages", { title: "Tanpa judul" }),
    onSuccess: (created) => {
      void qc.invalidateQueries({ queryKey: ["pages"] });
      navigate(`/pages/${created.id}`);
    },
  });

  if (!visible) return null;
  const roots = (pages.data ?? []).filter((p) => !p.parent_id);
  return (
    <div>
      <div className="flex items-center justify-between px-2 pb-1 pt-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--n-text-muted)" }}>
          📄 Halaman
        </span>
        <button
          onClick={() => createPage.mutate()}
          disabled={createPage.isPending}
          title="Halaman baru"
          className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
        >
          +
        </button>
      </div>
      <div className="space-y-0.5">
        {roots.map((p) => (
          <div key={p.id}>
            <a
              href={`/pages/${p.id}`}
              onClick={(e) => {
                e.preventDefault();
                navigate(`/pages/${p.id}`);
              }}
              className="block truncate rounded px-2 py-1 text-sm transition-colors hover:bg-[var(--n-hover)]"
              style={{ color: pathname === `/pages/${p.id}` ? "var(--n-text)" : "var(--n-text-muted)" }}
            >
              {p.icon} {p.title}
            </a>
            {(pages.data ?? [])
              .filter((c) => c.parent_id === p.id)
              .map((c) => (
                <a
                  key={c.id}
                  href={`/pages/${c.id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(`/pages/${c.id}`);
                  }}
                  className="block truncate rounded pl-6 pr-2 py-1 text-xs transition-colors hover:bg-[var(--n-hover)]"
                  style={{ color: pathname === `/pages/${c.id}` ? "var(--n-text)" : "var(--n-text-muted)" }}
                >
                  {c.icon} {c.title}
                </a>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/// Item sidebar tanpa rute (Pencarian / Kotak Masuk) ala mockup.
function SidebarAction({
  emoji,
  label,
  badge,
  onClick,
}: {
  emoji: string;
  label: string;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors hover:bg-[var(--n-hover)]"
      style={{ color: "var(--n-text)" }}
    >
      <span>{emoji}</span>
      {label}
      {badge !== undefined && (
        <span
          className="ml-auto flex h-[17px] min-w-[17px] items-center justify-center rounded px-1 text-[10.5px] font-semibold"
          style={{ backgroundColor: "rgba(224,62,62,.14)", color: "#E03E3E" }}
        >
          {badge}
        </span>
      )}
    </button>
  );
}

/// Panel Kotak Masuk: 5 notifikasi terakhir + tandai dibaca.
function InboxPanel({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const items = useQuery({
    queryKey: ["notif-list"],
    queryFn: () =>
      api.get<
        { id: string; title: string; body: string | null; read_at: string | null }[]
      >("/notifications?unread_only=true"),
  });
  const readAll = useMutation({
    mutationFn: () => api.post("/notifications/read-all", {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notif-list"] });
      void qc.invalidateQueries({ queryKey: ["notif-unread"] });
      onDone();
    },
  });

  return (
    <div
      className="mx-3 mb-2 rounded-lg p-2.5 text-xs shadow-md"
      style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg-elevated)" }}
    >
      <div className="mb-1 flex items-center justify-between">
        <b style={{ color: "var(--n-text)" }}>Belum dibaca</b>
        <button
          onClick={() => readAll.mutate()}
          disabled={readAll.isPending || (items.data?.length ?? 0) === 0}
          className="text-indigo-600 hover:text-indigo-800 disabled:opacity-40"
        >
          Tandai semua dibaca
        </button>
      </div>
      {(items.data ?? []).slice(0, 5).map((n) => (
        <div key={n.id} className="border-t py-1.5 first:border-t-0" style={{ borderColor: "var(--n-border)" }}>
          <p className="font-medium" style={{ color: "var(--n-text)" }}>
            {n.title}
          </p>
          {n.body && (
            <p className="truncate" style={{ color: "var(--n-text-muted)" }}>
              {n.body}
            </p>
          )}
        </div>
      ))}
      {(items.data?.length ?? 0) === 0 && (
        <p style={{ color: "var(--n-text-muted)" }}>Tidak ada notifikasi belum dibaca. 🎉</p>
      )}
    </div>
  );
}

function MoreItem({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="block w-full px-3 py-1.5 text-left transition-colors hover:bg-[var(--n-hover)]"
      style={{ color: "var(--n-text)" }}
    >
      {label}
    </button>
  );
}
