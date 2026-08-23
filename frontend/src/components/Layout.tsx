import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { api, clearToken, getToken } from "../api/client";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/leads", label: "Pipeline" },
  { to: "/clients", label: "Klien" },
  { to: "/job-orders", label: "Job Orders" },
  { to: "/candidates", label: "Kandidat" },
  { to: "/employees", label: "Karyawan" },
  { to: "/payroll", label: "Payroll" },
  { to: "/finance", label: "Finance" },
];

export default function Layout() {
  const navigate = useNavigate();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
    enabled: Boolean(getToken()),
    retry: false,
  });

  if (!getToken()) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col bg-slate-900 text-slate-200">
        <div className="px-5 py-6">
          <p className="text-lg font-bold text-white">AI Enterprise OS</p>
          <p className="mt-1 text-xs text-slate-400">Outsourcing Operations</p>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV_ITEMS.map((item) => (
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
