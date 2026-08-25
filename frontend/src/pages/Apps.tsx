import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

interface AppEntitlement {
  key: string;
  name: string;
  emoji: string;
  accent: string;
  description: string;
  depends_on: string[];
  licensed: boolean;
  status: string | null;
  expires_at: string | null;
}

const ACCENT_RING: Record<string, string> = {
  blue: "border-blue-200 bg-blue-50/60",
  purple: "border-purple-200 bg-purple-50/60",
  green: "border-emerald-200 bg-emerald-50/60",
  orange: "border-orange-200 bg-orange-50/60",
  amber: "border-amber-200 bg-amber-50/60",
  red: "border-rose-200 bg-rose-50/60",
  violet: "border-violet-200 bg-violet-50/60",
};

const STATUS_BADGE: Record<string, string> = {
  aktif: "bg-emerald-100 text-emerald-700",
  trial: "bg-amber-100 text-amber-700",
  kedaluwarsa: "bg-slate-100 text-slate-500",
};

const HOME_ROUTE: Record<string, string> = {
  sales_crm: "/leads",
  recruitment: "/job-orders",
  hr_payroll: "/employees",
  operations_billing: "/finance",
  finance_accounting: "/accounting",
  esign: "/employees",
  ai_addon: "/employees",
};

export default function Apps() {
  const qc = useQueryClient();
  const { data: apps, isLoading, error } = useQuery({
    queryKey: ["apps"],
    queryFn: () => api.get<AppEntitlement[]>("/apps"),
  });

  const startTrial = useMutation({
    mutationFn: (key: string) => api.post(`/apps/${key}/trial`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apps"] }),
  });

  if (isLoading) return <p className="text-slate-500">Memuat aplikasi...</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;

  const licensedCount = (apps ?? []).filter((a) => a.licensed).length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Aplikasi</h1>
        <p className="mt-1 text-sm text-slate-500">
          {licensedCount} dari {apps?.length ?? 0} aplikasi aktif untuk
          perusahaan Anda. Mulai trial 14 hari langsung dari sini — tanpa
          hubungi sales.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(apps ?? []).map((app) => (
          <div
            key={app.key}
            className={`card border ${ACCENT_RING[app.accent] ?? ""} flex flex-col`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-3">
                <span className="text-3xl">{app.emoji}</span>
                <div>
                  <h2 className="font-semibold text-slate-800">{app.name}</h2>
                  {app.status && (
                    <span className={`badge mt-0.5 ${STATUS_BADGE[app.status] ?? ""}`}>
                      {app.status}
                      {app.status === "trial" && app.expires_at
                        ? ` s.d. ${new Date(app.expires_at).toLocaleDateString("id-ID")}`
                        : ""}
                    </span>
                  )}
                </div>
              </div>
              {app.depends_on.length > 0 && (
                <span
                  className="text-[11px] text-slate-400"
                  title={`Butuh: ${app.depends_on.join(", ")}`}
                >
                  butuh {app.depends_on.length} app
                </span>
              )}
            </div>

            <p className="mt-3 flex-1 text-sm text-slate-600">{app.description}</p>

            <div className="mt-4">
              {app.licensed ? (
                <Link
                  to={HOME_ROUTE[app.key] ?? "/"}
                  className="btn-secondary inline-block w-full text-center"
                >
                  Buka Aplikasi
                </Link>
              ) : (
                <>
                  <button
                    onClick={() => startTrial.mutate(app.key)}
                    disabled={startTrial.isPending || app.status === "kedaluwarsa"}
                    className="btn w-full"
                  >
                    {app.status === "kedaluwarsa"
                      ? "Trial sudah digunakan"
                      : "Coba Gratis 14 Hari"}
                  </button>
                  {startTrial.error && (
                    <p className="mt-2 text-xs text-red-600">
                      {(startTrial.error as Error).message}
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
