import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Clock,
  FileText,
  Heart,
  IdCard,
  ShieldCheck,
  Sparkles,
  Users,
  Wallet,
} from "lucide-react";
import { api } from "../api/client";
import { CalloutBlock, IconBadge, PageHeader, RowFrame, SeeAllLink } from "../components/notion";

interface Overview {
  people: {
    total_employees: number;
    active_employees: number;
    expiring_contracts_14d: number;
    bpjs_complete: number;
    insurance_complete: number;
  };
  ai_insight: { hint: string };
}

interface Employee {
  id: string;
  employee_no: string;
  full_name: string;
  join_date: string | null;
  status: string;
  employment_type: string;
}

interface ExpiringContract {
  contract_id: string;
  contract_no: string;
  employee_id: string;
  employee_name: string;
  employee_no: string;
  end_date: string;
  days_left: number;
}

interface EsignRequestItem {
  id: string;
  contract_id: string | null;
  placement_id: string | null;
  signer_name: string;
  status: string;
}

interface AttendanceRecord {
  id: string;
  employee_id: string;
  date: string;
  status: string;
}

interface ClientRow {
  id: string;
  name: string;
}

interface PayrollRun {
  id: string;
  year: number;
  month: number;
  run_type: string;
  client_id: string | null;
  status: string;
  finalized_at: string | null;
}

interface AuditItem {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
}

interface UserOption {
  id: string;
  full_name: string;
}

const EMPLOYEE_STATUS_PILL: Record<string, string> = {
  aktif: "pill p-green",
  resign: "pill p-gray",
};

const EMPLOYEE_STATUS_LABELS: Record<string, string> = {
  aktif: "Aktif",
  resign: "Resign",
};

const EMPLOYMENT_TYPE_LABELS: Record<string, string> = {
  internal: "Internal",
  eksternal: "Outsourcing",
};

const ATTENDANCE_STATUS_LABELS: Record<string, string> = {
  hadir: "Hadir",
  terlambat: "Terlambat",
  izin: "Izin",
  sakit: "Sakit",
  cuti: "Cuti",
  alpa: "Alpa",
  libur: "Libur",
  dinas_luar: "Dinas Luar",
};

const ESIGN_STATUS_LABELS: Record<string, string> = {
  terkirim: "Terkirim",
  dilihat: "Dilihat",
  selesai: "Ditandatangani",
  ditolak: "Ditolak",
  kedaluwarsa: "Kedaluwarsa",
  gagal: "Gagal",
};

const ESIGN_STATUS_PILL: Record<string, string> = {
  terkirim: "pill p-yellow",
  dilihat: "pill p-blue",
  selesai: "pill p-green",
  ditolak: "pill p-red",
  kedaluwarsa: "pill p-gray",
  gagal: "pill p-red",
};

const PAYROLL_RUN_TYPE_LABELS: Record<string, string> = {
  internal: "Internal",
  proyek: "Proyek (per klien)",
};

const PAYROLL_RUN_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted_to_client: "Menunggu klien",
  client_rejected: "Ditolak klien",
  client_approved: "Disetujui klien",
  finance_processing: "Diproses finance",
  final: "Final",
};

const PAYROLL_RUN_STATUS_PILL: Record<string, string> = {
  draft: "pill p-gray",
  submitted_to_client: "pill p-yellow",
  client_rejected: "pill p-red",
  client_approved: "pill p-blue",
  finance_processing: "pill p-violet",
  final: "pill p-green",
};

function actorName(users: UserOption[] | undefined, userId: string | null): string {
  if (!userId) return "Sistem";
  return users?.find((u) => u.id === userId)?.full_name ?? "Pengguna";
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

const ACTION_LABELS: Record<string, string> = {
  "contract.upload": "unggah kontrak",
  "employee.insurance_created": "tambah polis asuransi",
  "employee.bpjs_card_uploaded": "unggah kartu BPJS",
  "ess.account_linked": "tautkan akun ESS",
  "ess.account_unlinked": "lepas tautan akun ESS",
  "attendance.summary_validated": "validasi absensi",
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/[._]/g, " ");
}

export default function WorkforceCloudOverview() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
  });

  const overview = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });
  const employees = useQuery({
    queryKey: ["employees"],
    queryFn: () => api.get<Employee[]>("/employees"),
  });
  const contractsExpiring = useQuery({
    queryKey: ["contracts-expiring"],
    queryFn: () => api.get<ExpiringContract[]>("/employees/contracts/expiring?within_days=30"),
  });
  const esignRequests = useQuery({
    queryKey: ["esign-requests"],
    queryFn: () => api.get<EsignRequestItem[]>("/esign/requests"),
  });
  const attendanceRecords = useQuery({
    queryKey: ["attendance-records", `${year}-${month}`],
    queryFn: () => api.get<AttendanceRecord[]>(`/attendance/records?year=${year}&month=${month}`),
  });
  const clients = useQuery({ queryKey: ["clients"], queryFn: () => api.get<ClientRow[]>("/clients") });
  const payrollRuns = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get<PayrollRun[]>("/payroll/runs"),
  });
  const users = useQuery({
    queryKey: ["users-for-interview"],
    queryFn: () => api.get<UserOption[]>("/auth/users"),
  });

  const canSeeActivity = me.data?.role === "admin" || me.data?.role === "management";
  const auditEmployee = useQuery({
    queryKey: ["audit-activity-wf", "employee"],
    queryFn: () => api.get<{ total: number; items: AuditItem[] }>("/audit/logs?entity_type=employee&limit=5"),
    enabled: canSeeActivity,
    retry: false,
  });
  const auditContract = useQuery({
    queryKey: ["audit-activity-wf", "employment_contract"],
    queryFn: () =>
      api.get<{ total: number; items: AuditItem[] }>("/audit/logs?entity_type=employment_contract&limit=5"),
    enabled: canSeeActivity,
    retry: false,
  });
  const auditAttendance = useQuery({
    queryKey: ["audit-activity-wf", "attendance_summary"],
    queryFn: () =>
      api.get<{ total: number; items: AuditItem[] }>("/audit/logs?entity_type=attendance_summary&limit=5"),
    enabled: canSeeActivity,
    retry: false,
  });
  const activityFeed = useMemo(() => {
    const merged = [
      ...(auditEmployee.data?.items ?? []),
      ...(auditContract.data?.items ?? []),
      ...(auditAttendance.data?.items ?? []),
    ];
    return merged
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 3);
  }, [auditEmployee.data, auditContract.data, auditAttendance.data]);

  const totalEmployees = employees.data?.length ?? 0;
  const internalCount = (employees.data ?? []).filter((e) => e.employment_type === "internal").length;
  const outsourcingCount = (employees.data ?? []).filter((e) => e.employment_type === "eksternal").length;

  const peopleTotal = overview.data?.people.total_employees ?? 0;
  const bpjsPct = peopleTotal > 0 ? Math.round(((overview.data?.people.bpjs_complete ?? 0) / peopleTotal) * 100) : 0;
  const insurancePct =
    peopleTotal > 0 ? Math.round(((overview.data?.people.insurance_complete ?? 0) / peopleTotal) * 100) : 0;

  const esignPending = (esignRequests.data ?? []).filter(
    (r) => r.contract_id && (r.status === "terkirim" || r.status === "dilihat"),
  );

  const attendanceCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of attendanceRecords.data ?? []) {
      counts[r.status] = (counts[r.status] ?? 0) + 1;
    }
    return counts;
  }, [attendanceRecords.data]);

  const currentRuns = (payrollRuns.data ?? []).filter((r) => r.year === year && r.month === month);
  const clientName = (id: string | null) => clients.data?.find((c) => c.id === id)?.name ?? "-";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          icon={IdCard}
          title="Workforce Cloud"
          subtitle={`${totalEmployees} karyawan · ${internalCount} internal + ${outsourcingCount} outsourcing · ${overview.data?.people.bpjs_complete ?? 0} BPJS aktif.`}
        />
        <Link to="/employees" className="btn shrink-0">
          + Tambah Karyawan
        </Link>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>Total Karyawan</span>
            <IconBadge icon={Users} tone="green" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {overview.data?.people.total_employees ?? "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--n-text-muted)" }}>
            {internalCount} internal · {outsourcingCount} outsourcing
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>BPJS Aktif</span>
            <IconBadge icon={ShieldCheck} tone="accent" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {overview.data?.people.bpjs_complete ?? "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--n-text-muted)" }}>{bpjsPct}%</p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>Asuransi</span>
            <IconBadge icon={Heart} tone="orange" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {overview.data?.people.insurance_complete ?? "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--n-text-muted)" }}>{insurancePct}%</p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>Kontrak Akan Berakhir</span>
            <IconBadge icon={AlertTriangle} tone="orange" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {contractsExpiring.data?.length ?? "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--n-text-muted)" }}>≤30 hari</p>
        </div>
      </div>

      {/* People & Compliance */}
      <div className="card space-y-3">
        <div className="flex items-center gap-2">
          <IconBadge icon={ShieldCheck} tone="accent" />
          <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>People & Compliance</h2>
        </div>
        <div>
          <div className="flex items-center justify-between text-xs font-medium" style={{ color: "var(--n-text)" }}>
            <span>BPJS Kesehatan & Ketenagakerjaan</span>
            <span>{overview.data?.people.bpjs_complete ?? 0}/{peopleTotal} · {bpjsPct}%</span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full" style={{ backgroundColor: "var(--n-hover)" }}>
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${bpjsPct}%` }} />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between text-xs font-medium" style={{ color: "var(--n-text)" }}>
            <span>Private Insurance (one-to-many)</span>
            <span>{overview.data?.people.insurance_complete ?? 0}/{peopleTotal} · {insurancePct}%</span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full" style={{ backgroundColor: "var(--n-hover)" }}>
            <div className="h-full rounded-full bg-amber-500" style={{ width: `${insurancePct}%` }} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {overview.data?.ai_insight.hint && (
            <CalloutBlock icon={Sparkles} tone="info">
              {overview.data.ai_insight.hint}
            </CalloutBlock>
          )}

          {/* Daftar Karyawan */}
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Users} tone="accent" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Daftar Karyawan</h2>
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>{totalEmployees} total</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {(employees.data ?? []).slice(0, 2).map((e) => (
                <RowFrame key={e.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>{e.full_name}</span>
                    <span className={`${EMPLOYEE_STATUS_PILL[e.status] ?? "pill p-gray"} shrink-0`}>
                      {EMPLOYEE_STATUS_LABELS[e.status] ?? e.status}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>
                    {EMPLOYMENT_TYPE_LABELS[e.employment_type] ?? e.employment_type}
                    {e.join_date ? ` · bergabung ${new Date(e.join_date).toLocaleDateString("id-ID")}` : ""}
                  </p>
                </RowFrame>
              ))}
              {(employees.data ?? []).length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada karyawan.</p>
              )}
            </div>
            <SeeAllLink to="/employees">Lihat semua karyawan →</SeeAllLink>
          </div>
        </div>

        <div className="space-y-4">
          {/* Expiry alert */}
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={AlertTriangle} tone="orange" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Expiry Alert</h2>
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Kontrak ≤30 hari</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {(contractsExpiring.data ?? []).slice(0, 3).map((c) => (
                <RowFrame key={c.contract_id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>{c.employee_name}</span>
                    <span className="shrink-0 text-xs" style={{ color: "var(--n-text-muted)" }}>
                      {c.days_left} hari
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>{c.contract_no}</p>
                </RowFrame>
              ))}
              {(contractsExpiring.data ?? []).length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Tidak ada kontrak akan berakhir.</p>
              )}
            </div>
            <SeeAllLink to="/employees">Lihat semua karyawan →</SeeAllLink>
          </div>

          {/* Dokumen - eSign pending */}
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={FileText} tone="violet" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Dokumen</h2>
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                  {esignPending.length} menunggu eSign
                </p>
              </div>
            </div>
            <div className="space-y-1.5">
              {esignPending.slice(0, 3).map((r) => (
                <RowFrame key={r.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>{r.signer_name}</span>
                    <span className={`shrink-0 text-[10px] ${ESIGN_STATUS_PILL[r.status] ?? "pill p-gray"}`}>
                      {ESIGN_STATUS_LABELS[r.status] ?? r.status}
                    </span>
                  </div>
                </RowFrame>
              ))}
              {esignPending.length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Tidak ada dokumen menunggu eSign.</p>
              )}
            </div>
            <SeeAllLink to="/employees">Kelola di Karyawan →</SeeAllLink>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Kehadiran */}
        <div className="card space-y-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={Clock} tone="accent" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Kehadiran</h2>
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Bulan ini</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.keys(ATTENDANCE_STATUS_LABELS).map((s) =>
              attendanceCounts[s] ? (
                <span key={s} className="pill p-gray">
                  {ATTENDANCE_STATUS_LABELS[s]}: {attendanceCounts[s]}
                </span>
              ) : null,
            )}
            {Object.keys(attendanceCounts).length === 0 && (
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada data absensi bulan ini.</p>
            )}
          </div>
          <SeeAllLink to="/attendance">Lihat semua →</SeeAllLink>
        </div>

        {/* Aktivitas terbaru */}
        {canSeeActivity && (
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Activity} tone="green" />
              <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Aktivitas Terbaru</h2>
            </div>
            <div className="space-y-1.5">
              {activityFeed.map((a) => (
                <RowFrame key={a.id}>
                  <p className="text-sm font-medium" style={{ color: "var(--n-text)" }}>{actionLabel(a.action)}</p>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>
                    oleh {actorName(users.data, a.user_id)} · {timeAgo(a.created_at)}
                  </p>
                </RowFrame>
              ))}
              {activityFeed.length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada aktivitas.</p>
              )}
            </div>
          </div>
        )}

        {/* Payroll run */}
        <div className="card space-y-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={Wallet} tone="green" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Payroll Run</h2>
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                {now.toLocaleDateString("id-ID", { month: "long", year: "numeric" })}
              </p>
            </div>
          </div>
          <div className="space-y-1.5">
            {currentRuns.map((r) => (
              <RowFrame key={r.id}>
                <div className="flex items-center justify-between text-sm">
                  <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>
                    {PAYROLL_RUN_TYPE_LABELS[r.run_type] ?? r.run_type}
                    {r.client_id ? ` · ${clientName(r.client_id)}` : ""}
                  </span>
                  <span className={`shrink-0 text-[10px] ${PAYROLL_RUN_STATUS_PILL[r.status] ?? "pill p-gray"}`}>
                    {PAYROLL_RUN_STATUS_LABELS[r.status] ?? r.status}
                  </span>
                </div>
              </RowFrame>
            ))}
            {currentRuns.length === 0 && (
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada payroll run bulan ini.</p>
            )}
          </div>
          <SeeAllLink to="/payroll">Kelola payroll →</SeeAllLink>
        </div>
      </div>
    </div>
  );
}
