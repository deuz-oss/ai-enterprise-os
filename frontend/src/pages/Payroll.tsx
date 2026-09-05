import { FormEvent, useState } from "react";
import { Wallet } from "lucide-react";
import { PageHeader, CalloutBlock } from "../components/workspace";
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
  run_type: "internal" | "proyek";
  client_id: string | null;
  status: string;
  finalized_at: string | null;
}

interface ClientRow {
  id: string;
  name: string;
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

interface SaltabComp {
  id: string;
  ctype: "earnings" | "deduction" | "passthrough";
  code: string;
  name: string;
  amount: number;
  source: string;
  notes: string | null;
}

interface SaltabRow {
  payslip_id: string;
  employee_id: string;
  employee_name: string;
  components: SaltabComp[];
  total_earnings: number;
  total_deductions: number;
  total_passthrough: number;
}

function SaltabTable({ runId }: { runId: string | null }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const { data: rows, isLoading } = useQuery({
    queryKey: ["saltab", runId],
    queryFn: () => api.get<SaltabRow[]>(`/payroll/runs/${runId}/saltab`),
    enabled: Boolean(runId),
  });
  const saveAmount = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: number }) =>
      api.patch(`/payroll/saltab/components/${id}`, { amount }),
    onSuccess: () => {
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["saltab", runId] });
      qc.invalidateQueries({ queryKey: ["slips", runId] });
    },
  });
  const sendPayslip = useMutation({
    mutationFn: (employeeId: string) =>
      api.post(`/payroll/runs/${runId}/employees/${employeeId}/send-payslip-email`),
  });
  const err = (saveAmount.error ?? sendPayslip.error) as Error | null;

  if (!runId)
    return (
      <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>
        Pilih payroll run (klik "Slip Gaji") untuk melihat grid Saltab.
      </p>
    );
  if (isLoading) return <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>;

  return (
    <div className="divide-y" style={{ borderColor: "var(--border)" }}>
      {(rows ?? []).map((row) => (
        <div key={row.payslip_id} className="px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{row.employee_name}</p>
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  downloadFile(`/payroll/runs/${runId}/bukti-potong/${row.employee_id}/pdf`)
                }
                className="cursor-pointer text-xs font-medium hover:opacity-80"
                style={{ color: "var(--accent)" }}
                title="Unduh Bukti Potong PPh 21 karyawan ini"
              >
                Bukti Potong PPh 21
              </button>
              <button
                onClick={() => sendPayslip.mutate(row.employee_id)}
                disabled={sendPayslip.isPending}
                className="cursor-pointer text-xs font-medium hover:opacity-80"
                style={{ color: "var(--accent)" }}
                title="Kirim payslip ke email karyawan ini"
              >
                Kirim Payslip
              </button>
            </div>
          </div>
          <table className="mt-1 w-full text-xs">
            <tbody>
              {row.components.map((c) => (
                <tr key={c.id}>
                  <td className="py-0.5 pr-2 capitalize" style={{ color: "var(--text-muted)" }}>
                    {c.name}
                    {c.source === "manual" && (
                      <span className="ml-1 pill p-indigo">manual</span>
                    )}
                  </td>
                  <td className="py-0.5 pr-2 uppercase text-[10px]" style={{ color: "var(--text-muted)" }}>
                    {c.ctype}
                  </td>
                  <td className="w-40 py-0.5 text-right font-mono">
                    {editing === c.id ? null : formatRupiah(c.amount)}
                  </td>
                  <td className="w-24 py-0.5 pl-2 text-right">
                    {editing === c.id ? (
                      <form
                        className="flex justify-end gap-1"
                        onSubmit={(e) => {
                          e.preventDefault();
                          const f = new FormData(e.currentTarget);
                          saveAmount.mutate({
                            id: c.id,
                            amount: Number(f.get("amount") || 0),
                          });
                        }}
                      >
                        <input
                          name="amount"
                          type="number"
                          defaultValue={c.amount}
                          className="input w-28 px-1 py-0.5 text-right"
                        />
                        <button className="btn-secondary px-1.5 py-0.5">✓</button>
                      </form>
                    ) : (
                      <button
                        onClick={() => setEditing(c.id)}
                        style={{ color: "var(--accent)" }}
                        className="hover:opacity-80"
                        title="Override manual"
                      >
                        edit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              <tr className="font-semibold">
                <td className="pt-1">THP</td>
                <td />
                <td className="pt-1 text-right font-mono">
                  {formatRupiah(row.total_earnings - row.total_deductions)}
                </td>
                <td />
              </tr>
              {row.total_passthrough > 0 && (
                <tr style={{ color: "var(--text-muted)" }}>
                  <td className="pr-2" colSpan={2}>
                    + BPJS perusahaan (pass-through, ditagih ke klien)
                  </td>
                  <td className="text-right font-mono">{formatRupiah(row.total_passthrough)}</td>
                  <td />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ))}
      {rows?.length === 0 && (
        <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>Belum ada slip pada run ini.</p>
      )}
      {err && <p className="px-4 pb-3 text-sm text-red-600">{err.message}</p>}
    </div>
  );
}

export default function Payroll() {
  const qc = useQueryClient();
  const [period, setPeriod] = useState({ year: 2026, month: 8 });
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runType, setRunType] = useState<"internal" | "proyek">("internal");
  const [createClientId, setCreateClientId] = useState("");
  const [clientLink, setClientLink] = useState<{ link: string; expires: string } | null>(null);

  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });

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
  const submitToClient = useMutation({
    mutationFn: (runId: string) =>
      api.post<{ status: string; expires_at: string; link: string }>(
        `/payroll/runs/${runId}/submit-to-client`,
        { days: 14 }
      ),
    onSuccess: (data) => {
      setClientLink({ link: data.link, expires: data.expires_at });
      invalidateAll();
    },
  });
  const startProcessing = useMutation({
    mutationFn: (runId: string) => api.post(`/payroll/runs/${runId}/start-processing`, {}),
    onSuccess: invalidateAll,
  });
  const createPr = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<{ pr_number: string }>("/payment-requests", body),
  });
  const [showSendSaltab, setShowSendSaltab] = useState(false);
  const sendSaltabToClient = useMutation({
    mutationFn: ({ runId, recipientEmail }: { runId: string; recipientEmail: string }) =>
      api.post(`/payroll/runs/${runId}/send-to-client`, { recipient_email: recipientEmail }),
    onSuccess: () => setShowSendSaltab(false),
  });

  const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
    draft: { label: "Draft", cls: "pill p-gray" },
    submitted_to_client: { label: "Menunggu Klien", cls: "pill p-yellow" },
    client_rejected: { label: "Ditolak Klien", cls: "pill p-red" },
    client_approved: { label: "Disetujui Klien", cls: "pill p-green" },
    finance_processing: { label: "Proses Finance", cls: "pill p-blue" },
    final: { label: "Final", cls: "pill p-gray" },
  };

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
        <PageHeader icon={Wallet} title="Payroll" />
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
          <select
            value={runType}
            onChange={(e) => setRunType(e.target.value as "internal" | "proyek")}
            className="input w-auto"
            title="Jenis payrol"
          >
            <option value="internal">Internal</option>
            <option value="proyek">Proyek (per klien)</option>
          </select>
          {runType === "proyek" && (
            <select
              onChange={(e) => setCreateClientId(e.target.value)}
              defaultValue=""
              className="input w-auto"
              title="Klien"
            >
              <option value="">-- pilih klien --</option>
              {(clients ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          <button
            className="btn"
            onClick={() =>
              createRun.mutate({
                year: period.year,
                month: period.month,
                run_type: runType,
                ...(runType === "proyek" ? { client_id: createClientId || undefined } : {}),
              })
            }
          >
            + Run Payrol
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--text)" }}>
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
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(attendance ?? []).map((a) => {
              const emp = employees?.find((e) => e.id === a.employee_id);
              return (
                <tr key={a.id}>
                  <td className="td">{emp?.full_name ?? "-"}</td>
                  <td className="td">{a.present_days}</td>
                  <td className="td">{a.overtime_hours}</td>
                  <td className="td">
                    {a.client_approved ? (
                      <span className="pill p-green">disetujui</span>
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
                <td colSpan={4} className="td py-6 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada rekap absensi untuk periode ini.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {clientLink && (
        <CalloutBlock tone="success">
          <p className="font-medium">Link approval klien aktif</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <code className="rounded px-2 py-0.5 text-xs" style={{ backgroundColor: "var(--hover)", border: "1px solid var(--border)" }}>{clientLink.link}</code>
            <button
              className="btn-secondary py-0.5 text-xs"
              onClick={() => navigator.clipboard.writeText(window.location.origin + clientLink.link)}
            >
              Salin URL
            </button>
            <span className="text-xs">berlaku s.d. {new Date(clientLink.expires).toLocaleString("id-ID")}</span>
          </div>
        </CalloutBlock>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
            <tr>
              <th className="th">Periode</th>
              <th className="th">Jenis / Klien</th>
              <th className="th">Status</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(runs ?? []).map((r) => {
              const badge = STATUS_LABELS[r.status] ?? { label: r.status, cls: "pill p-gray" };
              return (
                <tr key={r.id}>
                  <td className="td font-medium">
                    {String(r.month).padStart(2, "0")}/{r.year}
                  </td>
                  <td className="td text-xs">
                    {r.run_type === "proyek"
                      ? `Proyek · ${clients?.find((c) => c.id === r.client_id)?.name ?? "klien"}`
                      : "Internal"}
                  </td>
                  <td className="td">
                    <span className={`${badge.cls}`}>{badge.label}</span>
                  </td>
                  <td className="td space-x-2 whitespace-nowrap text-sm">
                    <button onClick={() => setSelectedRunId(r.id)} style={{ color: "var(--accent)" }} className="font-medium hover:opacity-80">
                      Slip Gaji
                    </button>
                    {(r.status === "draft" || (r.run_type === "proyek" && r.status === "client_rejected")) && (
                      <>
                        <button onClick={() => generateSlips.mutate(r.id)} style={{ color: "var(--text-muted)" }} className="hover:opacity-80">
                          Generate
                        </button>
                        {r.run_type === "proyek" ? (
                          <button
                            onClick={() =>
                              submitToClient.mutate(r.id, {
                                onSuccess: (d) => setClientLink({ link: d.link, expires: d.expires_at }),
                              })
                            }
                            style={{ color: "var(--accent)" }}
                            className="font-medium hover:opacity-80"
                          >
                            Kirim ke Klien
                          </button>
                        ) : (
                          <button onClick={() => finalizeRun.mutate(r.id)} className="text-rose-600 hover:text-rose-800">
                            Finalisasi
                          </button>
                        )}
                      </>
                    )}
                    {r.status === "client_approved" && (
                      <button onClick={() => startProcessing.mutate(r.id)} className="font-medium text-blue-600 hover:text-blue-800">
                        Mulai Proses Finance
                      </button>
                    )}
                    {r.status === "finance_processing" && (
                      <button onClick={() => finalizeRun.mutate(r.id)} className="text-rose-600 hover:text-rose-800">
                        Finalisasi
                      </button>
                    )}
                    {r.status === "submitted_to_client" && (
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>menunggu keputusan klien</span>
                    )}
                    {r.status === "final" && (
                      <button
                        onClick={() =>
                          createPr.mutate(
                            { payroll_run_id: r.id, pr_type: r.run_type },
                            {
                              onSuccess: () =>
                                window.location.assign("/payment-requests"),
                            }
                          )
                        }
                        style={{ color: "var(--accent)" }}
                        className="font-medium hover:opacity-80"
                        title="Ajukan Payment Request pembayaran gaji"
                      >
                        + Payment Request
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {runs?.length === 0 && (
              <tr>
                <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada payroll run.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedRunId && (
        <div className="card overflow-x-auto p-0">
          <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Slip Gaji</h2>
          </div>
          <table className="w-full">
            <thead className="border-b" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
              <tr>
                <th className="th">Karyawan</th>
                <th className="th">Gaji Pokok</th>
                <th className="th">Lembur</th>
                <th className="th">Bruto</th>
                <th className="th">PPh21 (TER)</th>
                <th className="th">Diterima</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
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
                  <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                    Belum ada slip. Tekan "Generate" pada run ini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="card p-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4" style={{ borderColor: "var(--border)" }}>
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>
            Saltab (Grid Komponen) — Run terpilih
          </h2>
          {selectedRunId && (
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                className="btn-secondary text-xs"
                onClick={() => downloadFile(`/payroll/runs/${selectedRunId}/saltab/export`)}
                title="CSV ; delimiter"
              >
                CSV
              </button>
              <button
                className="btn-secondary text-xs"
                onClick={() => downloadFile(`/payroll/runs/${selectedRunId}/saltab/export-excel`)}
              >
                Excel
              </button>
              <button
                className="btn-secondary text-xs"
                onClick={() => downloadFile(`/payroll/runs/${selectedRunId}/saltab/export-pdf`)}
              >
                PDF
              </button>
              <button
                className="btn-secondary text-xs"
                onClick={() => setShowSendSaltab(!showSendSaltab)}
                title="Kirim Saltab manual ke email klien"
              >
                {showSendSaltab ? "Batal" : "Kirim ke Klien"}
              </button>
            </div>
          )}
        </div>
        {showSendSaltab && selectedRunId && (
          <form
            className="flex flex-wrap items-center gap-2 border-b p-4"
            style={{ borderColor: "var(--border)" }}
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const recipientEmail = String(form.get("recipient_email") || "").trim();
              if (recipientEmail) {
                sendSaltabToClient.mutate({ runId: selectedRunId, recipientEmail });
              }
            }}
          >
            <input
              name="recipient_email"
              type="email"
              required
              placeholder="Email PIC klien"
              className="input w-64"
            />
            <button className="btn text-xs" disabled={sendSaltabToClient.isPending}>
              {sendSaltabToClient.isPending ? "Mengirim..." : "Kirim"}
            </button>
            {sendSaltabToClient.isSuccess && (
              <span className="text-xs text-emerald-600">Terkirim.</span>
            )}
            {sendSaltabToClient.error && (
              <span className="text-xs text-red-600">
                {(sendSaltabToClient.error as Error).message}
              </span>
            )}
          </form>
        )}
        <SaltabTable runId={selectedRunId} />
      </div>

      <div className="card p-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4" style={{ borderColor: "var(--border)" }}>
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>
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
          <thead className="border-b" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
            <tr>
              <th className="th">Karyawan</th>
              <th className="th">No BPJS TK</th>
              <th className="th">Gaji Kes (cap)</th>
              <th className="th">Iuran Perusahaan</th>
              <th className="th">Potongan Karyawan</th>
              <th className="th">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(bpjsRecap?.rows ?? []).map((r) => (
              <tr key={r.employee_id}>
                <td className="td font-medium">{r.full_name}</td>
                <td className="td font-mono text-xs">{r.bpjs_ketenagakerjaan_no ?? "-"}</td>
                <td className="td">{formatRupiah(r.salary_kesehatan)}</td>
                <td className="td" style={{ color: "var(--text-muted)" }}>{formatRupiah(r.employer_total)}</td>
                <td className="td text-rose-600">-{formatRupiah(r.employee_total)}</td>
                <td className="td font-semibold">{formatRupiah(r.grand_total)}</td>
              </tr>
            ))}
            {bpjsRecap && bpjsRecap.rows.length > 0 && (
              <tr className="font-bold" style={{ backgroundColor: "var(--hover)" }}>
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
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
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
