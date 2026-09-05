import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Ban,
  BarChart3,
  Bell,
  Briefcase,
  Building2,
  Calculator,
  Calendar,
  ChevronDown,
  ChevronsUpDown,
  ClipboardList,
  CreditCard,
  Dna,
  FileCheck2,
  FileSignature,
  FileText,
  Gift,
  IdCard,
  LayoutDashboard,
  Lightbulb,
  type LucideIcon,
  Magnet,
  MessageCircle,
  MessagesSquare,
  Moon,
  MoreHorizontal,
  PartyPopper,
  Plus,
  Receipt,
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
import { api, clearToken, formatRupiah, getToken } from "../api/client";
import CommandPalette, { type PaletteItem } from "./CommandPalette";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
  roles?: string[];
  bundle?: Category;
  // Item ini adalah landing page kategori-nya (mis. /talent-cloud) — kalau
  // sebuah grup kategori punya item dengan flag ini, sidebar HANYA menampilkan
  // satu baris tunggal (nama kategori, ikon landing) alih-alih tree flat semua
  // item. Item lain di kategori itu tetap ada (tetap muncul di ⌘K), cuma
  // disembunyikan dari daftar sidebar — navigasi ke sana dilakukan lewat
  // link "Lihat semua X →" di dalam landing page itu sendiri.
  bundleLanding?: boolean;
}

// 5 kategori sidebar Opsi G (Fase 28), menggantikan branding "Cloud"
// (Talent/Workforce/Revenue/Govern) — murni pengelompokan TAMPILAN, tidak
// terkait sama sekali dengan app_key teknis di backend (`core/apps.py`,
// sudah tidak dipakai untuk penegakan akses sejak guard subscription
// menggantikan lisensi per-SKU). Semua fitur terbuka penuh untuk tenant
// berlangganan aktif -- kategori ini murni navigasi, bukan gating.
type Category = "crm" | "recruitment" | "workforce" | "finance_accounting" | "administration";

const CATEGORY_META: Record<Category, { label: string; accent: string }> = {
  crm: { label: "CRM", accent: "#7c3aed" },
  recruitment: { label: "Recruitment", accent: "#2563eb" },
  workforce: { label: "Workforce", accent: "#059669" },
  finance_accounting: { label: "Finance & Accounting", accent: "#d97706" },
  administration: { label: "Administration", accent: "#475569" },
};

const CATEGORY_ORDER: Category[] = [
  "crm",
  "recruitment",
  "workforce",
  "finance_accounting",
  "administration",
];

// `roles` di bawah cuma menyembunyikan menu (allowlist ketat, admin TIDAK
// otomatis lolos di sini) — keamanan sesungguhnya ditegakkan backend lewat
// `require_roles(...)` per route. Sumber kebenaran role per area ada di
// `backend/app/core/permissions.py`; kalau ubah salah satu, cek yang lain
// biar sidebar tidak menyesatkan (menampilkan/menyembunyikan menu yang
// sebenarnya beda dgn apa yang backend izinkan).
const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  // Ringkasan gabungan Sales CRM + Recruitment (halaman lama, isinya lintas
  // dua kategori baru) — diletakkan di bawah "crm" saja (keputusan
  // implementasi Fase 28: satu landing bersama lebih murah daripada
  // membelah jadi dua halaman ringkasan terpisah sekarang).
  {
    to: "/talent-cloud",
    label: "Ringkasan",
    bundle: "crm",
    end: true,
    bundleLanding: true,
  },
  { to: "/leads", label: "Pipeline", bundle: "crm" },
  { to: "/clients", label: "Klien", bundle: "crm" },
  { to: "/quotations", label: "Quotation", bundle: "crm" },
  { to: "/agreements", label: "Agreement", bundle: "crm" },
  { to: "/job-orders", label: "Job Orders", bundle: "recruitment" },
  { to: "/candidates", label: "Kandidat", bundle: "recruitment" },
  { to: "/referral", label: "Referral", bundle: "recruitment" },
  {
    to: "/talent-pool",
    label: "Talent Pool",
    bundle: "recruitment",
    roles: ["admin", "recruiter", "operations", "hr", "management"],
  },
  {
    to: "/ai-interview",
    label: "AI Interview",
    bundle: "recruitment",
    roles: ["admin", "recruiter", "management"],
  },
  {
    to: "/blacklist",
    label: "Black Lists",
    bundle: "recruitment",
    roles: ["admin", "recruiter", "management"],
  },
  {
    to: "/workforce-cloud",
    label: "Ringkasan",
    bundle: "workforce",
    end: true,
    bundleLanding: true,
  },
  { to: "/employees", label: "Karyawan", bundle: "workforce" },
  { to: "/attendance", label: "Absensi", bundle: "workforce" },
  { to: "/chat", label: "Chat" },
  {
    to: "/payment-requests",
    label: "Payment Request",
    bundle: "workforce",
    roles: ["admin", "operations", "hr", "finance", "management"],
  },
  // Payroll sengaja di Workforce, bukan Finance & Accounting -- keputusan
  // desain Fase 28 (docs/design/design.md §7), beda dari pengelompokan
  // Opsi F lama yang menyatukan payroll dengan Revenue Cloud.
  { to: "/payroll", label: "Payroll", bundle: "workforce" },
  { to: "/portal-saya", label: "Portal Saya", roles: ["karyawan"], bundle: "workforce" },
  // "Ringkasan Finance" jadi entri biasa (bukan bundleLanding) karena
  // /govern-cloud di bawah sudah jadi landing kategori administration --
  // isinya audit+users+roles, cocoknya di sana, bukan di Finance & Accounting
  // seperti pengelompokan Opsi F lama.
  { to: "/revenue-cloud", label: "Ringkasan Finance", bundle: "finance_accounting" },
  { to: "/finance", label: "Finance", bundle: "finance_accounting" },
  { to: "/accounting", label: "Akunting", bundle: "finance_accounting" },
  // Landing kategori administration -- isinya audit log + users + roles,
  // konten halaman ini sebenarnya sudah pas di sini sejak awal.
  {
    to: "/govern-cloud",
    label: "Ringkasan",
    roles: ["admin", "management"],
    bundle: "administration",
    end: true,
    bundleLanding: true,
  },
  // Kelola rate ber-versi — role finance ke atas.
  {
    to: "/rates",
    label: "Rate Configuration",
    roles: ["admin", "finance", "management"],
    bundle: "administration",
  },
  // Langganan & saldo kredit Opsi G (Fase 28) — role finance ke atas, sama
  // seperti Rate Configuration.
  {
    to: "/billing",
    label: "Pembayaran",
    roles: ["admin", "finance", "management"],
    bundle: "administration",
  },
  // Jejak audit sensitif — disembunyikan dari role non-management.
  { to: "/audit", label: "Audit", roles: ["admin", "management"], bundle: "administration" },
  // Kelola akun tim & role — hanya admin (dibutuhkan utk buat akun role "karyawan"
  // sebelum bisa ditautkan ke data karyawan di halaman People & Ops).
  { to: "/users", label: "Pengguna", roles: ["admin"], bundle: "administration" },
  // Manajemen tenant SaaS — hanya platform_admin (Brian), menu tersendiri
  // (dulu cuma bisa diakses lewat URL langsung, tanpa link menu apa pun).
  { to: "/platform", label: "Manajemen Tenant", roles: ["platform_admin"] },
];

// Emoji untuk command palette (hasil pencarian entitas di CommandPalette.tsx
// masih pakai emoji, jadi daftar ini tetap ada utk item quick-nav di sana).
const PAGE_EMOJI: Record<string, string> = {
  "/": "🏠",
  "/talent-cloud": "✨",
  "/leads": "🎯",
  "/clients": "🎯",
  "/quotations": "📝",
  "/agreements": "📜",
  "/job-orders": "🧲",
  "/candidates": "🧲",
  "/referral": "🎁",
  "/talent-pool": "🧬",
  "/ai-interview": "🎙️",
  "/blacklist": "🚫",
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
  "/billing": "💳",
  "/audit": "🛡️",
  "/users": "👥",
  "/platform": "🏢",
};

// Ikon sidebar/topbar ala mockup dashboard.html (lucide-react, sudah jadi
// dependency proyek tapi belum pernah dipakai — sebelumnya nav sidebar pakai
// emoji, beda jauh dari garis vektor bersih di mockup).
const PAGE_ICON: Record<string, LucideIcon> = {
  "/": LayoutDashboard,
  "/talent-cloud": Sparkles,
  "/leads": Briefcase,
  "/clients": Building2,
  "/quotations": FileSignature,
  "/agreements": FileCheck2,
  "/job-orders": Magnet,
  "/candidates": Users,
  "/referral": Gift,
  "/talent-pool": Dna,
  "/ai-interview": MessagesSquare,
  "/blacklist": Ban,
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
  "/billing": CreditCard,
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
  const { dark, toggle } = useDarkMode();
  const [paletteOpen, setPaletteOpen] = useState(false);
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
  // Badge Kotak Masuk dari notifikasi in-app sungguhan.
  const unread = useQuery({
    queryKey: ["notif-unread"],
    queryFn: () => api.get<{ count: number }>("/me/notifications/unread-count"),
    enabled: Boolean(getToken()),
    refetchInterval: 30_000,
  });
  // Indikator saldo kredit Opsi G (Fase 28) -- hanya tenant biasa, bukan
  // platform_admin/karyawan (mereka tidak berlangganan langsung).
  const balance = useQuery({
    queryKey: ["billing-balance"],
    queryFn: () =>
      api.get<{
        cycle_remaining: number;
        cycle_included: number;
        credit_balance: number;
        state: "normal" | "warning" | "empty";
      }>("/billing/balance-summary"),
    enabled:
      Boolean(getToken()) && me.data?.role !== "platform_admin" && me.data?.role !== "karyawan",
    refetchInterval: 30_000,
    retry: false,
  });

  // Ctrl/Cmd+K membuka command palette dari mana saja.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
      if (e.key === "Escape") {
        setInboxOpen(false);
        setProfileMenuOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
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

  // Visibilitas nav murni role-based sejak Fase 28 -- semua fitur terbuka
  // penuh untuk tenant berlangganan aktif (ditegakkan backend lewat
  // `require_active_subscription()`), tidak ada lagi gating per-app_key.
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (isKaryawan && !KARYAWAN_ALLOWED_PATHS.includes(item.to)) return false;
    if (isPlatform && !PLATFORM_ALLOWED_PATHS.includes(item.to)) return false;
    if (item.roles && !(me.data && item.roles.includes(me.data.role))) return false;
    return true;
  });

  // Grup: Umum (tanpa kategori) → 5 kategori Opsi G. Setiap item punya
  // tepat satu `bundle`, jadi tidak ada risiko duplikasi lintas grup.
  const groups: { label: string; accent?: string; items: NavItem[] }[] = [];
  const umum = visibleItems.filter((i) => !i.bundle);
  if (umum.length) groups.push({ label: "General", items: umum });
  for (const bundle of CATEGORY_ORDER) {
    const items = visibleItems.filter((i) => i.bundle === bundle);
    if (!items.length) continue;
    groups.push({
      label: CATEGORY_META[bundle].label,
      accent: CATEGORY_META[bundle].accent,
      items,
    });
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
    {
      id: "theme",
      label: dark ? "Mode Terang" : "Mode Gelap",
      emoji: dark ? "☀️" : "🌙",
      group: "Preferensi",
      action: toggle,
    },
  ];

  function isTenantUser(): boolean {
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
  // aktif). Warna kategori (ungu/biru/emerald/amber/slate) HANYA menempel
  // di ikon grup sidebar, lewat CATEGORY_META di atas — item aktif & logo
  // tetap netral gelap.
  return (
    <div className="min-h-screen">
      {/* ===== Topbar (lebar penuh) ===== */}
      <header
        className="sticky top-0 z-20 flex h-14 items-center gap-3 px-4 lg:px-6"
        style={{ backgroundColor: "var(--bg-elevated)", borderBottom: "1px solid var(--border)" }}
      >
        <button
          onClick={() => navigate("/")}
          className="flex shrink-0 cursor-pointer items-center gap-2.5 rounded-lg p-1 transition-colors hover:bg-[var(--hover)]"
          title="Ke Dashboard"
        >
          <span
            className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
            style={{ backgroundColor: "var(--accent)" }}
          >
            AE
          </span>
          <span className="hidden text-left sm:block">
            <span className="block text-sm font-semibold leading-none" style={{ color: "var(--text)" }}>
              AI Enterprise OS
            </span>
            <span className="mt-0.5 block text-xs" style={{ color: "var(--text-muted)" }}>
              Outsourcing Operations
            </span>
          </span>
        </button>

        {me.data?.tenant_name && (
          <span
            className="hidden shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm md:flex"
            style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg)" }}
            title="Workspace aktif"
          >
            <Building2 className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
            <span className="font-medium" style={{ color: "var(--text)" }}>
              {me.data.tenant_name}
            </span>
            <ChevronsUpDown className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
          </span>
        )}

        <button
          onClick={() => setPaletteOpen(true)}
          className="ml-2 hidden max-w-md flex-1 cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm lg:flex"
          style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg)", color: "var(--text-muted)" }}
        >
          <Search className="h-4 w-4 shrink-0" />
          <span className="flex-1">Cari halaman, kandidat, invoice...</span>
          <span
            className="rounded px-1.5 py-0.5 text-[10px]"
            style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
          >
            ⌘K
          </span>
        </button>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <button
            onClick={() => setPaletteOpen(true)}
            className="cursor-pointer rounded-lg p-2 transition-colors hover:bg-[var(--hover)] lg:hidden"
            style={{ color: "var(--text-muted)" }}
            title="Cari"
          >
            <Search className="h-[18px] w-[18px]" />
          </button>
          <button
            className="hidden cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-sm sm:flex"
            style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)", color: "var(--text)" }}
            title="Periode tampilan (segera dapat difilter)"
          >
            <Calendar className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
            {periodLabel}
            <ChevronDown className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
          </button>
          {balance.data && (
            <button
              onClick={() => navigate("/billing")}
              className={`hidden cursor-pointer sm:flex pill ${
                balance.data.state === "empty"
                  ? "p-red"
                  : balance.data.state === "warning"
                    ? "p-orange"
                    : "p-green"
              }`}
              title="Saldo & langganan Opsi G"
            >
              <Wallet className="h-3.5 w-3.5" />
              {formatRupiah(balance.data.cycle_remaining + balance.data.credit_balance)}
            </button>
          )}
          <div className="relative">
            <button
              onClick={() => setInboxOpen((v) => !v)}
              className="relative cursor-pointer rounded-lg p-2 transition-colors hover:bg-[var(--hover)]"
              style={{ color: "var(--text-muted)" }}
              title="Kotak Masuk"
            >
              <Bell className="h-[18px] w-[18px]" />
              {unread.data && unread.data.count > 0 && (
                <span
                  className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500"
                  style={{ boxShadow: "0 0 0 2px var(--bg-elevated)" }}
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
          style={{ backgroundColor: "var(--sidebar)", borderRight: "1px solid var(--border)" }}
        >
          <nav className="flex-1 space-y-5 overflow-y-auto p-3">
            <PageTreeSection pathname={location.pathname} visible={isTenantUser()} />
            {groups.map((g) => {
              // Kategori dengan landing page (mis. CRM → /talent-cloud) diciutkan
              // jadi satu baris klik-in saja, bukan tree flat. Sub-halamannya
              // (Pipeline/Klien/Job Orders/dst) diakses lewat link "Lihat semua
              // X →" di dalam landing page-nya sendiri, bukan lewat sidebar —
              // tapi tetap ada di sini (tersembunyi) supaya tetap muncul di ⌘K.
              const landing = g.items.find((i) => i.bundleLanding);
              const rowItems = landing ? [landing] : g.items;
              return (
                <div key={g.label}>
                  {!landing && (
                    <p
                      className="px-2.5 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-widest"
                      style={{ color: "var(--text-muted)" }}
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
                            color: isActive ? "#ffffff" : "var(--text-muted)",
                          })}
                        >
                          {({ isActive }) => (
                            <>
                              {/* Ikon berwarna per kategori (ungu=CRM, biru=Recruitment,
                                  emerald=Workforce, amber=Finance & Accounting, slate=
                                  Administration); netral putih saat item aktif. */}
                              <Icon
                                className="h-4 w-4 shrink-0"
                                style={{ color: isActive ? "#ffffff" : (g.accent ?? "var(--text-muted)") }}
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

          <div className="relative border-t p-3" style={{ borderColor: "var(--border)" }}>
            <div
              className="flex items-center gap-3 rounded-xl p-3"
              style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg)" }}
            >
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                style={{ backgroundColor: "var(--accent)" }}
              >
                {initials}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold" style={{ color: "var(--text)" }}>
                  {me.data?.full_name ?? "..."}
                </p>
                <p className="truncate text-xs capitalize" style={{ color: "var(--text-muted)" }}>
                  {me.data?.role ?? ""}
                </p>
              </div>
              <button
                onClick={() => setProfileMenuOpen((v) => !v)}
                className="ml-auto shrink-0 cursor-pointer rounded p-1 transition-colors hover:bg-[var(--hover)]"
                style={{ color: "var(--text-muted)" }}
                title="Menu akun"
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </div>

            {profileMenuOpen && (
              <div
                className="absolute bottom-full left-3 right-3 z-10 mb-1.5 overflow-hidden rounded-lg shadow-lg"
                style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
              >
                <button
                  onClick={() => {
                    toggle();
                    setProfileMenuOpen(false);
                  }}
                  className="flex w-full cursor-pointer items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--hover)]"
                  style={{ color: "var(--text)" }}
                >
                  {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                  {dark ? "Mode Terang" : "Mode Gelap"}
                </button>
                <button
                  onClick={() => {
                    clearToken();
                    navigate("/login");
                  }}
                  className="flex w-full cursor-pointer items-center gap-2.5 border-t px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--hover)]"
                  style={{ color: "var(--text)", borderColor: "var(--border)" }}
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

      {/* FAB Tanya AEOS + help chip */}
      {isTenantUser() && location.pathname !== "/chat" && (
        <>
          {!helpDismissed && (
            <div
              className="fixed bottom-4 left-4 z-20 hidden items-center gap-2 rounded-lg px-3 py-2 text-[11.5px] md:flex"
              style={{
                backgroundColor: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
                boxShadow: "0 2px 8px rgba(15,15,15,.08)",
              }}
            >
              <Lightbulb className="h-4 w-4 shrink-0" />
              <span>
                Tekan <kbd className="font-mono">⌘K</kbd> untuk cari cepat · sebut{" "}
                <b style={{ color: "var(--text)" }}>@AEOS</b> di chat untuk bertanya
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
        <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
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
              className="block truncate rounded-lg px-2.5 py-1.5 text-sm transition-colors hover:bg-[var(--hover)]"
              style={{ color: pathname === `/pages/${p.id}` ? "var(--text)" : "var(--text-muted)" }}
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
                  className="block truncate rounded-lg py-1.5 pl-7 pr-2.5 text-xs transition-colors hover:bg-[var(--hover)]"
                  style={{ color: pathname === `/pages/${c.id}` ? "var(--text)" : "var(--text-muted)" }}
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
        <b style={{ color: "var(--text)" }}>Belum dibaca</b>
        <button
          onClick={() => readAll.mutate()}
          disabled={readAll.isPending || (items.data?.length ?? 0) === 0}
          className="cursor-pointer text-[var(--accent)] hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Tandai semua dibaca
        </button>
      </div>
      {(items.data ?? []).slice(0, 5).map((n) => (
        <div key={n.id} className="border-t py-1.5 text-xs first:border-t-0" style={{ borderColor: "var(--border)" }}>
          <p className="font-medium" style={{ color: "var(--text)" }}>
            {n.title}
          </p>
          {n.body && (
            <p className="truncate" style={{ color: "var(--text-muted)" }}>
              {n.body}
            </p>
          )}
        </div>
      ))}
      {(items.data?.length ?? 0) === 0 && (
        <p className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
          <PartyPopper className="h-3.5 w-3.5 shrink-0" /> Tidak ada notifikasi belum dibaca.
        </p>
      )}
    </div>
  );
}
