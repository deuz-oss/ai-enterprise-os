import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  FileText,
  Scale,
  Shield,
  ShieldAlert,
  Users,
} from "lucide-react";
import { api } from "../api/client";
import { CalloutBlock, IconBadge, PageHeader, RowFrame, SeeAllLink } from "../components/workspace";

interface Overview {
  ai_insight: { hint: string };
}

interface AuditItem {
  id: string;
  tenant_id: string | null;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  object_key: string | null;
  ip: string | null;
  created_at: string;
  detail: Record<string, unknown> | null;
}

interface UserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  business_dev: "Business Dev",
  recruiter: "Recruiter",
  hr: "HR",
  operations: "Operations",
  finance: "Finance",
  management: "Management",
  karyawan: "Karyawan (Portal Saya)",
  platform_admin: "Platform Admin",
};

const ROLE_CAPTIONS: Record<string, string> = {
  admin: "Akses penuh tenant",
  business_dev: "Sales & klien",
  recruiter: "Rekrutmen & talent",
  hr: "Workforce & rekrutmen",
  operations: "Operasional harian",
  finance: "Keuangan & payroll",
  management: "Operasional & approval",
  karyawan: "Portal Saya (ESS)",
  platform_admin: "Manajemen platform",
};

const ROLE_DOT: Record<string, string> = {
  admin: "var(--accent)",
  management: "#10b981",
  hr: "#8b5cf6",
  karyawan: "#9f9f9f",
};

const ROLE_ORDER = ["admin", "management", "hr", "finance", "operations", "recruiter", "business_dev", "karyawan"];

const ACTION_LABELS: Record<string, string> = {
  "auth.login": "login berhasil",
  "auth.login_failed": "login gagal",
  "auth.login_ratelimited": "login diblokir (rate limit)",
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/[._]/g, " ");
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "baru saja";
  if (min < 60) return `${min} menit lalu`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} jam lalu`;
  return `${Math.floor(hr / 24)} hari lalu`;
}

export default function GovernCloudOverview() {
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
  });

  const canSeeAudit = me.data?.role === "admin" || me.data?.role === "management";
  const canSeeUsers = me.data?.role === "admin";

  const overview = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });
  const auditLogs = useQuery({
    queryKey: ["audit-logs-govern"],
    queryFn: () => api.get<{ total: number; items: AuditItem[] }>("/audit/logs?limit=500"),
    enabled: canSeeAudit,
    retry: false,
  });
  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserRow[]>("/auth/users"),
    enabled: canSeeUsers,
    retry: false,
  });

  const items = auditLogs.data?.items ?? [];
  const userById = (id: string | null) => users.data?.find((u) => u.id === id);
  const actorName = (userId: string | null) => {
    if (!userId) return "Sistem";
    return userById(userId)?.full_name ?? "Pengguna";
  };

  const today = new Date();
  const todayCount = useMemo(
    () =>
      items.filter((i) => {
        const d = new Date(i.created_at);
        return (
          d.getFullYear() === today.getFullYear() &&
          d.getMonth() === today.getMonth() &&
          d.getDate() === today.getDate()
        );
      }).length,
    [items],
  );

  const loginIssues = useMemo(
    () => items.filter((i) => i.action === "auth.login_failed" || i.action === "auth.login_ratelimited"),
    [items],
  );

  const activeUsers = (users.data ?? []).filter((u) => u.is_active);
  const roleGroups = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const u of users.data ?? []) {
      counts[u.role] = (counts[u.role] ?? 0) + 1;
    }
    return ROLE_ORDER.filter((r) => counts[r] > 0).map((r) => ({ role: r, count: counts[r] }));
  }, [users.data]);

  const recentAudit = items.slice(0, 5);
  const recentActivity = items.slice(0, 3);
  const recentIssues = loginIssues.slice(0, 3);
  const recentUsers = (users.data ?? []).slice(0, 3);

  const entityLabel = (i: AuditItem) => {
    if (i.entity_type && i.entity_id) return `${i.entity_type} · ${i.entity_id.slice(0, 8)}`;
    if (i.entity_type) return i.entity_type;
    return "-";
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          icon={Scale}
          title="Govern Cloud"
          subtitle={`${auditLogs.data?.total ?? 0} audit log · ${activeUsers.length} user aktif · ${roleGroups.length} roles.`}
        />
        <Link to="/users" className="btn shrink-0">
          + Tambah User
        </Link>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Audit Logs</span>
            <IconBadge icon={FileText} tone="accent" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>
            {auditLogs.data?.total ?? "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>{todayCount} hari ini</p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Active Users</span>
            <IconBadge icon={Users} tone="green" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>
            {canSeeUsers ? activeUsers.length : "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>{roleGroups.length} roles · RBAC</p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Login Issues</span>
            <IconBadge icon={ShieldAlert} tone="orange" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>
            {canSeeAudit ? loginIssues.length : "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
            {loginIssues.length > 0 ? "perlu review" : "aman"}
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Roles Aktif</span>
            <IconBadge icon={Shield} tone="violet" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--text)" }}>
            {canSeeUsers ? roleGroups.length : "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-muted)" }}>dari 9 role tersedia</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex items-center lg:col-span-2">
          {overview.data?.ai_insight.hint && (
            <CalloutBlock icon={Scale} tone="info">
              {overview.data.ai_insight.hint}
            </CalloutBlock>
          )}
        </div>

        {/* RBAC & Roles */}
        {canSeeUsers && (
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Shield} tone="accent" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>RBAC & Roles</h2>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{roleGroups.length} roles terpakai</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {roleGroups.map(({ role, count }) => (
                <RowFrame key={role}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--text)" }}>
                      {ROLE_LABELS[role] ?? role}
                    </span>
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: ROLE_DOT[role] ?? "#9f9f9f" }}
                    />
                  </div>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
                    {count} user · {ROLE_CAPTIONS[role] ?? "-"}
                  </p>
                </RowFrame>
              ))}
              {roleGroups.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada user.</p>
              )}
            </div>
            <SeeAllLink to="/users">Kelola role →</SeeAllLink>
          </div>
        )}
      </div>

      {canSeeAudit && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Audit Trail */}
          <div className="card space-y-2 lg:col-span-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={FileText} tone="accent" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Audit Trail</h2>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Siapa, apa, kapan — immutable</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {recentAudit.map((i) => (
                <RowFrame key={i.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--text)" }}>
                      {actionLabel(i.action)}
                    </span>
                    <span className="shrink-0 font-mono text-[10px]" style={{ color: "var(--text-muted)" }}>
                      {new Date(i.created_at).toLocaleString("id-ID")}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
                    {canSeeUsers ? actorName(i.user_id) : "Pengguna"} · {entityLabel(i)}
                  </p>
                </RowFrame>
              ))}
              {recentAudit.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada aktivitas tercatat.</p>
              )}
            </div>
            <SeeAllLink to="/audit">Lihat semua audit log →</SeeAllLink>
          </div>

          {/* Compliance Issues */}
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={ShieldAlert} tone="orange" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Compliance Issues</h2>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{loginIssues.length} tercatat</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {recentIssues.map((i) => (
                <RowFrame key={i.id}>
                  <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
                    {actionLabel(i.action)} — {canSeeUsers ? actorName(i.user_id) : "Pengguna"}
                  </p>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
                    {new Date(i.created_at).toLocaleString("id-ID")}
                    {i.ip ? ` · ${i.ip}` : ""}
                  </p>
                </RowFrame>
              ))}
              {recentIssues.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Tidak ada isu login.</p>
              )}
            </div>
            <SeeAllLink to="/audit">Review →</SeeAllLink>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* User Management */}
        {canSeeUsers && (
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Users} tone="accent" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>User Management</h2>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>{users.data?.length ?? 0} users</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {recentUsers.map((u) => (
                <RowFrame key={u.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--text)" }}>
                      {u.full_name} — {ROLE_LABELS[u.role] ?? u.role}
                    </span>
                    <span className={`shrink-0 pill ${u.is_active ? "p-green" : "p-red"}`}>
                      {u.is_active ? "Aktif" : "Nonaktif"}
                    </span>
                  </div>
                  <p className="mt-0.5 truncate text-xs" style={{ color: "var(--text-muted)" }}>{u.email}</p>
                </RowFrame>
              ))}
              {recentUsers.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada user.</p>
              )}
            </div>
            <SeeAllLink to="/users">Kelola user →</SeeAllLink>
          </div>
        )}

        {/* Aktivitas terbaru */}
        {canSeeAudit && (
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Activity} tone="green" />
              <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Aktivitas Terbaru</h2>
            </div>
            <div className="space-y-1.5">
              {recentActivity.map((a) => (
                <RowFrame key={a.id}>
                  <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{actionLabel(a.action)}</p>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
                    oleh {canSeeUsers ? actorName(a.user_id) : "Pengguna"} · {timeAgo(a.created_at)}
                  </p>
                </RowFrame>
              ))}
              {recentActivity.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Belum ada aktivitas.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
