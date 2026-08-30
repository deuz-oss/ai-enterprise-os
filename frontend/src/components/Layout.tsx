import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Bell,
  Briefcase,
  Building2,
  Calculator,
  Calendar,
  ChevronDown,
  ChevronsUpDown,
  ClipboardList,
  Dna,
  FileText,
  IdCard,
  LayoutDashboard,
  Lightbulb,
  type LucideIcon,
  Magnet,
  MessageCircle,
  Moon,
  MoreHorizontal,
  PartyPopper,
  Plus,
  Receipt,
  Rocket,
  Scale,
  Search,
  Shield,
  Sparkles,
  Sun,
  UserCircle,
  UserCog,
  Users,
  Wallet,
  X,
} from "lucide-react";
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
  bundle?: Bundle;
  // Item ini adalah landing page bundle-nya (mis. /talent-cloud) — kalau
  // sebuah grup bundle punya item dengan flag ini, sidebar HANYA menampilkan
  // satu baris tunggal (nama bundle, ikon landing) alih-alih tree flat semua
  // item. Item lain di bundle itu tetap ada (tetap kena cek lisensi & tetap
  // muncul di ⌘K), cuma disembunyikan dari daftar sidebar — navigasi ke sana
  // dilakukan lewat link "Lihat semua X →" di dalam landing page itu sendiri
  // (ala docs/design/mockups/talent-cloud.html).
  bundleLanding?: boolean;
}

// Kelompok sidebar ala 4 "Metered SKU Bundles" di dashboard.html (Talent/
// Workforce/Revenue/Govern Cloud) — murni pengelompokan TAMPILAN, terpisah
// dari `app`/`apps` di atas (yang menentukan status lisensi per item).
// Beberapa modul lisensi asli sengaja disatukan ke satu bundel tampilan
// (mis. Sales CRM + Recruitment → Talent Cloud) supaya sidebar seringkas
// mockup — 4 grup bundel, bukan satu grup per app.
type Bundle = "talent" | "workforce" | "revenue" | "govern";

const BUNDLE_META: Record<Bundle, { label: string; accent: string }> = {
  talent: { label: "Talent Cloud", accent: "#7c3aed" },
  workforce: { label: "Workforce Cloud", accent: "#059669" },
  revenue: { label: "Revenue Cloud", accent: "#d97706" },
  govern: { label: "Govern Cloud", accent: "#475569" },
};

const BUNDLE_ORDER: Bundle[] = ["talent", "workforce", "revenue", "govern"];

// Regresi ditemukan saat redesign: key di sini sebelumnya ("hr_payroll",
// "operations_billing", "finance_accounting") TIDAK PERNAH cocok dengan key
// lisensi asli di backend (`APP_REGISTRY` — app/core/apps.py:
// sales_crm/recruitment/people_ops/payroll/finance/accounting/ai_addon).
// Akibatnya `licensedSet.has(key)` selalu false utk 3 grup itu → nav
// Karyawan/Absensi/Payment Request/Payroll/Finance/Akunting/Tarif TIDAK
// PERNAH tampil di sidebar (juga hilang dari hasil ⌘K) untuk siapa pun,
// admin maupun karyawan — bukan cuma soal desain.
type AppKey =
  | "sales_crm"
  | "recruitment"
  | "people_ops"
  | "payroll"
  | "finance"
  | "accounting";

// `roles` di bawah cuma menyembunyikan menu (allowlist ketat, admin TIDAK
// otomatis lolos di sini) — keamanan sesungguhnya ditegakkan backend lewat
// `require_roles(...)` per route. Sumber kebenaran role per area ada di
// `backend/app/core/permissions.py`; kalau ubah salah satu, cek yang lain
// biar sidebar tidak menyesatkan (menampilkan/menyembunyikan menu yang
// sebenarnya beda dgn apa yang backend izinkan).
const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  // Ringkasan gabungan Sales CRM + Recruitment (mockup talent-cloud.html) — item
  // paling atas grup bundle "talent", label "Ringkasan" (bukan "Talent Cloud")
  // supaya tidak bentrok nama dengan header grup bundle di bawahnya.
  {
    to: "/talent-cloud",
    label: "Ringkasan",
    apps: ["sales_crm", "recruitment"],
    bundle: "talent",
    end: true,
    bundleLanding: true,
  },
  { to: "/leads", label: "Pipeline", app: "sales_crm", bundle: "talent" },
  { to: "/clients", label: "Klien", app: "sales_crm", bundle: "talent" },
  { to: "/job-orders", label: "Job Orders", app: "recruitment", bundle: "talent" },
  { to: "/candidates", label: "Kandidat", app: "recruitment", bundle: "talent" },
  {
    to: "/talent-pool",
    label: "Talent Pool",
    app: "recruitment",
    bundle: "talent",
    roles: ["admin", "recruiter", "operations", "hr", "management"],
  },
  {
    to: "/workforce-cloud",
    label: "Ringkasan",
    app: "people_ops",
    bundle: "workforce",
    end: true,
    bundleLanding: true,
  },
  { to: "/employees", label: "Karyawan", app: "people_ops", bundle: "workforce" },
  { to: "/attendance", label: "Absensi", apps: ["people_ops", "payroll"], bundle: "workforce" },
  { to: "/chat", label: "Chat" },
  {
    to: "/payment-requests",
    label: "Payment Request",
    apps: ["people_ops", "finance"],
    bundle: "workforce",
    roles: ["admin", "operations", "hr", "finance", "management"],
  },
  // Payroll masuk Revenue Cloud (bukan Workforce) — persis PRD v3.0 §2.2
  // Opsi F: "Payroll hitung (saltab/PPh21) + tagih (invoice/faktur)" adalah
  // satu paket komersial Revenue Cloud bersama Finance.
  {
    to: "/revenue-cloud",
    label: "Ringkasan",
    app: "finance",
    bundle: "revenue",
    end: true,
    bundleLanding: true,
  },
  { to: "/payroll", label: "Payroll", app: "payroll", bundle: "revenue" },
  { to: "/portal-saya", label: "Portal Saya", roles: ["karyawan"], app: "payroll", bundle: "workforce" },
  { to: "/finance", label: "Finance", app: "finance", bundle: "revenue" },
  {
    to: "/govern-cloud",
    label: "Ringkasan",
    roles: ["admin", "management"],
    bundle: "govern",
    end: true,
    bundleLanding: true,
  },
  { to: "/accounting", label: "Akunting", app: "accounting", bundle: "govern" },
  // Kelola rate ber-versi — role finance ke atas.
  {
    to: "/rates",
    label: "Tarif & Rate",
    roles: ["admin", "finance", "management"],
    app: "accounting",
    bundle: "govern",
  },
  // Jejak audit sensitif — disembunyikan dari role non-management.
  { to: "/audit", label: "Audit", roles: ["admin", "management"], bundle: "govern" },
  // Kelola akun tim & role — hanya admin (dibutuhkan utk buat akun role "karyawan"
  // sebelum bisa ditautkan ke data karyawan di halaman People & Ops).
  { to: "/users", label: "Pengguna", roles: ["admin"], bundle: "govern" },
  // Manajemen tenant SaaS — hanya platform_admin (Brian), menu tersendiri
  // (dulu cuma bisa diakses lewat URL langsung, tanpa link menu apa pun).
  { to: "/platform", label: "Manajemen Tenant", roles: ["platform_admin"] },
];

interface AppEntitlement {
  key: string;
  name: string;
  emoji: string;
  description?: string;
  status?: string | null;
  licensed: boolean;
}

// Emoji untuk command palette (hasil pencarian entitas di CommandPalette.tsx
// masih pakai emoji, jadi daftar ini tetap ada utk item quick-nav di sana).
const PAGE_EMOJI: Record<string, string> = {  "/": "🏠",
  "/apps": "🚀",
  "/talent-cloud": "✨",
  "/leads": "🎯",
  "/clients": "🎯",
  "/job-orders": "🧲",
  "/candidates": "🧲",
  "/talent-pool": "🧬",
  "/pages": "📄",
  "/workforce-cloud": "🪪",
  "/employees": "💼",
  "/attendance": "📅",
  "/chat": "💬",
  "/payment-requests": "🧾",
  "/revenue-cloud": "🧾",
  "/payroll": "💼",
  "/portal-saya": "🙋",
  "/finance": "🏗️",
  "/govern-cloud": "⚖️",
  "/accounting": "📊",
  "/rates": "🧮",
  "/audit": "🛡️",
  "/users": "👥",
  "/platform": "🏢",
};

// Ikon sidebar/topbar ala mockup dashboard.html (lucide-react, sudah jadi
// dependency proyek tapi belum pernah dipakai — sebelumnya nav sidebar pakai
// emoji, beda jauh dari garis vektor bersih di mockup).
const PAGE_ICON: Record<string, LucideIcon> = {
  "/": LayoutDashboard,
  "/apps": Rocket,
  "/talent-cloud": Sparkles,
  "/leads": Briefcase,
  "/clients": Building2,
  "/job-orders": Magnet,
  "/candidates": Users,
  "/talent-pool": Dna,
  "/pages": FileText,
  "/workforce-cloud": IdCard,
  "/employees": IdCard,
  "/attendance": Calendar,
  "/chat": MessageCircle,
  "/payment-requests": ClipboardList,
  "/revenue-cloud": Receipt,
  "/payroll": Wallet,
  "/portal-saya": UserCircle,
  "/finance": Receipt,
  "/govern-cloud": Scale,
  "/accounting": BarChart3,
  "/rates": Calculator,
  "/audit": Shield,
  "/users": UserCog,
  "/platform": Building2,
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
  const [inboxOpen, setInboxOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [helpDismissed, setHelpDismissed] = useState(
    () => localStorage.getItem("aeos_helpchip") === "0"
  );
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () =>
      api.get<{ email: string; full_name: string; role: string; tenant_name: string | null }>(
        "/auth/me"
      ),
    enabled: Boolean(getToken()),
    retry: false,
  });
  // Entitlement Fase 7: nav dinamis mengikuti lisensi aplikasi tenant.
  const apps = useQuery({
    queryKey: ["apps"],
    queryFn: () => api.get<AppEntitlement[]>("/apps"),
    enabled: Boolean(getToken()) && me.data?.role !== "platform_admin",
  });
  // Badge Kotak Masuk dari notifikasi in-app sungguhan.
  const unread = useQuery({
    queryKey: ["notif-unread"],
    queryFn: () => api.get<{ count: number }>("/me/notifications/unread-count"),
    enabled: Boolean(getToken()),
    refetchInterval: 30_000,
  });
  const startTrialSidebar = useMutation({
    mutationFn: (key: string) => api.post(`/apps/${key}/trial`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apps"] }),
  });

  // Ctrl/Cmd+K membuka command palette dari mana saja.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
      if (e.key === "Escape") {
        setLauncherOpen(false);
        setInboxOpen(false);
        setProfileMenuOpen(false);
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
  // Platform admin: satu-satunya menu adalah Manajemen Tenant (Brian saja).
  const PLATFORM_ALLOWED_PATHS = ["/platform"];
  if (isPlatform && !PLATFORM_ALLOWED_PATHS.includes(location.pathname)) {
    return <Navigate to="/platform" replace />;
  }
  // Karyawan hanya butuh portal self-service — tanpa akses ke halaman
  // operasional internal (job orders, klien, payroll, dst).
  const KARYAWAN_ALLOWED_PATHS = ["/portal-saya", "/chat"];
  if (isKaryawan && !KARYAWAN_ALLOWED_PATHS.includes(location.pathname)) {
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
    if (isKaryawan && !KARYAWAN_ALLOWED_PATHS.includes(item.to)) return false;
    if (isPlatform && !PLATFORM_ALLOWED_PATHS.includes(item.to)) return false;
    if (item.roles && !(me.data && item.roles.includes(me.data.role))) return false;
    // Selama entitlement belum termuat, tampilkan dulu (hindari kedipan).
    if (!item.apps && !item.app) return true;
    if (!apps.data) return true;
    return licensedFor(item);
  });

  // Grup: Umum (tanpa bundel) → 4 bundel tampilan ala dashboard.html (Talent/
  // Workforce/Revenue/Govern Cloud). Setiap item punya tepat satu `bundle`,
  // jadi tidak ada risiko duplikasi lintas grup seperti skema lama.
  const groups: { label: string; accent?: string; items: NavItem[] }[] = [];
  const umum = visibleItems.filter((i) => !i.bundle);
  if (umum.length) groups.push({ label: "General", items: umum });
  for (const bundle of BUNDLE_ORDER) {
    const items = visibleItems.filter((i) => i.bundle === bundle);
    if (!items.length) continue;
    groups.push({ label: BUNDLE_META[bundle].label, accent: BUNDLE_META[bundle].accent, items });
  }

  const paletteItems: PaletteItem[] = [
    ...groups.flatMap((g) =>
      g.items.map((i) => ({
        id: i.to,
        label: i.label,
        emoji: PAGE_EMOJI[i.to] ?? "📄",
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

  const initials = (me.data?.full_name ?? "?")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const periodLabelRaw = new Date().toLocaleDateString("id-ID", { month: "long", year: "numeric" });
  const periodLabel = periodLabelRaw.charAt(0).toUpperCase() + periodLabelRaw.slice(1);

  // --accent TIDAK pernah di-override per halaman — tetap warisi default
  // tema (:root/.dark) di semua tempat (logo, tombol primer, highlight nav
  // aktif), persis seperti dashboard.html (selalu slate-900, tak pernah
  // ikut warna kategori). Warna kategori (biru/violet/emerald/amber/slate)
  // HANYA menempel di ikon grup sidebar, lewat BUNDLE_META di atas — sama
  // seperti mockup: ikon "Talent/Workforce/Revenue/Govern Cloud" berwarna,
  // tapi item aktif & logo tetap netral gelap.
  return (
    <div className="min-h-screen">
      {/* ===== Topbar (lebar penuh) ===== */}
      <header
        className="sticky top-0 z-20 flex h-14 items-center gap-3 px-4 lg:px-6"
        style={{ backgroundColor: "var(--n-bg-elevated)", borderBottom: "1px solid var(--n-border)" }}
      >
        <button
          onClick={() => setLauncherOpen(true)}
          className="flex shrink-0 cursor-pointer items-center gap-2.5 rounded-lg p-1 transition-colors hover:bg-[var(--n-hover)]"
          title="Buka App Launcher"
        >
          <span
            className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
            style={{ backgroundColor: "var(--accent)" }}
          >
            AE
          </span>
          <span className="hidden text-left sm:block">
            <span className="block text-sm font-semibold leading-none" style={{ color: "var(--n-text)" }}>
              AI Enterprise OS
            </span>
            <span className="mt-0.5 block text-xs" style={{ color: "var(--n-text-muted)" }}>
              Outsourcing Operations
            </span>
          </span>
        </button>

        {me.data?.tenant_name && (
          <span
            className="hidden shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm md:flex"
            style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg)" }}
            title="Workspace aktif"
          >
            <Building2 className="h-4 w-4 shrink-0" style={{ color: "var(--n-text-muted)" }} />
            <span className="font-medium" style={{ color: "var(--n-text)" }}>
              {me.data.tenant_name}
            </span>
            <ChevronsUpDown className="h-4 w-4 shrink-0" style={{ color: "var(--n-text-muted)" }} />
          </span>
        )}

        <button
          onClick={() => setPaletteOpen(true)}
          className="ml-2 hidden max-w-md flex-1 cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm lg:flex"
          style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg)", color: "var(--n-text-muted)" }}
        >
          <Search className="h-4 w-4 shrink-0" />
          <span className="flex-1">Cari halaman, kandidat, invoice...</span>
          <span
            className="rounded px-1.5 py-0.5 text-[10px]"
            style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg-elevated)" }}
          >
            ⌘K
          </span>
        </button>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <button
            onClick={() => setPaletteOpen(true)}
            className="cursor-pointer rounded-lg p-2 transition-colors hover:bg-[var(--n-hover)] lg:hidden"
            style={{ color: "var(--n-text-muted)" }}
            title="Cari"
          >
            <Search className="h-[18px] w-[18px]" />
          </button>
          <button
            className="hidden cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-sm sm:flex"
            style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg-elevated)", color: "var(--n-text)" }}
            title="Periode tampilan (segera dapat difilter)"
          >
            <Calendar className="h-4 w-4" style={{ color: "var(--n-text-muted)" }} />
            {periodLabel}
            <ChevronDown className="h-4 w-4" style={{ color: "var(--n-text-muted)" }} />
          </button>
          <div className="relative">
            <button
              onClick={() => setInboxOpen((v) => !v)}
              className="relative cursor-pointer rounded-lg p-2 transition-colors hover:bg-[var(--n-hover)]"
              style={{ color: "var(--n-text-muted)" }}
              title="Kotak Masuk"
            >
              <Bell className="h-[18px] w-[18px]" />
              {unread.data && unread.data.count > 0 && (
                <span
                  className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500"
                  style={{ boxShadow: "0 0 0 2px var(--n-bg-elevated)" }}
                />
              )}
            </button>
            {inboxOpen && (
              <div className="absolute right-0 top-full z-30 mt-2 w-80">
                <InboxPanel onDone={() => void unread.refetch()} />
              </div>
            )}
          </div>
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors"
            style={{ backgroundColor: "var(--accent)" }}
            title="Aksi cepat (buat halaman, ke chat, dst.)"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Action Baru</span>
          </button>
        </div>
      </header>

      <div className="flex">
        {/* ===== Sidebar ===== */}
        <aside
          className="flex w-64 shrink-0 flex-col sticky top-14 h-[calc(100vh-56px)]"
          style={{ backgroundColor: "var(--n-sidebar)", borderRight: "1px solid var(--n-border)" }}
        >
          <nav className="flex-1 space-y-5 overflow-y-auto p-3">
            {showAppsMenu() && (
              <SidebarLink to="/apps" icon={Rocket} label="Aplikasi" active={location.pathname === "/apps"} />
            )}
            <PageTreeSection pathname={location.pathname} visible={showAppsMenu()} />
            {groups.map((g) => {
              // Bundle dengan landing page (mis. Talent Cloud) diciutkan jadi
              // satu baris klik-in saja, persis mockup talent-cloud.html
              // (sidebar "Aplikasi" cuma 4 baris datar, bukan tree). Sub-
              // halamannya (Pipeline/Klien/Job Orders/dst) diakses lewat link
              // "Lihat semua X →" di dalam landing page-nya sendiri, bukan
              // lewat sidebar — tapi tetap ada di sini (tersembunyi) supaya
              // tetap ikut cek lisensi & tetap muncul di hasil ⌘K.
              const landing = g.items.find((i) => i.bundleLanding);
              const rowItems = landing ? [landing] : g.items;
              return (
                <div key={g.label}>
                  {!landing && (
                    <p
                      className="px-2.5 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-widest"
                      style={{ color: "var(--n-text-muted)" }}
                    >
                      {g.label}
                    </p>
                  )}
                  <div className="space-y-0.5">
                    {rowItems.map((item) => {
                      const Icon = PAGE_ICON[item.to] ?? FileText;
                      return (
                        <NavLink
                          key={item.to}
                          to={item.to}
                          end={item.end}
                          className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors"
                          style={({ isActive }) => ({
                            backgroundColor: isActive ? "var(--accent)" : undefined,
                            color: isActive ? "#ffffff" : "var(--n-text-muted)",
                          })}
                        >
                          {({ isActive }) => (
                            <>
                              {/* Ikon berwarna per kategori (biru=Sales, violet=Recruitment,
                                  emerald=People&Ops/Payroll, amber=Finance, slate=Akunting) —
                                  sama seperti ikon "Talent/Workforce/Revenue/Govern Cloud" di
                                  dashboard.html; netral putih saat item aktif. */}
                              <Icon
                                className="h-4 w-4 shrink-0"
                                style={{ color: isActive ? "#ffffff" : (g.accent ?? "var(--n-text-muted)") }}
                              />
                              {landing ? g.label : item.label}
                            </>
                          )}
                        </NavLink>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </nav>

          {/* Kartu upsell app belum terpasang */}
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
                className="mx-3 mb-3 rounded-xl p-3 text-xs"
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
                  className="mt-2 w-full cursor-pointer rounded-lg py-1.5 text-[12px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                  style={{ backgroundColor: "var(--accent)" }}
                >
                  Coba sekarang
                </button>
              </div>
            );
          })()}

          <div className="relative border-t p-3" style={{ borderColor: "var(--n-border)" }}>
            <div
              className="flex items-center gap-3 rounded-xl p-3"
              style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg)" }}
            >
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                style={{ backgroundColor: "var(--accent)" }}
              >
                {initials}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold" style={{ color: "var(--n-text)" }}>
                  {me.data?.full_name ?? "..."}
                </p>
                <p className="truncate text-xs capitalize" style={{ color: "var(--n-text-muted)" }}>
                  {me.data?.role ?? ""}
                </p>
              </div>
              <button
                onClick={() => setProfileMenuOpen((v) => !v)}
                className="ml-auto shrink-0 cursor-pointer rounded p-1 transition-colors hover:bg-[var(--n-hover)]"
                style={{ color: "var(--n-text-muted)" }}
                title="Menu akun"
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </div>

            {profileMenuOpen && (
              <div
                className="absolute bottom-full left-3 right-3 z-10 mb-1.5 overflow-hidden rounded-lg shadow-lg"
                style={{ border: "1px solid var(--n-border)", backgroundColor: "var(--n-bg-elevated)" }}
              >
                <button
                  onClick={() => {
                    toggle();
                    setProfileMenuOpen(false);
                  }}
                  className="flex w-full cursor-pointer items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--n-hover)]"
                  style={{ color: "var(--n-text)" }}
                >
                  {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                  {dark ? "Mode Terang" : "Mode Gelap"}
                </button>
                <button
                  onClick={() => {
                    clearToken();
                    navigate("/login");
                  }}
                  className="flex w-full cursor-pointer items-center gap-2.5 border-t px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--n-hover)]"
                  style={{ color: "var(--n-text)", borderColor: "var(--n-border)" }}
                >
                  <X className="h-4 w-4" />
                  Keluar
                </button>
              </div>
            )}
          </div>
        </aside>

        {/* ===== Konten ===== */}
        <main className="min-h-[calc(100vh-56px)] flex-1 overflow-x-auto">
          <div className="mx-auto w-full max-w-[1440px] px-4 py-5 lg:px-6 lg:py-6">
            <Outlet />
          </div>
        </main>
      </div>

      {/* App Launcher modal dari workspace switcher */}
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
                className="ml-auto flex cursor-pointer items-center gap-1 rounded px-2 py-1 text-xs hover:bg-[var(--n-hover)]"
                onClick={() => setLauncherOpen(false)}
                style={{ color: "var(--n-text-muted)" }}
              >
                <X className="h-3.5 w-3.5" /> Esc
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-5 pt-3">
              <AppLauncherGrid compact />
            </div>
            <div
              className="flex items-center gap-2 border-t px-5 py-3 text-[12.5px]"
              style={{ borderColor: "var(--n-border)", color: "var(--n-text-muted)" }}
            >
              <Lightbulb className="h-4 w-4 shrink-0" /> Ambil{" "}
              <b style={{ color: "var(--n-text)" }}>Full Package</b> (semua aplikasi + AI) dan
              hemat hingga 35% dibeli satuan.
            </div>
          </div>
        </div>
      )}

      {/* FAB Tanya AEOS + help chip */}
      {showAppsMenu() && location.pathname !== "/chat" && (
        <>
          {!helpDismissed && (
            <div
              className="fixed bottom-4 left-4 z-20 hidden items-center gap-2 rounded-lg px-3 py-2 text-[11.5px] md:flex"
              style={{
                backgroundColor: "var(--n-bg-elevated)",
                border: "1px solid var(--n-border)",
                color: "var(--n-text-muted)",
                boxShadow: "0 2px 8px rgba(15,15,15,.08)",
              }}
            >
              <Lightbulb className="h-4 w-4 shrink-0" />
              <span>
                Tekan <kbd className="font-mono">⌘K</kbd> untuk cari cepat · sebut{" "}
                <b style={{ color: "var(--n-text)" }}>@AEOS</b> di chat untuk bertanya
              </span>
              <button
                className="ml-1 cursor-pointer text-xs hover:underline"
                onClick={() => {
                  localStorage.setItem("aeos_helpchip", "0");
                  setHelpDismissed(true);
                }}
              >
                tutup
              </button>
            </div>
          )}
          <button
            onClick={() => navigate("/chat")}
            className="fixed bottom-5 right-5 z-30 flex cursor-pointer items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold text-white shadow-lg transition-transform hover:scale-105"
            style={{ backgroundColor: "var(--accent)" }}
            title="Buka Chat — sebut @AEOS untuk bertanya"
          >
            <Sparkles className="h-4 w-4" /> Tanya AEOS AI
          </button>
        </>
      )}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={paletteItems} />
    </div>
  );
}

function SidebarLink({
  to,
  icon: Icon,
  label,
  active,
}: {
  to: string;
  icon: LucideIcon;
  label: string;
  active: boolean;
}) {
  return (
    <NavLink
      to={to}
      end
      className="mb-2 flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors"
      style={{
        backgroundColor: active ? "var(--accent)" : undefined,
        color: active ? "#ffffff" : "var(--n-text-muted)",
      }}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </NavLink>
  );
}

/// Page tree: daftar halaman buatan user dari /pages, ditautkan ke editor /pages/{id}.
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
      <div className="flex items-center justify-between px-2.5 pb-1.5 pt-1">
        <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--n-text-muted)" }}>
          Workspace
        </span>
        <button
          onClick={() => createPage.mutate()}
          disabled={createPage.isPending}
          title="Halaman baru"
          className="cursor-pointer text-[var(--accent)] hover:opacity-80 disabled:cursor-not-allowed"
        >
          <Plus className="h-3.5 w-3.5" />
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
              className="block truncate rounded-lg px-2.5 py-1.5 text-sm transition-colors hover:bg-[var(--n-hover)]"
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
                  className="block truncate rounded-lg py-1.5 pl-7 pr-2.5 text-xs transition-colors hover:bg-[var(--n-hover)]"
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

/// Panel Kotak Masuk: 5 notifikasi terakhir + tandai dibaca.
function InboxPanel({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const items = useQuery({
    queryKey: ["notif-list"],
    queryFn: () =>
      api.get<
        { id: string; title: string; body: string | null; read_at: string | null }[]
      >("/me/notifications?unread_only=true"),
  });
  const readAll = useMutation({
    mutationFn: () => api.post("/me/notifications/read-all", {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["notif-list"] });
      void qc.invalidateQueries({ queryKey: ["notif-unread"] });
      onDone();
    },
  });

  return (
    <div className="card shadow-lg">
      <div className="mb-1 flex items-center justify-between text-xs">
        <b style={{ color: "var(--n-text)" }}>Belum dibaca</b>
        <button
          onClick={() => readAll.mutate()}
          disabled={readAll.isPending || (items.data?.length ?? 0) === 0}
          className="cursor-pointer text-[var(--accent)] hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Tandai semua dibaca
        </button>
      </div>
      {(items.data ?? []).slice(0, 5).map((n) => (
        <div key={n.id} className="border-t py-1.5 text-xs first:border-t-0" style={{ borderColor: "var(--n-border)" }}>
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
        <p className="flex items-center gap-1.5 text-xs" style={{ color: "var(--n-text-muted)" }}>
          <PartyPopper className="h-3.5 w-3.5 shrink-0" /> Tidak ada notifikasi belum dibaca.
        </p>
      )}
    </div>
  );
}
