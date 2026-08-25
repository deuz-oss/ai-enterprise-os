import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, clearToken, getToken } from "../api/client";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/leads", label: "Pipeline", app: "sales_crm" },
  { to: "/clients", label: "Klien", app: "sales_crm" },
  { to: "/job-orders", label: "Job Orders", app: "recruitment" },
  { to: "/candidates", label: "Kandidat", app: "recruitment" },
  { to: "/employees", label: "Karyawan", app: "hr_payroll" },
  { to: "/payroll", label: "Payroll", app: "hr_payroll" },
  { to: "/finance", label: "Finance", app: "operations_billing" },
  { to: "/accounting", label: "Akunting", app: "finance_accounting" },
  // Jejak audit sensitif — disembunyikan dari role non-management.
  { to: "/audit", label: "Audit", roles: ["admin", "management"] },
  // Portal self-service karyawan — hanya untuk akun role karyawan.
  { to: "/portal-saya", label: "Portal Saya", roles: ["karyawan"], app: "hr_payroll" },
];

// Platform admin hanya melihat manajemen tenant.
const PLATFORM_NAV_ITEMS = [{ to: "/platform", label: "Tenant", end: true }];

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
    enabled: Boolean(getToken()),
    retry: false,
  });
  // Entitlement Fase 7: nav dinamis mengikuti lisensi aplikasi tenant.
  const apps = useQuery({
    queryKey: ["apps"],
    queryFn: () =>
      api.get<{ key: string; licensed: boolean }[]>("/apps"),
    enabled: Boolean(getToken()) && me.data?.role !== "platform_admin",
  });

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
  const items = (isPlatform
    ? PLATFORM_NAV_ITEMS
    : NAV_ITEMS.filter(
        (item) => !item.roles || (me.data && item.roles.includes(me.data.role))
      )
  ).filter((item) => {
    // Selama entitlement belum termuat, tampilkan dulu (hindari kedipan).
    if (!("app" in item) || !item.app) return true;
    if (!apps.data) return true;
    return apps.data.some((a) => a.key === item.app && a.licensed);
  });
  // Menu Aplikasi: launcher + upsell, bukan untuk karyawan & platform admin.
  const showAppsMenu = Boolean(getToken()) && me.data && !isPlatform && me.data.role !== "karyawan";

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col bg-slate-900 text-slate-200">
        <div className="px-5 py-6">
          <p className="text-lg font-bold text-white">AI Enterprise OS</p>
          <p className="mt-1 text-xs text-slate-400">Outsourcing Operations</p>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {showAppsMenu && (
            <NavLink
              to="/apps"
              end
              className={({ isActive }) =>
                `mb-2 block rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-indigo-600 text-white" : "hover:bg-slate-800"
                }`
              }
            >
              🚀 Aplikasi
            </NavLink>
          )}
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-indigo-600 text-white" : "hover:bg-slate-800"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-700 p-4 text-sm">
          <p className="truncate text-slate-300">{me.data?.full_name ?? "..."}</p>
          <button
            className="mt-2 text-xs text-slate-400 hover:text-white"
            onClick={() => {
              clearToken();
              navigate("/login");
            }}
          >
            Keluar
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-x-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
