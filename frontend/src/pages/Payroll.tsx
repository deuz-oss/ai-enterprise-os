import { FormEvent, useMemo, useRef, useState } from "react";
import { AlertCircle, Landmark, ShieldAlert, Users, Wallet } from "lucide-react";
import { PageHeader, CalloutBlock } from "../components/workspace";
import { Button, confirmToast, KpiCard, PreflightAlert } from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile, formatRupiah, previewFile } from "../api/client";

interface EmployeeRow {
  id: string;
  employee_no: string;
  full_name: string;
  status: string;
  bank_name: string | null;
  bpjs_kesehatan_valid_until: string | null;
  bpjs_ketenagakerjaan_valid_until: string | null;
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

interface SalaryHold {
  id: string;
  employee_id: string;
  held_payslip_id: string;
  released_payslip_id: string | null;
  amount: number;
  reason: string;
  status: "held" | "released";
  held_at: string;
  released_at: string | null;
}

// Preset komponen Saltab tambahan (Bonus/Insentif/THR/dst, gap 2026-09-06) --
// murni bantuan dropdown, backend terima ctype/code/name apa saja.
const SALTAB_COMPONENT_PRESETS: { code: string; name: string; ctype: "earnings" | "deduction" }[] = [
  { code: "bonus", name: "Bonus", ctype: "earnings" },
  { code: "insentif", name: "Insentif", ctype: "earnings" },
  { code: "thr", name: "THR", ctype: "earnings" },
  { code: "kompensasi_uuck", name: "Kompensasi UUCK", ctype: "earnings" },
  { code: "reimbursement", name: "Reimbursement", ctype: "earnings" },
  { code: "perdin", name: "Perjalanan Dinas", ctype: "earnings" },
  { code: "kasbon", name: "Kasbon (Cash Advance)", ctype: "deduction" },
  { code: "lainnya", name: "", ctype: "earnings" },
];

// Kode komponen yang tombol hapusnya TIDAK boleh muncul: hasil `generate_slips`
// (bukan dari "+ Tambah Komponen", walau `source`-nya terlanjur "manual"
// akibat pernah di-override lewat tombol "edit") DAN komponen tahan/cairkan
// gaji (harus lewat alur "Cairkan" di badge, bukan dihapus langsung --
// menghapusnya langsung akan meninggalkan SalaryHold "held" tanpa jejak).
const _CORE_COMPONENT_CODES = new Set([
  "gaji_pokok",
  "tunjangan",
  "lembur",
  "pph21",
  "potongan_lain",
  "admin_bank",
  "bpjs_kesehatan_py",
  "jht_py",
  "jp_py",
  "bpjs_employer",
  "tahan_gaji",
  "pencairan_gaji_ditahan",
]);

/** Badge "gaji tertahan" + tombol cairkan — satu query per karyawan (wajar,
 * jumlah karyawan per run tidak besar), dipakai di dalam baris SaltabTable. */
function HeldSalaryBadge({
  employeeId,
  targetPayslipId,
  runId,
}: {
  employeeId: string;
  targetPayslipId: string;
  runId: string | null;
}) {
  const qc = useQueryClient();
  const { data: holds } = useQuery({
    queryKey: ["salary-holds", employeeId, "held"],
    queryFn: () =>
      api.get<SalaryHold[]>(`/payroll/employees/${employeeId}/holds?status=held`),
  });
  const release = useMutation({
    mutationFn: (holdId: string) =>
      api.post(`/payroll/slips/${targetPayslipId}/holds/${holdId}/release`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["salary-holds", employeeId, "held"] });
      qc.invalidateQueries({ queryKey: ["saltab", runId] });
      qc.invalidateQueries({ queryKey: ["slips", runId] });
    },
  });
  if (!holds || holds.length === 0) return null;
  return (
    <>
      {holds.map((h) => (
        <span key={h.id} className="pill p-yellow inline-flex items-center gap-1">
          Gaji tertahan: {formatRupiah(h.amount)}
          <button
            onClick={() => release.mutate(h.id)}
            disabled={release.isPending}
            className="ml-1 font-medium underline hover:opacity-80"
            title={h.reason}
          >
            Cairkan
          </button>
        </span>
      ))}
      {release.error && (
        <span className="text-red-600">{(release.error as Error).message}</span>
      )}
    </>
  );
}

function SaltabTable({ runId }: { runId: string | null }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [addingComponentFor, setAddingComponentFor] = useState<string | null>(null);
  const [holdingFor, setHoldingFor] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
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
  const addComponent = useMutation({
    mutationFn: ({
      payslipId,
      ctype,
      code,
      name,
      amount,
    }: {
      payslipId: string;
      ctype: string;
      code: string;
      name: string;
      amount: number;
    }) => api.post(`/payroll/slips/${payslipId}/components`, { ctype, code, name, amount }),
    onSuccess: () => {
      setAddingComponentFor(null);
      qc.invalidateQueries({ queryKey: ["saltab", runId] });
      qc.invalidateQueries({ queryKey: ["slips", runId] });
    },
  });
  const deleteComponent = useMutation({
    mutationFn: (componentId: string) =>
      api.delete(`/payroll/saltab/components/${componentId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["saltab", runId] });
      qc.invalidateQueries({ queryKey: ["slips", runId] });
    },
  });
  const createHold = useMutation({
    mutationFn: ({
      payslipId,
      amount,
      reason,
    }: {
      payslipId: string;
      amount: number;
      reason: string;
    }) => api.post(`/payroll/slips/${payslipId}/holds`, { amount, reason }),
    onSuccess: () => {
      setHoldingFor(null);
      qc.invalidateQueries({ queryKey: ["saltab", runId] });
      qc.invalidateQueries({ queryKey: ["slips", runId] });
      qc.invalidateQueries({ queryKey: ["salary-holds"] });
    },
  });
  const sendPayslip = useMutation({
    mutationFn: (employeeId: string) =>
      api.post(`/payroll/runs/${runId}/employees/${employeeId}/send-payslip-email`),
  });
  const previewPayslip = useMutation({
    mutationFn: (employeeId: string) =>
      previewFile(`/payroll/runs/${runId}/employees/${employeeId}/payslip/pdf`),
    onSuccess: setPreviewUrl,
  });
  function closePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  }
  const err = (saveAmount.error ??
    addComponent.error ??
    deleteComponent.error ??
    createHold.error ??
    previewPayslip.error ??
    sendPayslip.error) as Error | null;

  if (!runId)
    return (
      <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>
        Pilih payroll run (klik "Slip Gaji") untuk melihat grid Saltab.
      </p>
    );
  if (isLoading) return <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>;

  return (
    <>
    <div className="divide-y" style={{ borderColor: "var(--border)" }}>
      {(rows ?? []).map((row) => (
        <div key={row.payslip_id} className="px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{row.employee_name}</p>
              <HeldSalaryBadge
                employeeId={row.employee_id}
                targetPayslipId={row.payslip_id}
                runId={runId}
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  setAddingComponentFor(addingComponentFor === row.payslip_id ? null : row.payslip_id)
                }
                className="cursor-pointer text-xs font-medium hover:opacity-80"
                style={{ color: "var(--accent)" }}
              >
                + Tambah Komponen
              </button>
              <button
                onClick={() => setHoldingFor(holdingFor === row.payslip_id ? null : row.payslip_id)}
                className="cursor-pointer text-xs font-medium hover:opacity-80"
                style={{ color: "var(--accent)" }}
              >
                Tahan Gaji
              </button>
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
                onClick={() => previewPayslip.mutate(row.employee_id)}
                disabled={previewPayslip.isPending}
                className="cursor-pointer text-xs font-medium hover:opacity-80"
                style={{ color: "var(--accent)" }}
                title="Pratinjau slip gaji karyawan ini"
              >
                Preview Slip Gaji
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
                  <td className="w-32 py-0.5 pl-2 text-right">
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
                      <span className="inline-flex gap-2">
                        <button
                          onClick={() => setEditing(c.id)}
                          style={{ color: "var(--accent)" }}
                          className="hover:opacity-80"
                          title="Override manual"
                        >
                          edit
                        </button>
                        {c.source === "manual" && !_CORE_COMPONENT_CODES.has(c.code) && (
                          <button
                            onClick={() => deleteComponent.mutate(c.id)}
                            disabled={deleteComponent.isPending}
                            className="text-rose-600 hover:text-rose-800"
                          >
                            hapus
                          </button>
                        )}
                      </span>
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

          {addingComponentFor === row.payslip_id && (
            <form
              className="mt-2 flex flex-wrap items-end gap-2 rounded-lg p-2"
              style={{ backgroundColor: "var(--hover)" }}
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                const presetCode = String(f.get("preset") || "");
                const preset = SALTAB_COMPONENT_PRESETS.find((p) => p.code === presetCode);
                if (!preset) return;
                const name = presetCode === "lainnya" ? String(f.get("custom_name") || "") : preset.name;
                if (!name) return;
                addComponent.mutate({
                  payslipId: row.payslip_id,
                  ctype: String(f.get("ctype") || preset.ctype),
                  code: presetCode,
                  name,
                  amount: Number(f.get("amount") || 0),
                });
              }}
            >
              <select name="preset" defaultValue="" required className="input py-1 text-xs">
                <option value="" disabled>
                  -- Pilih komponen --
                </option>
                {SALTAB_COMPONENT_PRESETS.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.code === "lainnya" ? "Lainnya (nama bebas)" : p.name}
                  </option>
                ))}
              </select>
              <input
                name="custom_name"
                placeholder="Nama komponen (kalau pilih Lainnya)"
                className="input py-1 text-xs"
              />
              <select name="ctype" defaultValue="earnings" className="input py-1 text-xs">
                <option value="earnings">Earnings (menambah THP)</option>
                <option value="deduction">Deduction (mengurangi THP)</option>
              </select>
              <input
                name="amount"
                type="number"
                required
                placeholder="Nominal"
                className="input w-32 py-1 text-xs"
              />
              <Button size="sm" type="submit" loading={addComponent.isPending}>
                Tambah
              </Button>
              <button
                type="button"
                onClick={() => setAddingComponentFor(null)}
                className="text-xs"
                style={{ color: "var(--th-color)" }}
              >
                Batal
              </button>
            </form>
          )}

          {holdingFor === row.payslip_id && (
            <form
              className="mt-2 flex flex-wrap items-end gap-2 rounded-lg p-2"
              style={{ backgroundColor: "var(--hover)" }}
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                createHold.mutate({
                  payslipId: row.payslip_id,
                  amount: Number(f.get("amount") || 0),
                  reason: String(f.get("reason") || ""),
                });
              }}
            >
              <input
                name="amount"
                type="number"
                required
                placeholder="Nominal ditahan"
                className="input w-32 py-1 text-xs"
              />
              <input
                name="reason"
                required
                placeholder="Alasan (mis. menunggu pengembalian aset)"
                className="input flex-1 py-1 text-xs"
              />
              <Button size="sm" type="submit" loading={createHold.isPending}>
                Tahan
              </Button>
              <button
                type="button"
                onClick={() => setHoldingFor(null)}
                className="text-xs"
                style={{ color: "var(--th-color)" }}
              >
                Batal
              </button>
            </form>
          )}
        </div>
      ))}
      {rows?.length === 0 && (
        <p className="p-4 text-sm" style={{ color: "var(--text-muted)" }}>Belum ada slip pada run ini.</p>
      )}
      {err && <p className="px-4 pb-3 text-sm text-red-600">{err.message}</p>}
    </div>
    {previewUrl && (
      <div
        className="fixed inset-0 z-50 flex items-start justify-center pt-[6vh]"
        style={{ background: "rgba(15,15,15,0.45)" }}
        onClick={closePreview}
      >
        <div
          className="flex h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-md"
          style={{
            backgroundColor: "var(--bg-elevated)",
            boxShadow: "0 12px 40px rgba(15,15,15,0.25)",
            border: "1px solid var(--border)",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div
            className="flex items-center justify-between px-4 py-2"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
              Preview Slip Gaji
            </p>
            <button
              onClick={closePreview}
              className="text-xs font-medium hover:underline"
              style={{ color: "var(--text-muted)" }}
            >
              Tutup
            </button>
          </div>
          <iframe src={previewUrl} title="Preview Slip Gaji" className="flex-1" />
        </div>
      </div>
    )}
    </>
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

  // Sinyal anomali NYATA (bukan 3 contoh ilustratif di spec -- PPh21 salah
  // hitung/NPWP kedaluwarsa/NIK duplikat tidak punya data pendukung di
  // backend, dikonfirmasi lewat investigasi & keputusan eksplisit sebelum
  // implementasi ini). Semua dihitung dari data yang SUDAH di-fetch di atas.
  const [alertDismissed, setAlertDismissed] = useState(false);
  const infoCardsRef = useRef<HTMLDivElement>(null);
  const activeEmployees = (employees ?? []).filter((e) => e.status === "aktif");
  const today = new Date();
  const missingBankEmployees = activeEmployees.filter((e) => !e.bank_name);
  const expiredBpjsEmployees = activeEmployees.filter((e) => {
    const kes = e.bpjs_kesehatan_valid_until ? new Date(e.bpjs_kesehatan_valid_until) : null;
    const tk = e.bpjs_ketenagakerjaan_valid_until ? new Date(e.bpjs_ketenagakerjaan_valid_until) : null;
    return (kes !== null && kes < today) || (tk !== null && tk < today);
  });
  const negativeNetPaySlips = (slips ?? []).filter((s) => Number(s.net_pay) < 0);
  const totalAnomalies = missingBankEmployees.length + expiredBpjsEmployees.length + negativeNetPaySlips.length;

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
            aria-label="Bulan periode payroll"
          />
          <input
            type="number"
            value={period.year}
            onChange={(e) => setPeriod({ ...period, year: Number(e.target.value) })}
            className="input w-24"
            aria-label="Tahun periode payroll"
          />
          <select
            value={runType}
            onChange={(e) => setRunType(e.target.value as "internal" | "proyek")}
            className="input w-auto"
            title="Jenis payrol"
            aria-label="Jenis payrol"
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
            onClick={() => {
              const anomalySummary = [
                missingBankEmployees.length > 0 && `${missingBankEmployees.length} karyawan rekening bank kosong`,
                expiredBpjsEmployees.length > 0 && `${expiredBpjsEmployees.length} karyawan BPJS kedaluwarsa`,
                negativeNetPaySlips.length > 0 && `${negativeNetPaySlips.length} slip net pay negatif`,
              ]
                .filter((v): v is string => Boolean(v))
                .join(", ");
              const message =
                totalAnomalies > 0
                  ? `Jalankan payroll ${period.month}/${period.year} untuk ${activeEmployees.length} karyawan aktif? Perhatian: ${anomalySummary}.`
                  : `Jalankan payroll ${period.month}/${period.year} untuk ${activeEmployees.length} karyawan aktif?`;
              confirmToast(
                message,
                () =>
                  createRun.mutate({
                    year: period.year,
                    month: period.month,
                    run_type: runType,
                    ...(runType === "proyek" ? { client_id: createClientId || undefined } : {}),
                  }),
                { confirmLabel: "Run Payroll" }
              );
            }}
          >
            + Run Payrol
          </button>
        </div>
      </div>

      {totalAnomalies > 0 && !alertDismissed && (
        <PreflightAlert
          title="Perlu Perhatian Sebelum Proses Payroll"
          summary={[
            missingBankEmployees.length > 0 && `${missingBankEmployees.length} karyawan rekening bank kosong`,
            expiredBpjsEmployees.length > 0 && `${expiredBpjsEmployees.length} karyawan BPJS kedaluwarsa`,
            negativeNetPaySlips.length > 0 && `${negativeNetPaySlips.length} slip net pay negatif`,
          ]
            .filter((v): v is string => Boolean(v))
            .join(", ")}
          actionLabel={`Lihat ${totalAnomalies} Kasus`}
          onAction={() => infoCardsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
          onDismiss={() => setAlertDismissed(true)}
        />
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Karyawan Aktif" value={activeEmployees.length} icon={Users} iconTone="info" />
        <KpiCard
          label="Absensi Tercatat"
          value={(attendance ?? []).length}
          icon={Users}
          iconTone="neutral"
          context={`dari ${activeEmployees.length} karyawan aktif`}
        />
        <KpiCard
          label="Total Iuran BPJS"
          value={formatRupiah(bpjsRecap?.summary.grand_total ?? 0)}
          icon={ShieldAlert}
          iconTone="accent"
          context={`Periode ${period.month}/${period.year}`}
        />
        <KpiCard
          label="Anomali Terdeteksi"
          value={totalAnomalies}
          icon={AlertCircle}
          iconTone="danger"
          badge={totalAnomalies > 0 ? { label: "Perlu Tindakan", tone: "danger" } : undefined}
        />
      </div>

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--text)" }}>
          Absensi & Lembur — {period.month}/{period.year} (approval klien)
        </h2>
        <form onSubmit={handleAttendance} className="mt-3 flex flex-wrap items-center gap-2">
          <select name="employee_id" required className="input w-auto" aria-label="Pilih karyawan">
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
                <th className="th text-right">Gaji Pokok</th>
                <th className="th text-right">Lembur</th>
                <th className="th text-right">Bruto</th>
                <th className="th text-right">PPh21 (TER)</th>
                <th className="th text-right">Diterima</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
              {(slips ?? []).map((s) => {
                const emp = employees?.find((e) => e.id === s.employee_id);
                const isNegative = Number(s.net_pay) < 0;
                return (
                  <tr key={s.id}>
                    <td className="td">{emp?.full_name ?? "-"}</td>
                    <td className="td text-right tabular-nums">{formatRupiah(Number(s.base_salary))}</td>
                    <td className="td text-right tabular-nums">
                      {s.overtime_hours > 0 ? formatRupiah(Number(s.overtime_amount)) : "-"}
                    </td>
                    <td className="td text-right tabular-nums">{formatRupiah(Number(s.gross))}</td>
                    <td className="td text-rose-600 text-right tabular-nums">-{formatRupiah(Number(s.tax_pph21))}</td>
                    <td className="td font-semibold text-right tabular-nums">
                      {isNegative ? (
                        <>
                          <span className="text-amber-700">{formatRupiah(Number(s.net_pay))}*</span>
                          <div className="text-[11px] font-normal text-amber-700">
                            (Net Pay Negatif)
                          </div>
                        </>
                      ) : (
                        <span className="text-emerald-700">{formatRupiah(Number(s.net_pay))}</span>
                      )}
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
              <th className="th text-right">Gaji Kes (cap)</th>
              <th className="th text-right">Iuran Perusahaan</th>
              <th className="th text-right">Potongan Karyawan</th>
              <th className="th text-right">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(bpjsRecap?.rows ?? []).map((r) => (
              <tr key={r.employee_id}>
                <td className="td font-medium">{r.full_name}</td>
                <td className="td font-mono text-xs">{r.bpjs_ketenagakerjaan_no ?? "-"}</td>
                <td className="td text-right tabular-nums">{formatRupiah(r.salary_kesehatan)}</td>
                <td className="td text-right tabular-nums" style={{ color: "var(--text-muted)" }}>{formatRupiah(r.employer_total)}</td>
                <td className="td text-rose-600 text-right tabular-nums">-{formatRupiah(r.employee_total)}</td>
                <td className="td font-semibold text-right tabular-nums">{formatRupiah(r.grand_total)}</td>
              </tr>
            ))}
            {bpjsRecap && bpjsRecap.rows.length > 0 && (
              <tr className="font-bold" style={{ backgroundColor: "var(--hover)" }}>
                <td className="td" colSpan={3}>
                  Total
                </td>
                <td className="td text-right tabular-nums">{formatRupiah(bpjsRecap.summary.employer_total)}</td>
                <td className="td text-rose-700 text-right tabular-nums">
                  -{formatRupiah(bpjsRecap.summary.employee_total)}
                </td>
                <td className="td text-right tabular-nums">{formatRupiah(bpjsRecap.summary.grand_total)}</td>
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

      {/* Kartu Info Baris Bawah (§1.7) -- kesiapan rekening & kepatuhan BPJS
          dari data karyawan yang sudah di-fetch, bukan jadwal cut-off
          fiktif (tidak ada konsep itu di backend Payroll). */}
      <div ref={infoCardsRef} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="card">
          <div className="flex items-center gap-2">
            <Landmark className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Kesiapan Rekening</h3>
            {missingBankEmployees.length > 0 && <span className="pill p-red ml-auto">{missingBankEmployees.length} kosong</span>}
          </div>
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {missingBankEmployees.length === 0
              ? "Semua karyawan aktif sudah punya rekening bank terdaftar."
              : `${missingBankEmployees.slice(0, 3).map((e) => e.full_name).join(", ")}${
                  missingBankEmployees.length > 3 ? ` +${missingBankEmployees.length - 3} lagi` : ""
                } belum punya rekening bank.`}
          </p>
        </div>
        <div className="card">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Kepatuhan BPJS</h3>
            {expiredBpjsEmployees.length > 0 && <span className="pill p-red ml-auto">{expiredBpjsEmployees.length} kedaluwarsa</span>}
          </div>
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {expiredBpjsEmployees.length === 0
              ? "Tidak ada BPJS kedaluwarsa pada karyawan aktif."
              : `${expiredBpjsEmployees.slice(0, 3).map((e) => e.full_name).join(", ")}${
                  expiredBpjsEmployees.length > 3 ? ` +${expiredBpjsEmployees.length - 3} lagi` : ""
                } BPJS-nya sudah kedaluwarsa.`}
          </p>
        </div>
        <div className="card">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Slip Bermasalah</h3>
            {negativeNetPaySlips.length > 0 && <span className="pill p-red ml-auto">{negativeNetPaySlips.length} negatif</span>}
          </div>
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {!selectedRunId
              ? "Pilih run (\"Slip Gaji\") untuk memeriksa net pay."
              : negativeNetPaySlips.length === 0
                ? "Tidak ada slip dengan net pay negatif pada run ini."
                : `${negativeNetPaySlips.length} slip pada run ini punya net pay negatif -- lihat tabel Slip Gaji di atas.`}
          </p>
        </div>
      </div>
    </div>
  );
}
