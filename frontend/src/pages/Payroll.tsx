import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile, formatRupiah } from "../api/client";

interface EmployeeRow {
  id: string;
  employee_no: string;
  full_name: string;
  status: string;
}

interface AttendanceRow {
  id: string;
  employee_id: string;
  year: number;
  month: number;
  present_days: number;
  overtime_hours: number;
  client_approved: boolean;
}

interface RunRow {
  id: string;
  year: number;
  month: number;
  status: string;
  finalized_at: string | null;
}

interface SlipRow {
  id: string;
  employee_id: string;
  base_salary: number;
  allowance: number;
  overtime_hours: number;
  overtime_amount: number;
  deductions: number;
  gross: number;
  tax_pph21: number;
  net_pay: number;
}

interface BpjsRow {
  employee_id: string;
  full_name: string;
  bpjs_kesehatan_no: string | null;
  bpjs_ketenagakerjaan_no: string | null;
  salary_kesehatan: number;
  breakdown: Record<string, number>;
  employer_total: number;
  employee_total: number;
  grand_total: number;
}

interface BpjsRecap {
  year: number;
  month: number;
  rows: BpjsRow[];
  summary: { employer_total: number; employee_total: number; grand_total: number };
}

export default function Payroll() {
  const qc = useQueryClient();
  const [period, setPeriod] = useState({ year: 2026, month: 8 });
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => api.get<EmployeeRow[]>("/employees"),
  });
  const { data: attendance } = useQuery({
    queryKey: ["attendance", period],
    queryFn: () =>
      api.get<AttendanceRow[]>(
        `/payroll/attendance?year=${period.year}&month=${period.month}`
      ),
  });
  const { data: runs } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get<RunRow[]>("/payroll/runs"),
  });
  const { data: slips } = useQuery({
    queryKey: ["slips", selectedRunId],
    queryFn: () => api.get<SlipRow[]>(`/payroll/runs/${selectedRunId}/slips`),
    enabled: Boolean(selectedRunId),
  });
  const { data: bpjsRecap } = useQuery({
    queryKey: ["bpjs", period],
    queryFn: () =>
      api.get<BpjsRecap>(`/bpjs/contributions/${period.year}/${period.month}`),
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["attendance"] });
    qc.invalidateQueries({ queryKey: ["runs"] });
    qc.invalidateQueries({ queryKey: ["slips"] });
  };

  const upsertAttendance = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/payroll/attendance", body),
    onSuccess: invalidateAll,
  });
  const approveAttendance = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      api.patch(`/payroll/attendance/${id}/client-approval?approved=${approved}`, {}),
    onSuccess: invalidateAll,
  });
  const createRun = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/payroll/runs", body),
    onSuccess: invalidateAll,
  });
  const generateSlips = useMutation({
    mutationFn: (runId: string) =>
      api.post(`/payroll/runs/${runId}/generate`, {
        allowance: 0,
        deductions: 0,
        overtime_rate: 50000,
      }),
    onSuccess: invalidateAll,
  });
  const finalizeRun = useMutation({
    mutationFn: (runId: string) => api.post(`/payroll/runs/${runId}/finalize`, {}),
    onSuccess: invalidateAll,
  });

  function handleAttendance(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    upsertAttendance.mutate({
      employee_id: form.get("employee_id"),
      year: period.year,
      month: period.month,
      present_days: Number(form.get("present_days") || 0),
      overtime_hours: Number(form.get("overtime_hours") || 0),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-slate-800">Payroll</h1>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={period.month}
            min={1}
            max={12}
            onChange={(e) => setPeriod({ ...period, month: Number(e.target.value) })}
            className="input w-20"
          />
          <input
            type="number"
            value={period.year}
            onChange={(e) => setPeriod({ ...period, year: Number(e.target.value) })}
            className="input w-24"
          />
          <button
            className="btn"
            onClick={() =>
              createRun.mutate({ year: period.year, month: period.month })
            }
          >
            + Run Payrol
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold text-slate-700">
          Absensi & Lembur — {period.month}/{period.year} (approval klien)
        </h2>
        <form onSubmit={handleAttendance} className="mt-3 flex flex-wrap items-center gap-2">
          <select name="employee_id" required className="input w-auto">
            {(employees ?? [])
              .filter((e) => e.status === "aktif")
              .map((e) => (
                <option key={e.id} value={e.id}>
                  {e.employee_no} · {e.full_name}
                </option>
              ))}
          </select>
          <input name="present_days" type="number" placeholder="Hari hadir" className="input w-28" />
          <input name="overtime_hours" type="number" placeholder="Jam lembur" className="input w-28" />
          <button className="btn-secondary">Simpan Rekap</button>
        </form>
        <table className="mt-3 w-full">
          <thead>
            <tr>
              <th className="th">Karyawan</th>
              <th className="th">Hadir</th>
              <th className="th">Lembur</th>
              <th className="th">Approval Klien</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(attendance ?? []).map((a) => {
              const emp = employees?.find((e) => e.id === a.employee_id);
              return (
                <tr key={a.id}>
                  <td className="td">{emp?.full_name ?? "-"}</td>
                  <td className="td">{a.present_days}</td>
                  <td className="td">{a.overtime_hours}</td>
                  <td className="td">
                    {a.client_approved ? (
                      <span className="badge bg-emerald-100 text-emerald-700">disetujui</span>
                    ) : (
                      <button
                        onClick={() => approveAttendance.mutate({ id: a.id, approved: true })}
                        className="btn-secondary text-xs"
                      >
                        Setujui
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {attendance?.length === 0 && (
              <tr>
                <td colSpan={4} className="td py-6 text-center text-slate-400">
                  Belum ada rekap absensi untuk periode ini.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Periode</th>
              <th className="th">Status</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(runs ?? []).map((r) => (
              <tr key={r.id}>
                <td className="td font-medium">
                  {String(r.month).padStart(2, "0")}/{r.year}
                </td>
                <td className="td">
                  <span
                    className={`badge ${
                      r.status === "final"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {r.status}
                  </span>
                </td>
                <td className="td space-x-2 whitespace-nowrap">
                  <button onClick={() => setSelectedRunId(r.id)} className="text-sm font-medium text-indigo-600 hover:text-indigo-800">
                    Slip Gaji
                  </button>
                  {r.status !== "final" && (
                    <>
                      <button onClick={() => generateSlips.mutate(r.id)} className="text-sm font-medium text-slate-600 hover:text-slate-900">
                        Generate
                      </button>
                      <button onClick={() => finalizeRun.mutate(r.id)} className="text-sm font-medium text-rose-600 hover:text-rose-800">
                        Finalisasi
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {runs?.length === 0 && (
              <tr>
                <td colSpan={3} className="td py-8 text-center text-slate-400">
                  Belum ada payroll run.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedRunId && (
        <div className="card overflow-x-auto p-0">
          <div className="border-b border-slate-200 p-4">
            <h2 className="font-semibold text-slate-700">Slip Gaji</h2>
          </div>
          <table className="w-full">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="th">Karyawan</th>
                <th className="th">Gaji Pokok</th>
                <th className="th">Lembur</th>
                <th className="th">Bruto</th>
                <th className="th">PPh21 (TER)</th>
                <th className="th">Diterima</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(slips ?? []).map((s) => {
                const emp = employees?.find((e) => e.id === s.employee_id);
                return (
                  <tr key={s.id}>
                    <td className="td">{emp?.full_name ?? "-"}</td>
                    <td className="td">{formatRupiah(Number(s.base_salary))}</td>
                    <td className="td">
                      {s.overtime_hours > 0 ? formatRupiah(Number(s.overtime_amount)) : "-"}
                    </td>
                    <td className="td">{formatRupiah(Number(s.gross))}</td>
                    <td className="td text-rose-600">-{formatRupiah(Number(s.tax_pph21))}</td>
                    <td className="td font-semibold text-emerald-700">
                      {formatRupiah(Number(s.net_pay))}
                    </td>
                  </tr>
                );
              })}
              {slips?.length === 0 && (
                <tr>
                  <td colSpan={6} className="td py-8 text-center text-slate-400">
                    Belum ada slip. Tekan "Generate" pada run ini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="card p-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 p-4">
          <h2 className="font-semibold text-slate-700">
            Rekap Iuran BPJS — {period.year}-{String(period.month).padStart(2, "0")}
          </h2>
          <div className="flex gap-2">
            <button
              className="btn-secondary text-xs"
              onClick={() =>
                downloadFile(`/bpjs/contributions/${period.year}/${period.month}/export`)
              }
            >
              Unduh CSV Iuran
            </button>
            <button
              className="btn-secondary text-xs"
              onClick={() => downloadFile("/bpjs/enrollments/export")}
            >
              Unduh Data Peserta
            </button>
          </div>
        </div>
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Karyawan</th>
              <th className="th">No BPJS TK</th>
              <th className="th">Gaji Kes (cap)</th>
              <th className="th">Iuran Perusahaan</th>
              <th className="th">Potongan Karyawan</th>
              <th className="th">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(bpjsRecap?.rows ?? []).map((r) => (
              <tr key={r.employee_id}>
                <td className="td font-medium">{r.full_name}</td>
                <td className="td font-mono text-xs">{r.bpjs_ketenagakerjaan_no ?? "-"}</td>
                <td className="td">{formatRupiah(r.salary_kesehatan)}</td>
                <td className="td text-slate-600">{formatRupiah(r.employer_total)}</td>
                <td className="td text-rose-600">-{formatRupiah(r.employee_total)}</td>
                <td className="td font-semibold">{formatRupiah(r.grand_total)}</td>
              </tr>
            ))}
            {bpjsRecap && bpjsRecap.rows.length > 0 && (
              <tr className="bg-slate-50 font-bold">
                <td className="td" colSpan={3}>
                  Total
                </td>
                <td className="td">{formatRupiah(bpjsRecap.summary.employer_total)}</td>
                <td className="td text-rose-700">
                  -{formatRupiah(bpjsRecap.summary.employee_total)}
                </td>
                <td className="td">{formatRupiah(bpjsRecap.summary.grand_total)}</td>
              </tr>
            )}
            {bpjsRecap?.rows.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center text-slate-400">
                  Tidak ada karyawan aktif.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
