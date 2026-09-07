import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile } from "../api/client";
import { Clock, IdCard, Lock, Users as UsersIcon } from "lucide-react";
import { CalloutBlock, PageHeader } from "../components/workspace";
import { KpiCard, PillTabs, type PillTab } from "../components/ui";
import { Pagination } from "../components/Pagination";

export interface EmployeeRow {
  id: string;
  employee_no: string;
  full_name: string;
  phone: string | null;
  ktp_no: string | null;
  npwp_no: string | null;
  join_date: string | null;
  status: string;
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
  emergency_contact_name: string | null;
  emergency_contact_relation: string | null;
  emergency_contact_phone: string | null;
  citizen_address: Record<string, string>;
  residential_address: Record<string, string>;
  payroll_locked: boolean;
  payroll_locked_at: string | null;
  referral_code: string | null;
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
  const [offset, setOffset] = useState(0);
  // Tab/Pill filter (§1.5) atas status -- backend belum expose param filter
  // ini, jadi difilter+dipaginasi di klien dari `employeesLookup` (endpoint
  // yang sama, sudah dipakai widget lain untuk lookup nama lintas-halaman).
  const [statusTab, setStatusTab] = useState("");
  const pageLimit = 50;
  const { data: employeesLookup } = useQuery({
    queryKey: ["employees-lookup"],
    queryFn: () => api.get<EmployeeRow[]>("/employees?limit=1000"),
  });
  const allEmployees = employeesLookup ?? [];
  const filteredEmployees = useMemo(
    () => allEmployees.filter((e) => !statusTab || e.status === statusTab),
    [allEmployees, statusTab]
  );
  const employees = filteredEmployees.slice(offset, offset + pageLimit);
  const employeesTotal = filteredEmployees.length;
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
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ role: string }>("/auth/me"),
  });
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

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["employees-lookup"] });
    qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader icon={IdCard} title="Karyawan" />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Karyawan Baru"}
        </button>
      </div>

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

      {(expiring ?? []).length > 0 && (
        <CalloutBlock tone="warning">
          <p className="font-medium">Reminder Kontrak ≤30 hari</p>
          <ul className="mt-1 list-inside list-disc text-xs">
            {expiring!.map((c) => (
              <li key={c.contract_id}>
                {c.employee_name} — kontrak {c.contract_no} berakhir {c.end_date} ({c.days_left} hari lagi)
              </li>
            ))}
          </ul>
        </CalloutBlock>
      )}

      {!isOpsOnly && (
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Tanya Kontrak (AI)</h2>
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
          <p className="mt-2 text-sm text-red-600">{(askAi.error as Error).message}</p>
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
          <table className="w-full">
            <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
              <tr>
                <th className="th">Karyawan</th>
                <th className="th">Periode</th>
                <th className="th">Usulan</th>
                <th className="th">Alasan</th>
                <th className="th">Status</th>
                <th className="th">Keputusan</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
              {(attendanceCorrections ?? []).map((c) => {
                const emp = employeesLookup?.find((e) => e.id === c.employee_id);
                return (
                  <tr key={c.id}>
                    <td className="td font-medium">{emp?.full_name ?? "-"}</td>
                    <td className="td">
                      {String(c.month).padStart(2, "0")}/{c.year}
                    </td>
                    <td className="td">
                      {c.requested_present_days} hari · {c.requested_overtime_hours} jam lembur
                    </td>
                    <td className="td">{c.reason ?? "-"}</td>
                    <td className="td">
                      <span
                        className={`badge ${LEAVE_STATUS_BADGES[c.status] ?? ""}`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="td whitespace-nowrap">
                      {c.status === "menunggu" ? (
                        <>
                          <button
                            onClick={() =>
                              decideCorrection.mutate({ id: c.id, approved: true })
                            }
                            disabled={decideCorrection.isPending}
                            className="text-sm font-medium text-emerald-600 hover:text-emerald-800"
                          >
                            Setujui
                          </button>
                          {" · "}
                          <button
                            onClick={() =>
                              decideCorrection.mutate({ id: c.id, approved: false })
                            }
                            disabled={decideCorrection.isPending}
                            className="text-sm font-medium text-rose-600 hover:text-rose-800"
                          >
                            Tolak
                          </button>
                        </>
                      ) : (
                        (c.decision_note ?? "-")
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {(leaveRequests ?? []).length > 0 && (
        <div className="card overflow-x-auto p-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4" style={{ borderColor: "var(--border)" }}>
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Pengajuan Cuti / Izin</h2>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="number"
                value={exportPeriod.month}
                min={1}
                max={12}
                onChange={(e) =>
                  setExportPeriod({ ...exportPeriod, month: Number(e.target.value) })
                }
                className="input w-16"
                title="Bulan (untuk rekap absensi)"
              />
              <input
                type="number"
                value={exportPeriod.year}
                onChange={(e) =>
                  setExportPeriod({ ...exportPeriod, year: Number(e.target.value) })
                }
                className="input w-20"
                title="Tahun"
              />
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
          <table className="w-full">
            <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
              <tr>
                <th className="th">Karyawan</th>
                <th className="th">Jenis</th>
                <th className="th">Tanggal</th>
                <th className="th">Alasan</th>
                <th className="th">Status</th>
                <th className="th">Keputusan</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
              {(leaveRequests ?? []).map((lv) => {
                const emp = employeesLookup?.find((e) => e.id === lv.employee_id);
                return (
                  <tr key={lv.id}>
                    <td className="td font-medium">{emp?.full_name ?? "-"}</td>
                    <td className="td">
                      {LEAVE_TYPE_LABELS[lv.leave_type] ?? lv.leave_type}
                    </td>
                    <td className="td">
                      {lv.start_date} s.d. {lv.end_date}
                    </td>
                    <td className="td">{lv.reason ?? "-"}</td>
                    <td className="td">
                      <span
                        className={`badge ${LEAVE_STATUS_BADGES[lv.status] ?? ""}`}
                      >
                        {lv.status}
                      </span>
                    </td>
                    <td className="td whitespace-nowrap">
                      {lv.file_name && (
                        <button
                          onClick={async () => {
                            const { url } = await api.get<{ url: string }>(
                              `/employees/leave-requests/${lv.id}/attachment/download-url`
                            );
                            window.open(url, "_blank");
                          }}
                          className="text-xs font-medium hover:opacity-80"
                          style={{ color: "var(--accent)" }}
                          title={lv.file_name}
                        >
                          Lampiran
                        </button>
                      )}
                      {lv.status === "menunggu" ? (
                        <>
                          {lv.file_name && " · "}
                          <button
                            onClick={() => decideLeave.mutate({ id: lv.id, approved: true })}
                            disabled={decideLeave.isPending}
                            className="text-sm font-medium text-emerald-600 hover:text-emerald-800"
                          >
                            Setujui
                          </button>
                          {" · "}
                          <button
                            onClick={() => decideLeave.mutate({ id: lv.id, approved: false })}
                            disabled={decideLeave.isPending}
                            className="text-sm font-medium text-rose-600 hover:text-rose-800"
                          >
                            Tolak
                          </button>
                        </>
                      ) : !lv.file_name ? (
                        lv.decision_note ?? "-"
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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

      <PillTabs
        tabs={statusTabs}
        value={statusTab}
        onChange={(k) => {
          setStatusTab(k);
          setOffset(0);
        }}
      />

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
            <tr>
              <th className="th">No. Induk</th>
              <th className="th">Nama</th>
              <th className="th">Telepon</th>
              <th className="th">Masuk</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {employees.map((e) => (
              <tr
                key={e.id}
                onClick={() => navigate(`/employees/${e.id}`)}
                className="cursor-pointer hover:bg-[var(--hover)] transition-colors"
              >
                <td className="td font-mono text-xs">{e.employee_no}</td>
                <td className="td font-medium">{e.full_name}</td>
                <td className="td">{e.phone ?? "-"}</td>
                <td className="td">{e.join_date ?? "-"}</td>
                <td className="td">
                  <span
                    className={`badge ${
                      e.status === "aktif" ? "pill p-green" : "pill p-gray"
                    }`}
                  >
                    {e.status}
                  </span>
                </td>
              </tr>
            ))}
            {employees.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  {allEmployees.length === 0 ? "Belum ada karyawan." : "Tidak ada karyawan untuk status ini."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination offset={offset} limit={pageLimit} total={employeesTotal} onOffsetChange={setOffset} />

    </div>
  );
}
