import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export interface AppEntitlement {
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

export const HOME_ROUTE: Record<string, string> = {
  sales_crm: "/leads",
  recruitment: "/job-orders",
  hr_payroll: "/employees",
  operations_billing: "/finance",
  finance_accounting: "/accounting",
  esign: "/employees",
  ai_addon: "/employees",
};

export function useApps() {
  return useQuery({
    queryKey: ["apps"],
    queryFn: () => api.get<AppEntitlement[]>("/apps"),
  });
}

/// Grid kartu aplikasi ala mockup launcher (badge Terpasang / Install +
/// tombol trial). Dipakai modal launcher & rute /apps sekaligus.
export default function AppLauncherGrid({ compact = false }: { compact?: boolean }) {
  const qc = useQueryClient();
  const { data: apps, isLoading, error } = useApps();

  const startTrial = useMutation({
    mutationFn: (key: string) => api.post(`/apps/${key}/trial`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apps"] }),
  });

  if (isLoading)
    return <p className="px-5 py-4 text-sm" style={{ color: "var(--n-text-muted)" }}>Memuat aplikasi…</p>;
  if (error)
    return <p className="px-5 py-4 text-sm text-red-600">{(error as Error).message}</p>;

  return (
    <div className={compact ? "grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3" : "grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"}>
      {(apps ?? []).map((app) => {
        const off = !app.licensed;
        return (
          <div
            key={app.key}
            className={`flex flex-col rounded-[10px] p-3.5 transition-colors ${off ? "opacity-75" : ""}`}
            style={{
              border: `1px ${off ? "dashed" : "solid"} var(--n-border)`,
              backgroundColor: "var(--n-bg-elevated)",
            }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span
                  className="flex h-9 w-9 items-center justify-center rounded-[9px] text-xl"
                  style={{ backgroundColor: "var(--n-hover)" }}
                >
                  {app.emoji}
                </span>
                <b className="text-[13.5px]" style={{ color: "var(--n-text)" }}>
                  {app.name}
                </b>
              </div>
              {app.licensed ? (
                <span className="text-[11px]" style={{ color: "var(--n-text-muted)" }}>
                  ✓ Terpasang
                </span>
              ) : (
                <button
                  onClick={() => startTrial.mutate(app.key)}
                  disabled={startTrial.isPending || app.status === "kedaluwarsa"}
                  className="rounded px-2 py-0.5 text-[11.5px] font-semibold disabled:opacity-40"
                  style={{
                    color: "#2383E2",
                    backgroundColor: "rgba(35,131,226,.14)",
                  }}
                >
                  {app.status === "kedaluwarsa"
                    ? "Trial habis"
                    : app.status === "trial"
                      ? "Lanjutkan Trial"
                      : "+ Install"}
                </button>
              )}
            </div>

            <p className="mt-1.5 mb-2 flex-1 text-[11.5px] leading-relaxed" style={{ color: "var(--n-text-muted)" }}>
              {app.description}
            </p>

            <div className="mt-1 flex items-center justify-between gap-2 text-xs">
              {app.status && (
                <span
                  className="badge"
                  style={{
                    backgroundColor:
                      app.status === "aktif"
                        ? "rgba(15,123,109,.15)"
                        : app.status === "trial"
                          ? "rgba(203,145,47,.18)"
                          : "var(--n-hover)",
                    color:
                      app.status === "aktif"
                        ? "#0F7B6D"
                        : app.status === "trial"
                          ? "#CB912F"
                          : "var(--n-text-muted)",
                  }}
                >
                  {app.status}
                  {app.status === "trial" && app.expires_at
                    ? ` s.d. ${new Date(app.expires_at).toLocaleDateString("id-ID")}`
                    : ""}
                </span>
              )}
              {!app.status && <span />}
              {app.licensed ? (
                <Link
                  to={HOME_ROUTE[app.key] ?? "/"}
                  onClick={() => document.dispatchEvent(new CustomEvent("aeos:close-launcher"))}
                  className="font-medium hover:underline"
                  style={{ color: "#2383E2" }}
                >
                  Buka →
                </Link>
              ) : (
                <span className="text-[10.5px]" style={{ color: "var(--n-text-muted)" }} title={`Butuh: ${app.depends_on.join(", ")}`}>
                  {app.depends_on.length > 0 ? `butuh ${app.depends_on.length} app` : ""}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
