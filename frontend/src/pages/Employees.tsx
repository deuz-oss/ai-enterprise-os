import { ComplianceDigestCard } from "../components/ComplianceDigest";
import { useMe } from "../api/auth";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { UrlFilterBar } from "../components/UrlFilterBar";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EMPLOYEE_LOOKUP_LIMIT, useEmployeeLookup } from "../api/employees";
import { api, downloadFile, formatDate } from "../api/client";
import { Clock, Lock, Sparkles, Users as UsersIcon } from "lucide-react";
import {
  type Column,
  DataTable,
  HeaderCanvas,
  KpiCard,
  PeriodPicker,
  type PillTab,
  PillTabs,
  PreflightAlert,
  StatusPill,
} from "../components/ui";

export interface EmployeeRow {
  id: string;
  employee_no: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  birthdate: string | null;
  birthplace: string | null;
  gender: string | null;
  kk_no: string | null;
  religion: string | null;
  blood_type: string | null;
  education: string | null;
  current_position: string | null;
  bank_name: string | null;
  bank_account: string | null;
  bank_code: string | null;
  bank_account_verified: boolean;
  bank_account_verified_name: string | null;
  bank_account_verified_at: string | null;
  ktp_no: string | null;
  npwp_no: string | null;
  join_date: string | null;
  status: string;
  marital_status: string | null;
  dependents: number;
  base_salary: number;
  user_id: string | null;
  bpjs_kesehatan_no: string | null;
  bpjs_ketenagakerjaan_no: string | null;
  bpjs_kesehatan_status: string | null;
  bpjs_ketenagakerjaan_status: string | null;
  bpjs_kesehatan_valid_until: string | null;
  bpjs_ketenagakerjaan_valid_until: string | null;
  bpjs_kesehatan_card_key: string | null;
  bpjs_ketenagakerjaan_card_key: string | null;
  grade: string | null;
  level: string | null;
  division: string | null;
  position: string | null;
  citizen_address: Record<string, string>;
  residential_address: Record<string, string>;
  payroll_locked: boolean;
  payroll_locked_at: string | null;
  referral_code: string | null;
  site_id: string | null;
  shift_start_time: string | null;
  shift_end_time: string | null;
  placement_client_id: string | null;
  placement_client_name: string | null;
  placement_job_order_id: string | null;
  placement_job_title: string | null;
  ptkp_label: string | null;
}

interface LeaveRequestRow {
  id: string;
  employee_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: string;
  decision_note: string | null;
  file_name: string | null;
}

interface AttendanceCorrectionRow {
  id: string;
  employee_id: string;
  year: number;
  month: number;
  requested_present_days: number;
  requested_overtime_hours: number;
  reason: string | null;
  status: string;
  decision_note: string | null;
}

interface OvertimeRequestRow {
  id: string;
  employee_id: string;
  date: string;
  requested_hours: number;
  reason: string | null;
  status: string;
  decision_note: string | null;
}

const LEAVE_TYPE_LABELS: Record<string, string> = {
  cuti_tahunan: "Cuti Tahunan",
  izin: "Izin",
  sakit: "Sakit",
  cuti_tak_berbayar: "Cuti Tak Berbayar",
};

const LEAVE_STATUS_BADGES: Record<string, string> = {
  menunggu: "pill p-yellow",
  disetujui: "pill p-green",
  ditolak: "pill p-red",
  dibatalkan: "pill p-gray",
};

interface ExpiringContract {
  contract_id: string;
  contract_no: string;
  employee_id: string;
  employee_name: string;
  end_date: string;
  days_left: number;
}

interface IndexedContract {
  contract_id: string;
  file_name: string | null;
  employee_name: string;
  chunks: number;
}

interface AskResult {
  answer: string;
  sources: {
    contract_id: string;
    employee_name: string | null;
    contract_no: string | null;
    score: number;
    snippet: string;
  }[];
}

export default function Employees() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [askResult, setAskResult] = useState<AskResult | null>(null);
  const [exportPeriod, setExportPeriod] = useState({
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
  });
  // Tab/Pill filter (§1.5) atas status -- backend belum expose param filter
  // ini, jadi difilter+dipaginasi di klien dari `employeesLookup` (endpoint
  // yang sama, sudah dipakai widget lain untuk lookup nama lintas-halaman).
  const [statusTab, setStatusTab] = useState("");
  const [search, setSearch] = useState("");
  // Filter dari URL (⌘K "Tampilkan daftar: …", AI opportunity #5): status, q,
  // client (id klien placement), contract_days (kontrak berakhir ≤ N hari).
  const [searchParams] = useSearchParams();
  const urlClient = searchParams.get("client") ?? "";
  const urlContractDays = Number(searchParams.get("contract_days")) || 0;
  useEffect(() => {
    setStatusTab(searchParams.get("status") ?? "");
    setSearch(searchParams.get("q") ?? "");
  }, [searchParams]);
  const { data: endingContracts } = useQuery({
    queryKey: ["contracts-expiring", urlContractDays],
    queryFn: () =>
      api.get<ExpiringContract[]>(`/employees/contracts/expiring?within_days=${urlContractDays}`),
    enabled: urlContractDays > 0,
  });
  const employeesQuery = useEmployeeLookup<EmployeeRow>();
  const {
    data: employeesLookup,
    total: employeesLookupTotal,
    truncated: employeesTruncated,
  } = employeesQuery;
  const allEmployees = useMemo(() => employeesLookup ?? [], [employeesLookup]);
  const filteredEmployees = useMemo(() => {
    const q = search.trim().toLowerCase();
    const endingIds = urlContractDays ? new Set((endingContracts ?? []).map((c) => c.employee_id)) : null;
    return allEmployees.filter(
      (e) =>
        (!statusTab || e.status === statusTab) &&
        (!urlClient || e.placement_client_id === urlClient) &&
        (!endingIds || endingIds.has(e.id)) &&
        (!q || [e.full_name, e.employee_no, e.phone].some((v) => v?.toLowerCase().includes(q)))
    );
  }, [allEmployees, statusTab, search, urlClient, urlContractDays, endingContracts]);
  const urlFilterLabels = [
    urlClient &&
      `Klien: ${allEmployees.find((e) => e.placement_client_id === urlClient)?.placement_client_name ?? "terpilih"}`,
    urlContractDays && `Kontrak berakhir ≤ ${urlContractDays} hari`,
  ].filter((l): l is string => Boolean(l));
  const employeeColumns: Column<EmployeeRow>[] = [
    {
      key: "employee_no",
      header: "No. Induk",
      className: "font-mono text-xs",
      cell: (e) => e.employee_no,
      sortValue: (e) => e.employee_no,
    },
    {
      key: "name",
      header: "Nama",
      sortValue: (e) => e.full_name,
      cell: (e) => (
        <div className="flex items-center gap-2">
          <span
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-[var(--accent-contrast)]"
            style={{ backgroundColor: "var(--accent)" }}
            aria-hidden="true"
          >
            {e.full_name
              .split(" ")
              .map((w) => w[0])
              .slice(0, 2)
              .join("")
              .toUpperCase()}
          </span>
          <span className="font-medium">{e.full_name}</span>
        </div>
      ),
    },
    { key: "phone", header: "Telepon", cell: (e) => e.phone ?? "-" },
    {
      key: "join_date",
      header: "Masuk",
      cell: (e) => <span className="whitespace-nowrap">{formatDate(e.join_date)}</span>,
      sortValue: (e) => e.join_date,
    },
    {
      key: "status",
      header: "Status",
      cell: (e) => <StatusPill domain="employee" status={e.status} />,
      sortValue: (e) => e.status,
    },
  ];
  const statusTabs: PillTab[] = [
    { key: "", label: "Semua", count: allEmployees.length },
    { key: "aktif", label: "Aktif", count: allEmployees.filter((e) => e.status === "aktif").length },
    { key: "resign", label: "Resign", count: allEmployees.filter((e) => e.status === "resign").length },
  ];
  const activeCount = allEmployees.filter((e) => e.status === "aktif").length;
  const payrollLockedCount = allEmployees.filter((e) => e.payroll_locked).length;
  // Fase 23: Ops sekarang boleh buka halaman ini (dibatasi ke karyawan
  // eksternal, lihat backend), tapi endpoint HR administratif lain di bawah
  // (kontrak, dokumen, BPJS, asuransi, cuti, TTE) masih 403 untuk role ini --
  // guard query + JSX-nya lewat `isOpsOnly` biar tidak menampilkan section
  // yang pasti gagal.
  const { data: me } = useMe();
  const isOpsOnly = me?.role === "operations";
  const { data: expiring } = useQuery({
    queryKey: ["contracts-expiring"],
    queryFn: () =>
      api.get<ExpiringContract[]>("/employees/contracts/expiring?within_days=30"),
    enabled: !isOpsOnly,
  });
  const { data: indexed } = useQuery({
    queryKey: ["ai-indexed"],
    queryFn: () => api.get<IndexedContract[]>("/ai/contracts/indexed"),
    enabled: !isOpsOnly,
  });
  const { data: leaveRequests } = useQuery({
    queryKey: ["leave-requests"],
    queryFn: () => api.get<LeaveRequestRow[]>("/employees/leave-requests"),
    enabled: !isOpsOnly,
  });
  const { data: attendanceCorrections } = useQuery({
    queryKey: ["attendance-corrections"],
    queryFn: () => api.get<AttendanceCorrectionRow[]>("/employees/attendance-corrections"),
    enabled: !isOpsOnly,
  });
  const { data: overtimeRequests } = useQuery({
    queryKey: ["overtime-requests"],
    queryFn: () => api.get<OvertimeRequestRow[]>("/employees/overtime-requests"),
    enabled: !isOpsOnly,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["employees-lookup"] });
    qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
    qc.invalidateQueries({ queryKey: ["compliance-digest"] });
  };

  const createEmployee = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/employees", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const askAi = useMutation({
    mutationFn: (body: { question: string; employee_id: string | null }) =>
      api.post<AskResult>("/ai/contracts/ask", body),
    onSuccess: (data) => setAskResult(data),
  });

  const decideLeave = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      api.patch(`/employees/leave-requests/${id}/decision`, {
        approved,
        note: null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leave-requests"] }),
  });

  const decideCorrection = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      api.patch(`/employees/attendance-corrections/${id}/decision`, {
        approved,
        note: null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance-corrections"] }),
  });

  const decideOvertime = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      api.patch(`/employees/overtime-requests/${id}/decision`, {
        approved,
        note: null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["overtime-requests"] }),
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createEmployee.mutate({
      full_name: form.get("full_name"),
      phone: form.get("phone") || null,
      ktp_no: form.get("ktp_no") || null,
      npwp_no: form.get("npwp_no") || null,
      join_date: form.get("join_date") || null,
      jkk_risk_category: Number(form.get("jkk_risk_category")) || null,
    });
  }

  // ---------- Tabel persetujuan (DataTable) ----------
  // Default: "menunggu" di atas -- itu yang perlu diproses HR.
  const employeeName = (id: string) => employeesLookup?.find((e) => e.id === id)?.full_name ?? "-";
  const statusOrder = (status: string) => (status === "menunggu" ? 0 : 1);
  function decisionButtons(
    decide: { mutate: (v: { id: string; approved: boolean }) => void; isPending: boolean },
    id: string
  ) {
    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <button
          onClick={() => decide.mutate({ id, approved: true })}
          disabled={decide.isPending}
          className="text-sm font-medium text-emerald-700 hover:text-emerald-800 dark:text-emerald-400"
        >
          Setujui
        </button>
        <button
          onClick={() => decide.mutate({ id, approved: false })}
          disabled={decide.isPending}
          className="text-sm font-medium text-rose-700 hover:text-rose-800 dark:text-rose-400"
        >
          Tolak
        </button>
      </span>
    );
  }
  const statusBadge = (status: string) => <span className={`badge ${LEAVE_STATUS_BADGES[status] ?? ""}`}>{status}</span>;

  const correctionColumns: Column<AttendanceCorrectionRow>[] = [
    {
      key: "name",
      header: "Karyawan",
      className: "font-medium",
      cell: (c) => employeeName(c.employee_id),
      sortValue: (c) => employeeName(c.employee_id),
    },
    {
      key: "period",
      header: "Periode",
      cell: (c) => `${String(c.month).padStart(2, "0")}/${c.year}`,
      sortValue: (c) => c.year * 100 + c.month,
    },
    {
      key: "usulan",
      header: "Usulan",
      cell: (c) => `${c.requested_present_days} hari · ${c.requested_overtime_hours} jam lembur`,
    },
    { key: "reason", header: "Alasan", cell: (c) => c.reason ?? "-" },
    { key: "status", header: "Status", cell: (c) => statusBadge(c.status), sortValue: (c) => statusOrder(c.status) },
    {
      key: "decision",
      header: "Keputusan",
      className: "whitespace-nowrap",
      cell: (c) => (c.status === "menunggu" ? decisionButtons(decideCorrection, c.id) : (c.decision_note ?? "-")),
    },
  ];

  const overtimeColumns: Column<OvertimeRequestRow>[] = [
    {
      key: "name",
      header: "Karyawan",
      className: "font-medium",
      cell: (o) => employeeName(o.employee_id),
      sortValue: (o) => employeeName(o.employee_id),
    },
    {
      key: "date",
      header: "Tanggal",
      className: "whitespace-nowrap",
      cell: (o) => formatDate(o.date),
      sortValue: (o) => o.date,
    },
    {
      key: "hours",
      header: "Jam",
      numeric: true,
      cell: (o) => `${o.requested_hours} jam`,
      sortValue: (o) => o.requested_hours,
    },
    { key: "reason", header: "Alasan", cell: (o) => o.reason ?? "-" },
    { key: "status", header: "Status", cell: (o) => statusBadge(o.status), sortValue: (o) => statusOrder(o.status) },
    {
      key: "decision",
      header: "Keputusan",
      className: "whitespace-nowrap",
      cell: (o) => (o.status === "menunggu" ? decisionButtons(decideOvertime, o.id) : (o.decision_note ?? "-")),
    },
  ];

  const leaveColumns: Column<LeaveRequestRow>[] = [
    {
      key: "name",
      header: "Karyawan",
      className: "font-medium",
      cell: (lv) => employeeName(lv.employee_id),
      sortValue: (lv) => employeeName(lv.employee_id),
    },
    { key: "type", header: "Jenis", cell: (lv) => LEAVE_TYPE_LABELS[lv.leave_type] ?? lv.leave_type },
    {
      key: "date",
      header: "Tanggal",
      className: "whitespace-nowrap",
      cell: (lv) => `${formatDate(lv.start_date)} s.d. ${formatDate(lv.end_date)}`,
      sortValue: (lv) => lv.start_date,
    },
    { key: "reason", header: "Alasan", cell: (lv) => lv.reason ?? "-" },
    { key: "status", header: "Status", cell: (lv) => statusBadge(lv.status), sortValue: (lv) => statusOrder(lv.status) },
    {
      key: "decision",
      header: "Keputusan",
      className: "whitespace-nowrap",
      cell: (lv) => (
        <span className="inline-flex flex-wrap items-center gap-2">
          {lv.file_name && (
            <button
              onClick={async () => {
                const { url } = await api.get<{ url: string }>(`/employees/leave-requests/${lv.id}/attachment/download-url`);
                window.open(url, "_blank");
              }}
              className="text-xs font-medium hover:opacity-80"
              style={{ color: "var(--accent)" }}
              title={lv.file_name}
            >
              Lampiran
            </button>
          )}
          {lv.status === "menunggu"
            ? decisionButtons(decideLeave, lv.id)
            : !lv.file_name
              ? (lv.decision_note ?? "-")
              : null}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <HeaderCanvas
        name={me?.full_name?.split(" ")[0]}
        headline="Karyawan"
        subtext={`${allEmployees.length} karyawan terdaftar · ${activeCount} aktif`}
        showRangePicker={false}
        actions={
          <button className="btn" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Tutup" : "+ Karyawan Baru"}
          </button>
        }
      />

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input name="full_name" required placeholder="Nama lengkap *" className="input" />
          <input name="phone" placeholder="Telepon" className="input" />
          <input name="join_date" type="date" placeholder="Tanggal masuk" className="input" />
          <input name="ktp_no" placeholder="No. KTP" className="input" />
          <input name="npwp_no" placeholder="No. NPWP" className="input" />
          <select name="jkk_risk_category" defaultValue="" className="input">
            <option value="">Kelas risiko JKK (default II)</option>
            {[1, 2, 3, 4, 5].map((k) => (
              <option key={k} value={k}>
                Kelas {["I", "II", "III", "IV", "V"][k - 1]}
              </option>
            ))}
          </select>
          <p className="self-center text-xs" style={{ color: "var(--text-muted)" }}>
            Nomor induk karyawan dibuat otomatis bila dikosongkan.
          </p>
          <button type="submit" disabled={createEmployee.isPending} className="btn sm:col-span-3">
            Simpan Karyawan
          </button>
        </form>
      )}

      {/* Digest kepatuhan (AI #4) menggantikan callout lama "Reminder Kontrak
          ≤30 hari": isinya superset (+ kontrak lewat & BPJS belum lengkap). */}
      <ComplianceDigestCard />

      {!isOpsOnly && (
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {/* Penanda ikon Sparkles disamakan dengan FAB "Tanya AEOS AI" &
              "AI Executive Digest" Dashboard.tsx (DES-002, audit desain
              2026-09-15) -- supaya semua titik masuk AI kebaca sebagai satu
              kapabilitas yang sama, bukan fitur-fitur lepas tak berhubungan. */}
          <h2 className="flex items-center gap-1.5 font-semibold" style={{ color: "var(--text)" }}>
            <Sparkles className="h-4 w-4 shrink-0" style={{ color: "var(--accent)" }} />
            Tanya Kontrak (AI)
          </h2>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {indexed?.length
              ? `${indexed.length} kontrak terindeks`
              : "Belum ada kontrak terindeks — klik \"Index AI\" pada kontrak"}
          </span>
        </div>
        <form
          className="mt-3 flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            const q = String(form.get("question") ?? "").trim();
            if (q) askAi.mutate({ question: q, employee_id: null });
          }}
        >
          <input
            name="question"
            required
            placeholder="Tanyakan apa pun tentang kontrak yang sudah diindeks"
            className="input flex-1"
          />
          <button className="btn" disabled={askAi.isPending || !indexed?.length}>
            {askAi.isPending ? "AI mencari..." : "Tanya"}
          </button>
        </form>
        {askAi.error && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">{(askAi.error as Error).message}</p>
        )}
        {askResult && (
          <div className="mt-3 rounded-lg border p-4" style={{ backgroundColor: "var(--accent-tint)", borderColor: "var(--border)" }}>
            <p className="text-sm" style={{ color: "var(--text)" }}>{askResult.answer}</p>
            {askResult.sources.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs" style={{ color: "var(--text-muted)" }}>
                {askResult.sources.map((s, i) => (
                  <li key={i}>
                    Sumber: {s.employee_name} — {s.contract_no} (skor{" "}
                    {(s.score * 100).toFixed(0)}%): “{s.snippet.slice(0, 120)}
                    {s.snippet.length > 120 ? "..." : ""}”
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      )}

      {!isOpsOnly && (attendanceCorrections ?? []).length > 0 && (
        <div className="card overflow-x-auto p-0">
          <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Koreksi Absensi (Portal)</h2>
          </div>
          <div className="px-4 pb-4 sm:p-0">
            <DataTable
              plain
              label="Koreksi absensi dari portal"
              rows={attendanceCorrections}
              columns={correctionColumns}
              rowKey={(r) => r.id}
              defaultSort={{ key: "status", dir: "asc" }}
              emptyTitle="Tidak ada pengajuan."
            />
          </div>
        </div>
      )}

      {!isOpsOnly && (overtimeRequests ?? []).length > 0 && (
        <div className="card overflow-x-auto p-0">
          <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Pengajuan Lembur</h2>
          </div>
          <div className="px-4 pb-4 sm:p-0">
            <DataTable
              plain
              label="Pengajuan lembur"
              rows={overtimeRequests}
              columns={overtimeColumns}
              rowKey={(r) => r.id}
              defaultSort={{ key: "status", dir: "asc" }}
              emptyTitle="Tidak ada pengajuan."
            />
          </div>
        </div>
      )}

      {(leaveRequests ?? []).length > 0 && (
        <div className="card overflow-x-auto p-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4" style={{ borderColor: "var(--border)" }}>
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Pengajuan Cuti / Izin</h2>
            <div className="flex flex-wrap items-center gap-2">
              <PeriodPicker value={exportPeriod} onChange={setExportPeriod} label="periode laporan" />
              <button
                className="btn-secondary text-xs"
                onClick={() =>
                  downloadFile(`/employees/reports/leave?year=${exportPeriod.year}`)
                }
              >
                Unduh CSV Cuti
              </button>
              <button
                className="btn-secondary text-xs"
                onClick={() =>
                  downloadFile(
                    `/employees/reports/attendance?year=${exportPeriod.year}&month=${exportPeriod.month}`
                  )
                }
              >
                Unduh CSV Absensi
              </button>
            </div>
          </div>
          <div className="px-4 pb-4 sm:p-0">
            <DataTable
              plain
              label="Pengajuan cuti dan izin"
              rows={leaveRequests}
              columns={leaveColumns}
              rowKey={(r) => r.id}
              defaultSort={{ key: "status", dir: "asc" }}
              emptyTitle="Tidak ada pengajuan."
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Karyawan" value={allEmployees.length} icon={UsersIcon} iconTone="info" />
        <KpiCard
          label="Karyawan Aktif"
          value={activeCount}
          icon={UsersIcon}
          iconTone="success"
          context={`dari ${allEmployees.length} terdaftar`}
        />
        <KpiCard
          label="Kontrak Akan Berakhir"
          value={(expiring ?? []).length}
          icon={Clock}
          iconTone="warning"
          context="Dalam 30 hari ke depan"
          badge={(expiring ?? []).length > 0 ? { label: "Perlu Tindak Lanjut", tone: "warning" } : undefined}
        />
        <KpiCard label="Payroll Terkunci" value={payrollLockedCount} icon={Lock} iconTone="neutral" />
      </div>

      {employeesTruncated && (
        <PreflightAlert
          title="Data karyawan terpotong"
          summary={`Hanya ${allEmployees.length} dari ${employeesLookupTotal} karyawan yang termuat (batas ${EMPLOYEE_LOOKUP_LIMIT}). Hitungan, tab status, dan daftar di bawah belum mencakup semua karyawan.`}
        />
      )}

      <UrlFilterBar labels={urlFilterLabels} />

      <div className="flex flex-wrap items-center gap-3">
        <PillTabs tabs={statusTabs} value={statusTab} onChange={setStatusTab} />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari nama, no. induk, atau telepon…"
          aria-label="Cari karyawan"
          className="input w-full sm:ml-auto sm:w-72"
        />
      </div>

      <DataTable
        label="Daftar karyawan"
        rows={filteredEmployees}
        columns={employeeColumns}
        rowKey={(e) => e.id}
        query={employeesQuery}
        onRowClick={(e) => navigate(`/employees/${e.id}`)}
        defaultSort={{ key: "employee_no", dir: "desc" }}
        pageSize={50}
        emptyTitle={
          allEmployees.length === 0
            ? "Belum ada karyawan."
            : search
              ? "Tidak ada karyawan yang cocok dengan pencarian."
              : "Tidak ada karyawan untuk status ini."
        }
      />

    </div>
  );
}
