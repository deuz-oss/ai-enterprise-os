import { useRef, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, AlertTriangle, Award, Banknote, Calendar, Gift, Home, IdCard, Pencil, Phone, Tag } from "lucide-react";
import { api, downloadFile, formatRupiah, previewFile } from "../api/client";
import { PropertiesPanel, PropertyRow, initials } from "../components/workspace";
import { Badge, confirmToast, PillTabs } from "../components/ui";
import type { EmployeeRow } from "./Employees";

/** Halaman detail karyawan (`/employees/:id`) -- konsolidasi 11 seksi yang
 * dulu jadi satu blok scroll panjang di bawah baris terpilih di
 * `Employees.tsx` jadi tab dalam satu profil, meniru struktur MYOHRIS.
 * 3 antrean admin lintas-karyawan (Tanya Kontrak AI, Koreksi Absensi,
 * Pengajuan Cuti/Izin) SENGAJA tetap di halaman list -- itu inbox org-wide,
 * bukan konten per-karyawan. */

interface InsuranceRow {
  id: string;
  employee_id: string;
  provider: string;
  policy_no: string;
  status: string;
  start_date: string | null;
  valid_until: string | null;
  card_object_key: string | null;
  policy_object_key: string | null;
}

interface SelfserviceAccount {
  id: string;
  email: string;
  full_name: string;
}

interface ClientSiteOption {
  id: string;
  client_name: string;
  name: string;
  radius_meters: number;
}

interface LeaveBalanceRow {
  id: string;
  year: number;
  total_days: number;
  used_days: number;
  remaining: number;
}

interface ContractRow {
  id: string;
  contract_no: string;
  start_date: string | null;
  end_date: string | null;
  sign_status: string;
  signed_at: string | null;
  file_name: string | null;
  template_id: string | null;
}

interface ContractTemplateField {
  key: string;
  label: string;
  type: string;
  list_style?: string;
}

interface ContractTemplateT {
  id: string;
  name: string;
  field_schema: ContractTemplateField[];
  is_active: boolean;
}

interface HrDoc {
  id: string;
  document_type: string;
  title: string;
  version: number;
  file_name: string;
  file_size: number;
}

interface WarningLetterRow {
  id: string;
  letter_type: string;
  reason: string;
  issued_at: string;
  valid_until: string | null;
  is_active: boolean;
  file_name: string | null;
}

interface SalaryHoldRow {
  id: string;
  held_payslip_id: string;
  released_payslip_id: string | null;
  amount: number;
  reason: string;
  status: "held" | "released";
  held_at: string;
  released_at: string | null;
}

interface EmployeeMovementRow {
  id: string;
  movement_type: string;
  previous_grade: string | null;
  new_grade: string | null;
  previous_level: string | null;
  new_level: string | null;
  previous_division: string | null;
  new_division: string | null;
  previous_position: string | null;
  new_position: string | null;
  effective_date: string;
  notes: string | null;
}

interface VaccineRecordRow {
  id: string;
  vaccine_name: string;
  dose_number: number;
  vaccinated_at: string;
  location: string | null;
}

interface EsignConfig {
  provider: string | null;
  webhook_ready: boolean;
}

interface EsignRequestRow {
  id: string;
  contract_id: string;
  provider: string;
  provider_document_id: string;
  signer_name: string;
  signer_email: string;
  sign_url: string | null;
  status: string;
  signed_at: string | null;
  error: string | null;
  created_at: string;
}

interface EmployeePayslipRow {
  id: string;
  run_id: string;
  run_status: string;
  year: number;
  month: number;
  base_salary: number;
  gross: number;
  tax_pph21: number;
  net_pay: number;
}

// Duplikat kecil dari Employees.tsx -- pola sudah dipakai di beberapa
// halaman, bukan disentralkan (lihat komentar aslinya di sana).
const ESIGN_STATUS_BADGES: Record<string, string> = {
  terkirim: "pill p-yellow",
  dilihat: "pill p-blue",
  selesai: "pill p-green",
  ditolak: "pill p-red",
  kedaluwarsa: "pill p-gray",
  gagal: "pill p-red",
};

const DOC_TYPES = ["ktp", "npwp", "bpjs_kesehatan", "bpjs_ketenagakerjaan", "skck", "lainnya"];

const BPJS_STATUS_BADGES: Record<string, string> = {
  aktif: "pill p-green",
  nonaktif: "pill p-gray",
  menunggu: "pill p-yellow",
};

const INSURANCE_STATUS_BADGES: Record<string, string> = {
  aktif: "pill p-green",
  kedaluwarsa: "pill p-red",
  nonaktif: "pill p-gray",
};

const INSURANCE_PROVIDERS = ["prudential", "allianz", "axa", "manulife", "bri_life", "sinarmas", "other"];

const INSURANCE_PROVIDER_LABELS: Record<string, string> = {
  prudential: "Prudential",
  allianz: "Allianz",
  axa: "AXA",
  manulife: "Manulife",
  bri_life: "BRI Life",
  sinarmas: "Sinarmas",
  other: "Lainnya",
};

const TYPE_LABELS: Record<string, string> = {
  ktp: "KTP",
  npwp: "NPWP",
  bpjs_kesehatan: "BPJS Kesehatan",
  bpjs_ketenagakerjaan: "BPJS Ketenagakerjaan",
  skck: "SKCK",
  lainnya: "Lainnya",
};

const WARNING_LETTER_TYPES = ["sp1", "sp2", "sp3"];
const WARNING_LETTER_LABELS: Record<string, string> = {
  sp1: "SP 1",
  sp2: "SP 2",
  sp3: "SP 3",
};

const MOVEMENT_TYPES = ["mutasi", "promosi", "demosi", "lainnya"];

type TabKey = "ringkasan" | "kontrak" | "dokumen" | "payroll" | "riwayat" | "bpjs-asuransi" | "cuti-akun";

/** Baris properti dengan mode lihat/edit terpisah (audit UI/UX 2026-09-12:
 * field ini dulu selalu tampil sebagai form siap-ketik, terasa "selalu
 * dalam mode edit" untuk data sensitif seperti gaji & alamat KTP). Default
 * ke tampilan read-only; klik ikon pensil untuk membuka form yang sama
 * seperti sebelumnya. */
function EditableRow({
  icon,
  label,
  editing,
  onEdit,
  onCancel,
  view,
  children,
}: {
  icon: Parameters<typeof PropertyRow>[0]["icon"];
  label: string;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  view: ReactNode;
  children: ReactNode;
}) {
  return (
    <PropertyRow icon={icon} label={label}>
      {editing ? (
        <div className="flex flex-1 flex-wrap items-center gap-2">
          {children}
          <button type="button" onClick={onCancel} className="btn-ghost py-1 text-xs">
            Batal
          </button>
        </div>
      ) : (
        <>
          <span className="flex-1">{view}</span>
          <button
            type="button"
            onClick={onEdit}
            className="shrink-0 hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
            title={`Ubah ${label}`}
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        </>
      )}
    </PropertyRow>
  );
}

export default function EmployeeDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabKey>("ringkasan");
  type SummaryEditKey = "salary" | "grade" | "emergency" | "citizen_address" | "residential_address" | null;
  const [editingField, setEditingField] = useState<SummaryEditKey>(null);

  const [tteContract, setTteContract] = useState<{ id: string; name: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const docTypeRef = useRef<HTMLSelectElement>(null);
  const bpjsKesehatanFileRef = useRef<HTMLInputElement>(null);
  const bpjsKetenagakerjaanFileRef = useRef<HTMLInputElement>(null);
  const [showInsuranceForm, setShowInsuranceForm] = useState(false);
  const [showWarningLetterForm, setShowWarningLetterForm] = useState(false);
  const warningLetterFileRef = useRef<HTMLInputElement>(null);
  const [generateForContractId, setGenerateForContractId] = useState<string | null>(null);
  const [generateTemplateId, setGenerateTemplateId] = useState("");
  const [showMovementForm, setShowMovementForm] = useState(false);
  const [showVaccineForm, setShowVaccineForm] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ role: string }>("/auth/me"),
  });
  const isOpsOnly = me?.role === "operations";

  const { data: employee, isLoading, error } = useQuery({
    queryKey: ["employee-detail", id],
    queryFn: () => api.get<EmployeeRow>(`/employees/${id}`),
    enabled: Boolean(id),
  });

  const { data: contracts } = useQuery({
    queryKey: ["employee-contracts", id],
    queryFn: () => api.get<ContractRow[]>(`/employees/${id}/contracts`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: documents } = useQuery({
    queryKey: ["employee-docs", id],
    queryFn: () => api.get<HrDoc[]>(`/employees/${id}/documents`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: indexed } = useQuery({
    queryKey: ["ai-indexed"],
    queryFn: () => api.get<{ contract_id: string }[]>("/ai/contracts/indexed"),
    enabled: !isOpsOnly,
  });
  const { data: esignConfig } = useQuery({
    queryKey: ["esign-config"],
    queryFn: () => api.get<EsignConfig>("/esign/config"),
    enabled: !isOpsOnly,
  });
  const { data: esignRequests } = useQuery({
    queryKey: ["esign-requests"],
    queryFn: () => api.get<EsignRequestRow[]>("/esign/requests"),
    enabled: Boolean(esignConfig?.provider) && !isOpsOnly,
  });
  const { data: selfserviceAccounts } = useQuery({
    queryKey: ["selfservice-accounts"],
    queryFn: () => api.get<SelfserviceAccount[]>("/employees/selfservice-accounts"),
    enabled: !isOpsOnly,
  });
  const { data: clientSites } = useQuery({
    queryKey: ["client-sites-all"],
    queryFn: () => api.get<ClientSiteOption[]>("/clients/sites"),
    enabled: !isOpsOnly,
  });
  const { data: selectedBalance } = useQuery({
    queryKey: ["leave-balance", id],
    queryFn: () =>
      api.get<LeaveBalanceRow | null>(`/employees/${id}/leave-balance?year=${new Date().getFullYear()}`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: insurances } = useQuery({
    queryKey: ["employee-insurances", id],
    queryFn: () => api.get<InsuranceRow[]>(`/employees/${id}/insurances`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: warningLetters } = useQuery({
    queryKey: ["employee-warning-letters", id],
    queryFn: () => api.get<WarningLetterRow[]>(`/employees/${id}/warning-letters`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: salaryHolds } = useQuery({
    queryKey: ["salary-holds", id],
    queryFn: () => api.get<SalaryHoldRow[]>(`/payroll/employees/${id}/holds`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: payslips } = useQuery({
    queryKey: ["employee-payslips", id],
    queryFn: () => api.get<EmployeePayslipRow[]>(`/payroll/employees/${id}/payslips`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: contractTemplates } = useQuery({
    queryKey: ["contract-templates"],
    queryFn: () => api.get<ContractTemplateT[]>("/employees/contract-templates"),
    enabled: !isOpsOnly,
  });
  const { data: movements } = useQuery({
    queryKey: ["employee-movements", id],
    queryFn: () => api.get<EmployeeMovementRow[]>(`/employees/${id}/movements`),
    enabled: Boolean(id) && !isOpsOnly,
  });
  const { data: vaccineRecords } = useQuery({
    queryKey: ["employee-vaccine-records", id],
    queryFn: () => api.get<VaccineRecordRow[]>(`/employees/${id}/vaccine-records`),
    enabled: Boolean(id) && !isOpsOnly,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["employees-lookup"] });
    qc.invalidateQueries({ queryKey: ["employee-detail", id] });
    qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
    qc.invalidateQueries({ queryKey: ["selfservice-accounts"] });
  };

  const linkAccount = useMutation({
    mutationFn: ({ empId, userId }: { empId: string; userId: string | null }) =>
      api.patch(`/employees/${empId}`, { user_id: userId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["selfservice-accounts"] });
      invalidate();
    },
  });

  const updateEmployee = useMutation({
    mutationFn: ({ empId, body }: { empId: string; body: Record<string, unknown> }) =>
      api.patch(`/employees/${empId}`, body),
    onSuccess: invalidate,
  });

  const uploadBpjsCard = useMutation({
    mutationFn: ({ empId, formData }: { empId: string; formData: FormData }) =>
      api.upload(`/employees/${empId}/bpjs-card`, formData),
    onSuccess: invalidate,
  });

  const invalidateInsurances = () => qc.invalidateQueries({ queryKey: ["employee-insurances", id] });

  const createInsurance = useMutation({
    mutationFn: ({ empId, body }: { empId: string; body: Record<string, unknown> }) =>
      api.post(`/employees/${empId}/insurances`, body),
    onSuccess: () => {
      setShowInsuranceForm(false);
      invalidateInsurances();
    },
  });

  const updateInsurance = useMutation({
    mutationFn: ({ insId, body }: { insId: string; body: Record<string, unknown> }) =>
      api.patch(`/employees/insurances/${insId}`, body),
    onSuccess: invalidateInsurances,
  });

  const deleteInsurance = useMutation({
    mutationFn: (insId: string) => api.delete(`/employees/insurances/${insId}`),
    onSuccess: invalidateInsurances,
  });

  const uploadInsuranceFile = useMutation({
    mutationFn: ({ insId, kind, formData }: { insId: string; kind: "card" | "policy"; formData: FormData }) =>
      api.upload(`/employees/insurances/${insId}/${kind}`, formData),
    onSuccess: invalidateInsurances,
  });

  const addContract = useMutation({
    mutationFn: ({ empId, body }: { empId: string; body: Record<string, unknown> }) =>
      api.post(`/employees/${empId}/contracts`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employee-contracts", id] }),
  });

  const signContract = useMutation({
    mutationFn: (contractId: string) => api.post(`/employees/contracts/${contractId}/sign`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employee-contracts", id] });
      qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
    },
  });

  const uploadDoc = useMutation({
    mutationFn: ({ empId, formData }: { empId: string; formData: FormData }) =>
      api.upload(`/employees/${empId}/documents`, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employee-docs", id] });
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const createWarningLetter = useMutation({
    mutationFn: ({ empId, formData }: { empId: string; formData: FormData }) =>
      api.upload(`/employees/${empId}/warning-letters`, formData),
    onSuccess: () => {
      setShowWarningLetterForm(false);
      qc.invalidateQueries({ queryKey: ["employee-warning-letters", id] });
    },
  });

  const generateContractDocument = useMutation({
    mutationFn: ({
      contractId,
      templateId,
      fieldValues,
    }: {
      contractId: string;
      templateId: string;
      fieldValues: Record<string, string | string[]>;
    }) =>
      api.post(`/employees/contracts/${contractId}/generate-document`, {
        template_id: templateId,
        field_values: fieldValues,
      }),
    onSuccess: () => {
      setGenerateForContractId(null);
      setGenerateTemplateId("");
      qc.invalidateQueries({ queryKey: ["employee-contracts", id] });
    },
  });

  const createMovement = useMutation({
    mutationFn: ({ empId, body }: { empId: string; body: Record<string, unknown> }) =>
      api.post(`/employees/${empId}/movements`, body),
    onSuccess: () => {
      setShowMovementForm(false);
      qc.invalidateQueries({ queryKey: ["employee-movements", id] });
    },
  });

  const createVaccineRecord = useMutation({
    mutationFn: ({ empId, body }: { empId: string; body: Record<string, unknown> }) =>
      api.post(`/employees/${empId}/vaccine-records`, body),
    onSuccess: () => {
      setShowVaccineForm(false);
      qc.invalidateQueries({ queryKey: ["employee-vaccine-records", id] });
    },
  });

  const setPayrollLock = useMutation({
    mutationFn: ({ empId, locked }: { empId: string; locked: boolean }) =>
      locked ? api.post(`/employees/${empId}/payroll-lock`) : api.delete(`/employees/${empId}/payroll-lock`),
    onSuccess: invalidate,
  });

  const indexContract = useMutation({
    mutationFn: (contractId: string) => api.post(`/ai/contracts/${contractId}/index`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-indexed"] }),
  });

  const invalidateEsign = () => {
    qc.invalidateQueries({ queryKey: ["esign-requests"] });
    qc.invalidateQueries({ queryKey: ["employee-contracts", id] });
    qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
  };

  const sendEsign = useMutation({
    mutationFn: ({
      contractId,
      signerName,
      signerEmail,
    }: {
      contractId: string;
      signerName: string;
      signerEmail: string;
    }) =>
      api.post(`/esign/contracts/${contractId}/send`, { signer_name: signerName, signer_email: signerEmail }),
    onSuccess: () => {
      setTteContract(null);
      invalidateEsign();
    },
  });

  const simulateEsign = useMutation({
    mutationFn: (requestId: string) => api.post(`/esign/requests/${requestId}/simulate-complete`),
    onSuccess: invalidateEsign,
  });

  const saveBalance = useMutation({
    mutationFn: ({ empId, body }: { empId: string; body: Record<string, unknown> }) =>
      api.post<LeaveBalanceRow>(`/employees/${empId}/leave-balance`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leave-balance", id] }),
  });

  const previewPayslip = useMutation({
    mutationFn: (runId: string) => previewFile(`/payroll/runs/${runId}/employees/${id}/payslip/pdf`),
    onSuccess: setPreviewUrl,
  });
  function closePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  }
  const sendPayslipEmail = useMutation({
    mutationFn: (runId: string) => api.post(`/payroll/runs/${runId}/employees/${id}/send-payslip-email`),
  });

  if (isLoading) {
    return <p className="text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>;
  }
  if (error || !employee || !id) {
    return (
      <p className="text-sm text-red-600">
        {error ? (error as Error).message : "Karyawan tidak ditemukan."}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <Link
        to="/employees"
        className="inline-flex items-center gap-1.5 text-xs font-medium"
        style={{ color: "var(--text-muted)" }}
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Karyawan
      </Link>

      <div className="flex items-center gap-4">
        <span
          className="flex h-14 w-14 items-center justify-center rounded-full text-lg font-bold text-white"
          style={{ backgroundColor: "var(--accent)" }}
        >
          {initials(employee.full_name)}
        </span>
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold leading-tight" style={{ color: "var(--text)" }}>
            {employee.full_name}
          </h1>
          <p className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
            {employee.employee_no}
          </p>
          <div className="flex flex-wrap gap-1.5">
            <Badge tone={employee.status === "aktif" ? "success" : "neutral"}>{employee.status}</Badge>
            {employee.payroll_locked && <Badge tone="warning">Payroll Terkunci</Badge>}
          </div>
        </div>
      </div>

      {isOpsOnly ? (
        <div className="card">
          <PropertiesPanel className="max-w-2xl">
            <PropertyRow icon={Phone} label="Telepon">{employee.phone ?? "—"}</PropertyRow>
            <PropertyRow icon={Calendar} label="Tanggal Masuk">{employee.join_date ?? "—"}</PropertyRow>
            <PropertyRow icon={Banknote} label="Gaji Pokok">
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {formatRupiah(employee.base_salary)}/bulan
              </span>
            </PropertyRow>
          </PropertiesPanel>
        </div>
      ) : (
        <>
          <PillTabs
            tabs={[
              { key: "ringkasan", label: "Ringkasan" },
              { key: "kontrak", label: "Kontrak Kerja", count: contracts?.length ?? 0 },
              { key: "dokumen", label: "Dokumen HR", count: documents?.length ?? 0 },
              { key: "payroll", label: "Payroll", count: payslips?.length ?? 0 },
              { key: "riwayat", label: "Riwayat" },
              { key: "bpjs-asuransi", label: "BPJS & Asuransi" },
              { key: "cuti-akun", label: "Cuti & Akun" },
            ]}
            value={tab}
            onChange={(k) => setTab(k as TabKey)}
          />

          {tab === "ringkasan" && (
            <div className="card">
              <PropertiesPanel className="max-w-2xl">
                <PropertyRow icon={IdCard} label="No. Induk">
                  <span className="font-mono text-xs">{employee.employee_no}</span>
                </PropertyRow>
                <PropertyRow icon={Gift} label="Kode Referral">
                  <span className="font-mono text-xs">{employee.referral_code ?? "—"}</span>
                </PropertyRow>
                <PropertyRow icon={Phone} label="Telepon">{employee.phone ?? "—"}</PropertyRow>
                <PropertyRow icon={Calendar} label="Tanggal Masuk">{employee.join_date ?? "—"}</PropertyRow>
                <PropertyRow icon={Tag} label="Status">
                  <span className={`badge ${employee.status === "aktif" ? "pill p-green" : "pill p-gray"}`}>
                    {employee.status}
                  </span>
                  {employee.payroll_locked && <span className="badge pill p-yellow ml-2">Payroll Terkunci</span>}
                  <button
                    type="button"
                    onClick={() => setPayrollLock.mutate({ empId: id, locked: !employee.payroll_locked })}
                    disabled={setPayrollLock.isPending}
                    className="btn-secondary ml-2 py-0.5 text-xs"
                  >
                    {employee.payroll_locked ? "Buka Kunci Payroll" : "Kunci Payroll"}
                  </button>
                </PropertyRow>
                <EditableRow
                  icon={Banknote}
                  label="Gaji Pokok"
                  editing={editingField === "salary"}
                  onEdit={() => setEditingField("salary")}
                  onCancel={() => setEditingField(null)}
                  view={
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {formatRupiah(employee.base_salary)}/bulan
                    </span>
                  }
                >
                  <form
                    className="flex items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = new FormData(e.currentTarget);
                      updateEmployee.mutate(
                        { empId: id, body: { base_salary: Number(form.get("base_salary")) || 0 } },
                        { onSuccess: () => setEditingField(null) }
                      );
                    }}
                  >
                    <input
                      autoFocus
                      name="base_salary"
                      type="number"
                      min="0"
                      defaultValue={employee.base_salary}
                      className="input w-auto py-1 text-xs"
                    />
                    <button disabled={updateEmployee.isPending} className="btn-secondary py-1 text-xs">
                      Simpan
                    </button>
                  </form>
                </EditableRow>
                <EditableRow
                  icon={Award}
                  label="Grade / Level"
                  editing={editingField === "grade"}
                  onEdit={() => setEditingField("grade")}
                  onCancel={() => setEditingField(null)}
                  view={[employee.grade, employee.level].filter(Boolean).join(" / ") || "—"}
                >
                  <form
                    className="flex flex-wrap items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = new FormData(e.currentTarget);
                      updateEmployee.mutate(
                        {
                          empId: id,
                          body: { grade: form.get("grade") || null, level: form.get("level") || null },
                        },
                        { onSuccess: () => setEditingField(null) }
                      );
                    }}
                  >
                    <input autoFocus name="grade" defaultValue={employee.grade ?? ""} placeholder="Grade" className="input w-auto py-1 text-xs" />
                    <input name="level" defaultValue={employee.level ?? ""} placeholder="Level" className="input w-auto py-1 text-xs" />
                    <button disabled={updateEmployee.isPending} className="btn-secondary py-1 text-xs">
                      Simpan
                    </button>
                  </form>
                </EditableRow>
                <EditableRow
                  icon={AlertTriangle}
                  label="Kontak Darurat"
                  editing={editingField === "emergency"}
                  onEdit={() => setEditingField("emergency")}
                  onCancel={() => setEditingField(null)}
                  view={
                    employee.emergency_contact_name
                      ? [
                          employee.emergency_contact_name,
                          employee.emergency_contact_relation && `(${employee.emergency_contact_relation})`,
                          employee.emergency_contact_phone,
                        ]
                          .filter(Boolean)
                          .join(" · ")
                      : "—"
                  }
                >
                  <form
                    className="flex flex-wrap items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = new FormData(e.currentTarget);
                      updateEmployee.mutate(
                        {
                          empId: id,
                          body: {
                            emergency_contact_name: form.get("emergency_contact_name") || null,
                            emergency_contact_relation: form.get("emergency_contact_relation") || null,
                            emergency_contact_phone: form.get("emergency_contact_phone") || null,
                          },
                        },
                        { onSuccess: () => setEditingField(null) }
                      );
                    }}
                  >
                    <input
                      autoFocus
                      name="emergency_contact_name"
                      defaultValue={employee.emergency_contact_name ?? ""}
                      placeholder="Nama"
                      className="input w-auto py-1 text-xs"
                    />
                    <input
                      name="emergency_contact_relation"
                      defaultValue={employee.emergency_contact_relation ?? ""}
                      placeholder="Hubungan"
                      className="input w-auto py-1 text-xs"
                    />
                    <input
                      name="emergency_contact_phone"
                      defaultValue={employee.emergency_contact_phone ?? ""}
                      placeholder="Telepon"
                      className="input w-auto py-1 text-xs"
                    />
                    <button disabled={updateEmployee.isPending} className="btn-secondary py-1 text-xs">
                      Simpan
                    </button>
                  </form>
                </EditableRow>
                {(
                  [
                    { key: "citizen_address", label: "Alamat KTP", value: employee.citizen_address },
                    { key: "residential_address", label: "Alamat Domisili", value: employee.residential_address },
                  ] as const
                ).map((addr) => (
                  <EditableRow
                    key={addr.key}
                    icon={Home}
                    label={addr.label}
                    editing={editingField === addr.key}
                    onEdit={() => setEditingField(addr.key)}
                    onCancel={() => setEditingField(null)}
                    view={
                      [addr.value?.detail, addr.value?.district, addr.value?.city, addr.value?.province, addr.value?.postal_code]
                        .filter(Boolean)
                        .join(", ") || "—"
                    }
                  >
                    <form
                      className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-5"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const form = new FormData(e.currentTarget);
                        updateEmployee.mutate(
                          {
                            empId: id,
                            body: {
                              [addr.key]: {
                                province: form.get("province") || undefined,
                                city: form.get("city") || undefined,
                                district: form.get("district") || undefined,
                                postal_code: form.get("postal_code") || undefined,
                                detail: form.get("detail") || undefined,
                              },
                            },
                          },
                          { onSuccess: () => setEditingField(null) }
                        );
                      }}
                    >
                      <input autoFocus name="province" defaultValue={addr.value?.province ?? ""} placeholder="Provinsi" className="input py-1 text-xs" />
                      <input name="city" defaultValue={addr.value?.city ?? ""} placeholder="Kota/Kab." className="input py-1 text-xs" />
                      <input name="district" defaultValue={addr.value?.district ?? ""} placeholder="Kecamatan" className="input py-1 text-xs" />
                      <input name="postal_code" defaultValue={addr.value?.postal_code ?? ""} placeholder="Kode Pos" className="input py-1 text-xs" />
                      <input name="detail" defaultValue={addr.value?.detail ?? ""} placeholder="Detail" className="input py-1 text-xs" />
                      <button disabled={updateEmployee.isPending} className="btn-secondary py-1 text-xs sm:col-span-5">
                        Simpan
                      </button>
                    </form>
                  </EditableRow>
                ))}
              </PropertiesPanel>
            </div>
          )}

          {tab === "kontrak" && (
            <div className="card">
              <h2 className="font-semibold" style={{ color: "var(--text)" }}>Kontrak Kerja</h2>
              <form
                className="mt-3 flex flex-wrap gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = new FormData(e.currentTarget);
                  addContract.mutate({
                    empId: id,
                    body: { start_date: form.get("start_date") || null, end_date: form.get("end_date") || null, notes: null },
                  });
                }}
              >
                <input name="start_date" type="date" className="input w-auto" />
                <input name="end_date" type="date" className="input w-auto" />
                <button className="btn-secondary">Tambah Kontrak</button>
              </form>
              <ul className="mt-3 space-y-2">
                {(contracts ?? []).map((c) => {
                  const req = (esignRequests ?? []).find((r) => r.contract_id === c.id);
                  const active = req && ["terkirim", "dilihat"].includes(req.status);
                  const selectedContractTemplate = contractTemplates?.find((t) => t.id === generateTemplateId);
                  return (
                    <li key={c.id} className="rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium" style={{ color: "var(--text)" }}>{c.contract_no}</p>
                          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                            {c.start_date ?? "?"} s/d {c.end_date ?? "-"}
                            {c.file_name ? ` · ${c.file_name}` : ""}
                          </p>
                          {req && (
                            <div className="mt-1 flex items-center gap-2">
                              <span className={`badge border-0 ${ESIGN_STATUS_BADGES[req.status] ?? ""}`}>
                                TTE: {req.status}
                              </span>
                              {active && req.sign_url && (
                                <a
                                  href={req.sign_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-xs font-medium hover:opacity-80"
                                  style={{ color: "var(--accent)" }}
                                >
                                  Halaman tanda tangan
                                </a>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {c.file_name && (
                            <button
                              onClick={() => indexContract.mutate(c.id)}
                              disabled={indexContract.isPending}
                              className="btn-secondary text-xs"
                            >
                              {indexContract.isPending ? "Mengindeks..." : "Index AI"}
                            </button>
                          )}
                          {esignConfig?.provider && active && esignConfig.provider === "sandbox" && req && (
                            <button
                              onClick={() => simulateEsign.mutate(req.id)}
                              disabled={simulateEsign.isPending}
                              className="btn text-xs"
                            >
                              Simulasi Selesai
                            </button>
                          )}
                          {esignConfig?.provider && c.sign_status === "menunggu_ttd" && !active ? (
                            <button
                              onClick={() => setTteContract({ id: c.id, name: employee.full_name })}
                              className="btn-secondary text-xs"
                            >
                              Kirim TTE
                            </button>
                          ) : c.sign_status === "menunggu_ttd" ? (
                            <button onClick={() => signContract.mutate(c.id)} className="btn-secondary text-xs">
                              Tandai TTD
                            </button>
                          ) : (
                            <span className="badge pill p-green">ditandatangani</span>
                          )}
                        </div>
                      </div>

                      {!c.template_id && (
                        <div className="mt-2">
                          <button
                            type="button"
                            className="text-xs font-medium hover:opacity-80"
                            style={{ color: "var(--accent)" }}
                            onClick={() => {
                              setGenerateForContractId(generateForContractId === c.id ? null : c.id);
                              setGenerateTemplateId("");
                            }}
                          >
                            {generateForContractId === c.id ? "Tutup" : "Generate dari Template"}
                          </button>
                          {generateForContractId === c.id && (
                            <div className="mt-2 space-y-2 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                              <select
                                value={generateTemplateId}
                                onChange={(e) => setGenerateTemplateId(e.target.value)}
                                className="input w-auto py-1 text-xs"
                              >
                                <option value="">-- Pilih template --</option>
                                {(contractTemplates ?? []).map((t) => (
                                  <option key={t.id} value={t.id}>{t.name}</option>
                                ))}
                              </select>
                              {contractTemplates?.length === 0 && (
                                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                                  Belum ada template kontrak aktif. Buat template dulu lewat API
                                  /employees/contract-templates.
                                </p>
                              )}
                              {selectedContractTemplate && (
                                <form
                                  className="grid grid-cols-1 gap-2 sm:grid-cols-2"
                                  onSubmit={(e) => {
                                    e.preventDefault();
                                    const form = new FormData(e.currentTarget);
                                    const fieldValues: Record<string, string | string[]> = {};
                                    for (const f of selectedContractTemplate.field_schema) {
                                      if (f.type === "list") {
                                        fieldValues[f.key] = String(form.get(f.key) ?? "")
                                          .split(",")
                                          .map((v) => v.trim())
                                          .filter(Boolean);
                                      } else {
                                        fieldValues[f.key] = String(form.get(f.key) ?? "");
                                      }
                                    }
                                    generateContractDocument.mutate({
                                      contractId: c.id,
                                      templateId: selectedContractTemplate.id,
                                      fieldValues,
                                    });
                                  }}
                                >
                                  {selectedContractTemplate.field_schema.map((f) => (
                                    <input
                                      key={f.key}
                                      name={f.key}
                                      placeholder={f.type === "list" ? `${f.label} (pisah koma)` : f.label}
                                      className="input py-1 text-xs"
                                      type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                                    />
                                  ))}
                                  <button
                                    type="submit"
                                    disabled={generateContractDocument.isPending}
                                    className="btn py-1 text-xs sm:col-span-2"
                                  >
                                    {generateContractDocument.isPending ? "Membuat..." : "Generate Dokumen"}
                                  </button>
                                  {generateContractDocument.error && (
                                    <p className="text-xs text-red-600 sm:col-span-2">
                                      {(generateContractDocument.error as Error).message}
                                    </p>
                                  )}
                                </form>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
                {contracts?.length === 0 && (
                  <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada kontrak.</li>
                )}
              </ul>
              {tteContract && (
                <form
                  className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto]"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    sendEsign.mutate({
                      contractId: tteContract.id,
                      signerName: String(form.get("signer_name") || ""),
                      signerEmail: String(form.get("signer_email") || ""),
                    });
                  }}
                >
                  <input name="signer_name" required defaultValue={tteContract.name} placeholder="Nama penandatangan" className="input" />
                  <input name="signer_email" type="email" required placeholder="Email penandatangan" className="input" />
                  <div className="flex gap-2">
                    <button className="btn" disabled={sendEsign.isPending}>
                      {sendEsign.isPending ? "Mengirim..." : "Kirim"}
                    </button>
                    <button type="button" className="btn-secondary" onClick={() => setTteContract(null)}>
                      Batal
                    </button>
                  </div>
                  {sendEsign.error && (
                    <p className="text-sm text-red-600 sm:col-span-3">{(sendEsign.error as Error).message}</p>
                  )}
                </form>
              )}
            </div>
          )}

          {tab === "dokumen" && (
            <div className="card">
              <h2 className="font-semibold" style={{ color: "var(--text)" }}>Dokumen HR</h2>
              <form
                className="mt-3 flex flex-wrap gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!fileRef.current?.files?.[0]) return;
                  const fd = new FormData();
                  fd.append("file", fileRef.current.files[0]);
                  fd.append("document_type", docTypeRef.current?.value ?? "lainnya");
                  uploadDoc.mutate({ empId: id, formData: fd });
                }}
              >
                <select ref={docTypeRef} className="input w-auto">
                  {DOC_TYPES.map((t) => (
                    <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                  ))}
                </select>
                <input ref={fileRef} type="file" required className="input w-auto" />
                <button className="btn-secondary">Upload</button>
              </form>
              <ul className="mt-3 space-y-2">
                {(documents ?? []).map((d) => (
                  <li key={d.id} className="flex items-center justify-between rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
                    <div>
                      <p className="font-medium" style={{ color: "var(--text)" }}>
                        {TYPE_LABELS[d.document_type]} — v{d.version}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {d.file_name} · {(d.file_size / 1024).toFixed(0)} KB
                      </p>
                    </div>
                    <a
                      href="#"
                      onClick={async (e) => {
                        e.preventDefault();
                        const { url } = await api.get<{ url: string }>(`/employees/documents/${d.id}/download-url`);
                        window.open(url, "_blank");
                      }}
                      className="text-sm font-medium hover:opacity-80"
                      style={{ color: "var(--accent)" }}
                    >
                      Unduh
                    </a>
                  </li>
                ))}
                {documents?.length === 0 && (
                  <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada dokumen.</li>
                )}
              </ul>

              <div className="mt-6 border-t pt-4" style={{ borderColor: "var(--border)" }}>
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold" style={{ color: "var(--text)" }}>Surat Peringatan</h2>
                  <button className="btn-secondary text-xs" onClick={() => setShowWarningLetterForm(!showWarningLetterForm)}>
                    {showWarningLetterForm ? "Tutup" : "+ Tambah SP"}
                  </button>
                </div>
                {showWarningLetterForm && (
                  <form
                    className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = new FormData(e.currentTarget);
                      const file = warningLetterFileRef.current?.files?.[0];
                      if (file) form.set("file", file);
                      createWarningLetter.mutate({ empId: id, formData: form });
                    }}
                  >
                    <select name="letter_type" defaultValue="sp1" className="input">
                      {WARNING_LETTER_TYPES.map((t) => (
                        <option key={t} value={t}>{WARNING_LETTER_LABELS[t]}</option>
                      ))}
                    </select>
                    <input name="issued_at" type="date" placeholder="Tanggal terbit" className="input" />
                    <input name="reason" required placeholder="Alasan" className="input sm:col-span-2" />
                    <input ref={warningLetterFileRef} type="file" className="input sm:col-span-3" />
                    <button disabled={createWarningLetter.isPending} className="btn">Simpan</button>
                    {createWarningLetter.error && (
                      <p className="text-sm text-red-600 sm:col-span-4">{(createWarningLetter.error as Error).message}</p>
                    )}
                  </form>
                )}
                <ul className="mt-3 space-y-2">
                  {(warningLetters ?? []).map((w) => (
                    <li key={w.id} className="flex items-center justify-between rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
                      <div>
                        <p className="font-medium" style={{ color: "var(--text)" }}>
                          {WARNING_LETTER_LABELS[w.letter_type] ?? w.letter_type} — {w.reason}
                        </p>
                        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                          Terbit {w.issued_at} · berlaku s/d {w.valid_until ?? "-"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`badge ${w.is_active ? "pill p-yellow" : "pill p-gray"}`}>
                          {w.is_active ? "berlaku" : "kedaluwarsa"}
                        </span>
                        {w.file_name && (
                          <button
                            onClick={async () => {
                              const { url } = await api.get<{ url: string }>(`/employees/warning-letters/${w.id}/download-url`);
                              window.open(url, "_blank");
                            }}
                            className="text-xs font-medium hover:opacity-80"
                            style={{ color: "var(--accent)" }}
                          >
                            Unduh
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                  {warningLetters?.length === 0 && (
                    <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada SP.</li>
                  )}
                </ul>
              </div>
            </div>
          )}

          {tab === "payroll" && (
            <div className="space-y-4">
              <div className="card">
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>Riwayat Slip Gaji</h2>
                <table className="mt-3 w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      <th className="th">Periode</th>
                      <th className="th">Take Home Pay</th>
                      <th className="th">Status Run</th>
                      <th className="th">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
                    {(payslips ?? []).map((p) => (
                      <tr key={p.id}>
                        <td className="td">{String(p.month).padStart(2, "0")}/{p.year}</td>
                        <td className="td font-mono">{formatRupiah(p.net_pay)}</td>
                        <td className="td">
                          <span className={`badge ${p.run_status === "final" ? "pill p-green" : "pill p-yellow"}`}>
                            {p.run_status}
                          </span>
                        </td>
                        <td className="td whitespace-nowrap">
                          <button
                            onClick={() => previewPayslip.mutate(p.run_id)}
                            disabled={previewPayslip.isPending}
                            className="text-xs font-medium hover:opacity-80"
                            style={{ color: "var(--accent)" }}
                          >
                            Preview
                          </button>
                          {" · "}
                          <button
                            onClick={() => sendPayslipEmail.mutate(p.run_id)}
                            disabled={sendPayslipEmail.isPending}
                            className="text-xs font-medium hover:opacity-80"
                            style={{ color: "var(--accent)" }}
                          >
                            Kirim Email
                          </button>
                        </td>
                      </tr>
                    ))}
                    {payslips?.length === 0 && (
                      <tr>
                        <td colSpan={4} className="td text-center" style={{ color: "var(--text-muted)" }}>
                          Belum ada slip gaji.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                {(sendPayslipEmail.error || previewPayslip.error) && (
                  <p className="mt-2 text-sm text-red-600">
                    {((sendPayslipEmail.error ?? previewPayslip.error) as Error).message}
                  </p>
                )}
                {sendPayslipEmail.isSuccess && (
                  <p className="mt-2 text-sm" style={{ color: "var(--text-muted)" }}>Email slip gaji terkirim.</p>
                )}
              </div>

              <div className="card">
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>Gaji Tertahan</h2>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Riwayat gaji yang ditahan/dicairkan lewat grid Saltab di halaman Payroll.
                </p>
                <ul className="mt-3 space-y-2">
                  {(salaryHolds ?? []).map((h) => (
                    <li key={h.id} className="flex items-center justify-between rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
                      <div>
                        <p className="font-medium" style={{ color: "var(--text)" }}>
                          {formatRupiah(h.amount)} — {h.reason}
                        </p>
                        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                          Ditahan {new Date(h.held_at).toLocaleDateString("id-ID")}
                          {h.released_at && ` · Dicairkan ${new Date(h.released_at).toLocaleDateString("id-ID")}`}
                        </p>
                      </div>
                      <span className={`pill ${h.status === "held" ? "p-yellow" : "p-green"}`}>
                        {h.status === "held" ? "ditahan" : "dicairkan"}
                      </span>
                    </li>
                  ))}
                  {salaryHolds?.length === 0 && (
                    <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada riwayat gaji tertahan.</li>
                  )}
                </ul>
              </div>

              {previewUrl && (
                <div
                  className="fixed inset-0 z-50 flex items-start justify-center pt-[6vh]"
                  style={{ background: "rgba(15,15,15,0.45)" }}
                  onClick={closePreview}
                >
                  <div
                    className="flex h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-md"
                    style={{ backgroundColor: "var(--bg-elevated)", boxShadow: "0 12px 40px rgba(15,15,15,0.25)", border: "1px solid var(--border)" }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="flex items-center justify-between px-4 py-2" style={{ borderBottom: "1px solid var(--border)" }}>
                      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Preview Slip Gaji</p>
                      <button onClick={closePreview} className="text-xs font-medium hover:underline" style={{ color: "var(--text-muted)" }}>
                        Tutup
                      </button>
                    </div>
                    <iframe src={previewUrl} title="Preview Slip Gaji" className="flex-1" />
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === "riwayat" && (
            <div className="space-y-4">
              <div className="card">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold" style={{ color: "var(--text)" }}>Riwayat Mutasi</h2>
                  <button className="btn-secondary text-xs" onClick={() => setShowMovementForm(!showMovementForm)}>
                    {showMovementForm ? "Tutup" : "+ Tambah Mutasi"}
                  </button>
                </div>
                {showMovementForm && (
                  <form
                    className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = new FormData(e.currentTarget);
                      createMovement.mutate({
                        empId: id,
                        body: {
                          movement_type: form.get("movement_type"),
                          previous_grade: form.get("previous_grade") || null,
                          new_grade: form.get("new_grade") || null,
                          previous_level: form.get("previous_level") || null,
                          new_level: form.get("new_level") || null,
                          previous_division: form.get("previous_division") || null,
                          new_division: form.get("new_division") || null,
                          previous_position: form.get("previous_position") || null,
                          new_position: form.get("new_position") || null,
                          effective_date: form.get("effective_date"),
                          notes: form.get("notes") || null,
                        },
                      });
                    }}
                  >
                    <select name="movement_type" defaultValue="mutasi" className="input">
                      {MOVEMENT_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <input name="effective_date" type="date" required className="input" />
                    <input name="notes" placeholder="Catatan" className="input" />
                    <input name="previous_grade" placeholder="Grade lama" className="input" />
                    <input name="new_grade" placeholder="Grade baru" className="input" />
                    <input name="previous_level" placeholder="Level lama" className="input" />
                    <input name="new_level" placeholder="Level baru" className="input" />
                    <input name="previous_division" placeholder="Divisi lama" className="input" />
                    <input name="new_division" placeholder="Divisi baru" className="input" />
                    <input name="previous_position" placeholder="Posisi lama" className="input" />
                    <input name="new_position" placeholder="Posisi baru" className="input" />
                    <button disabled={createMovement.isPending} className="btn sm:col-span-3">Simpan</button>
                  </form>
                )}
                <ul className="mt-3 space-y-2">
                  {(movements ?? []).map((m) => (
                    <li key={m.id} className="rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
                      <p className="font-medium capitalize" style={{ color: "var(--text)" }}>
                        {m.movement_type} · {m.effective_date}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {[
                          m.previous_grade || m.new_grade ? `Grade: ${m.previous_grade ?? "-"} → ${m.new_grade ?? "-"}` : null,
                          m.previous_level || m.new_level ? `Level: ${m.previous_level ?? "-"} → ${m.new_level ?? "-"}` : null,
                          m.previous_division || m.new_division ? `Divisi: ${m.previous_division ?? "-"} → ${m.new_division ?? "-"}` : null,
                          m.previous_position || m.new_position ? `Posisi: ${m.previous_position ?? "-"} → ${m.new_position ?? "-"}` : null,
                        ].filter(Boolean).join(" · ") || m.notes || "-"}
                      </p>
                    </li>
                  ))}
                  {movements?.length === 0 && (
                    <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada riwayat mutasi.</li>
                  )}
                </ul>
              </div>

              <div className="card">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold" style={{ color: "var(--text)" }}>Vaksinasi</h2>
                  <button className="btn-secondary text-xs" onClick={() => setShowVaccineForm(!showVaccineForm)}>
                    {showVaccineForm ? "Tutup" : "+ Tambah Vaksinasi"}
                  </button>
                </div>
                {showVaccineForm && (
                  <form
                    className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = new FormData(e.currentTarget);
                      createVaccineRecord.mutate({
                        empId: id,
                        body: {
                          vaccine_name: form.get("vaccine_name"),
                          dose_number: Number(form.get("dose_number")) || 1,
                          vaccinated_at: form.get("vaccinated_at"),
                          location: form.get("location") || null,
                        },
                      });
                    }}
                  >
                    <input name="vaccine_name" required placeholder="Nama vaksin" className="input" />
                    <input name="dose_number" type="number" min={1} defaultValue={1} placeholder="Dosis ke-" className="input" />
                    <input name="vaccinated_at" type="date" required className="input" />
                    <input name="location" placeholder="Lokasi" className="input" />
                    <button disabled={createVaccineRecord.isPending} className="btn sm:col-span-4">Simpan</button>
                  </form>
                )}
                <ul className="mt-3 space-y-2">
                  {(vaccineRecords ?? []).map((v) => (
                    <li key={v.id} className="rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
                      <p className="font-medium" style={{ color: "var(--text)" }}>
                        {v.vaccine_name} · dosis {v.dose_number}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {v.vaccinated_at} {v.location ? `· ${v.location}` : ""}
                      </p>
                    </li>
                  ))}
                  {vaccineRecords?.length === 0 && (
                    <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada catatan vaksinasi.</li>
                  )}
                </ul>
              </div>
            </div>
          )}

          {tab === "bpjs-asuransi" && (
            <div className="space-y-4">
              <div className="card">
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>BPJS</h2>
                <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {(
                    [
                      {
                        type: "kesehatan",
                        label: "BPJS Kesehatan",
                        no: employee.bpjs_kesehatan_no,
                        statusVal: employee.bpjs_kesehatan_status,
                        validUntil: employee.bpjs_kesehatan_valid_until,
                        cardKey: employee.bpjs_kesehatan_card_key,
                        fileRef: bpjsKesehatanFileRef,
                      },
                      {
                        type: "ketenagakerjaan",
                        label: "BPJS Ketenagakerjaan",
                        no: employee.bpjs_ketenagakerjaan_no,
                        statusVal: employee.bpjs_ketenagakerjaan_status,
                        validUntil: employee.bpjs_ketenagakerjaan_valid_until,
                        cardKey: employee.bpjs_ketenagakerjaan_card_key,
                        fileRef: bpjsKetenagakerjaanFileRef,
                      },
                    ] as const
                  ).map((b) => (
                    <div key={b.type} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{b.label}</p>
                        {b.statusVal && (
                          <span className={`badge ${BPJS_STATUS_BADGES[b.statusVal] ?? "pill p-gray"}`}>{b.statusVal}</span>
                        )}
                      </div>
                      <p className="mt-1 font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                        {b.no ?? "Nomor belum diisi"}
                      </p>
                      <form
                        className="mt-2 flex flex-wrap items-center gap-2"
                        onSubmit={(e) => {
                          e.preventDefault();
                          const form = new FormData(e.currentTarget);
                          updateEmployee.mutate({
                            empId: id,
                            body: {
                              [`bpjs_${b.type}_no`]: form.get("no") || null,
                              [`bpjs_${b.type}_status`]: form.get("status") || null,
                              [`bpjs_${b.type}_valid_until`]: form.get("valid_until") || null,
                            },
                          });
                        }}
                      >
                        <input name="no" defaultValue={b.no ?? ""} placeholder="Nomor BPJS" className="input w-auto py-1 text-xs" />
                        <select name="status" defaultValue={b.statusVal ?? ""} className="input w-auto py-1 text-xs">
                          <option value="">—</option>
                          <option value="aktif">aktif</option>
                          <option value="nonaktif">nonaktif</option>
                          <option value="menunggu">menunggu</option>
                        </select>
                        <input name="valid_until" type="date" defaultValue={b.validUntil ?? ""} className="input w-auto py-1 text-xs" title="Berlaku hingga" />
                        <button disabled={updateEmployee.isPending} className="btn-secondary py-1 text-xs">Simpan</button>
                      </form>
                      <form
                        className="mt-2 flex flex-wrap items-center gap-2"
                        onSubmit={(e) => {
                          e.preventDefault();
                          if (!b.fileRef.current?.files?.[0]) return;
                          const fd = new FormData();
                          fd.append("file", b.fileRef.current.files[0]);
                          fd.append("bpjs_type", b.type);
                          uploadBpjsCard.mutate({ empId: id, formData: fd });
                          b.fileRef.current.value = "";
                        }}
                      >
                        <input ref={b.fileRef} type="file" required className="input w-auto py-1 text-xs" />
                        <button disabled={uploadBpjsCard.isPending} className="btn-secondary py-1 text-xs">Upload Kartu</button>
                        {b.cardKey && (
                          <button
                            type="button"
                            onClick={async () => {
                              const { url } = await api.get<{ url: string }>(`/employees/${id}/bpjs-card/${b.type}/download-url`);
                              window.open(url, "_blank");
                            }}
                            className="text-xs font-medium hover:opacity-80"
                            style={{ color: "var(--accent)" }}
                          >
                            Lihat Kartu
                          </button>
                        )}
                      </form>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold" style={{ color: "var(--text)" }}>Asuransi</h2>
                  <button className="btn-secondary text-xs" onClick={() => setShowInsuranceForm(!showInsuranceForm)}>
                    {showInsuranceForm ? "Tutup" : "+ Tambah Polis"}
                  </button>
                </div>
                {showInsuranceForm && (
                  <form
                    className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = new FormData(e.currentTarget);
                      createInsurance.mutate({
                        empId: id,
                        body: {
                          provider: form.get("provider"),
                          policy_no: form.get("policy_no"),
                          start_date: form.get("start_date") || null,
                          valid_until: form.get("valid_until") || null,
                        },
                      });
                    }}
                  >
                    <select name="provider" defaultValue="prudential" className="input">
                      {INSURANCE_PROVIDERS.map((p) => (
                        <option key={p} value={p}>{INSURANCE_PROVIDER_LABELS[p]}</option>
                      ))}
                    </select>
                    <input name="policy_no" required placeholder="No. Polis" className="input" />
                    <input name="start_date" type="date" placeholder="Mulai" className="input" />
                    <input name="valid_until" type="date" placeholder="Berlaku hingga" className="input" />
                    <button disabled={createInsurance.isPending} className="btn sm:col-span-4">Simpan Polis</button>
                    {createInsurance.error && (
                      <p className="text-sm text-red-600 sm:col-span-4">{(createInsurance.error as Error).message}</p>
                    )}
                  </form>
                )}
                <ul className="mt-3 space-y-2">
                  {(insurances ?? []).map((ins) => (
                    <li key={ins.id} className="rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="font-medium" style={{ color: "var(--text)" }}>
                            {INSURANCE_PROVIDER_LABELS[ins.provider] ?? ins.provider} · {ins.policy_no}
                          </p>
                          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                            {ins.start_date ?? "?"} s/d {ins.valid_until ?? "-"}
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            value={ins.status}
                            disabled={updateInsurance.isPending}
                            onChange={(e) => updateInsurance.mutate({ insId: ins.id, body: { status: e.target.value } })}
                            className={`badge cursor-pointer border-0 ${INSURANCE_STATUS_BADGES[ins.status] ?? "pill p-gray"}`}
                          >
                            <option value="aktif">aktif</option>
                            <option value="kedaluwarsa">kedaluwarsa</option>
                            <option value="nonaktif">nonaktif</option>
                          </select>
                          <button
                            onClick={() =>
                              confirmToast("Hapus polis ini?", () => deleteInsurance.mutate(ins.id), {
                                confirmLabel: "Hapus",
                              })
                            }
                            className="text-xs font-medium text-rose-600 hover:text-rose-800"
                          >
                            Hapus
                          </button>
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                        <label className="cursor-pointer font-medium hover:opacity-80" style={{ color: "var(--accent)" }}>
                          {ins.card_object_key ? "Ganti Kartu" : "Upload Kartu"}
                          <input
                            type="file"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (!file) return;
                              const fd = new FormData();
                              fd.append("file", file);
                              uploadInsuranceFile.mutate({ insId: ins.id, kind: "card", formData: fd });
                              e.target.value = "";
                            }}
                          />
                        </label>
                        {ins.card_object_key && (
                          <button
                            onClick={async () => {
                              const { url } = await api.get<{ url: string }>(`/employees/insurances/${ins.id}/card/download-url`);
                              window.open(url, "_blank");
                            }}
                            className="hover:opacity-80"
                            style={{ color: "var(--text-muted)" }}
                          >
                            Lihat Kartu
                          </button>
                        )}
                        <label className="cursor-pointer font-medium hover:opacity-80" style={{ color: "var(--accent)" }}>
                          {ins.policy_object_key ? "Ganti Polis" : "Upload Polis"}
                          <input
                            type="file"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (!file) return;
                              const fd = new FormData();
                              fd.append("file", file);
                              uploadInsuranceFile.mutate({ insId: ins.id, kind: "policy", formData: fd });
                              e.target.value = "";
                            }}
                          />
                        </label>
                        {ins.policy_object_key && (
                          <button
                            onClick={async () => {
                              const { url } = await api.get<{ url: string }>(`/employees/insurances/${ins.id}/policy/download-url`);
                              window.open(url, "_blank");
                            }}
                            className="hover:opacity-80"
                            style={{ color: "var(--text-muted)" }}
                          >
                            Lihat Polis
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                  {insurances?.length === 0 && (
                    <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada polis asuransi.</li>
                  )}
                </ul>
              </div>
            </div>
          )}

          {tab === "cuti-akun" && (
            <div className="space-y-4">
              <div className="card">
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>Jatah Cuti Tahunan</h2>
                <form
                  className="mt-3 flex flex-wrap items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    saveBalance.mutate({
                      empId: id,
                      body: { year: Number(form.get("year")), total_days: Number(form.get("total_days")) },
                    });
                  }}
                >
                  <input name="year" type="number" required defaultValue={new Date().getFullYear()} className="input w-24" />
                  <input
                    key={`${id}-${selectedBalance?.total_days ?? "x"}`}
                    name="total_days"
                    type="number"
                    min={0}
                    required
                    placeholder="Total hari"
                    defaultValue={selectedBalance?.total_days ?? ""}
                    className="input w-32"
                  />
                  <button disabled={saveBalance.isPending} className="btn-secondary">Simpan Jatah</button>
                </form>
                {selectedBalance && (
                  <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    Terpakai {selectedBalance.used_days} hari · sisa{" "}
                    <span className="font-semibold">{selectedBalance.remaining}</span> dari{" "}
                    {selectedBalance.total_days} hari ({selectedBalance.year})
                  </p>
                )}
                {saveBalance.error && (
                  <p className="mt-2 text-sm text-red-600">{(saveBalance.error as Error).message}</p>
                )}
              </div>

              <div className="card">
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>Akun Portal Karyawan</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                  Tautkan akun login (role karyawan) agar karyawan bisa memakai Portal Saya: profil, slip gaji, cuti, dan dokumen.
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {employee.user_id ? (
                    <>
                      <span className="badge pill p-green">Akun portal aktif</span>
                      <button
                        onClick={() => linkAccount.mutate({ empId: employee.id, userId: null })}
                        disabled={linkAccount.isPending}
                        className="btn-secondary text-xs"
                      >
                        Lepas Tautan
                      </button>
                    </>
                  ) : (selfserviceAccounts ?? []).length > 0 ? (
                    <form
                      className="flex flex-wrap gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const form = new FormData(e.currentTarget);
                        const userId = String(form.get("user_id") || "");
                        if (userId) {
                          linkAccount.mutate({ empId: employee.id, userId });
                          e.currentTarget.reset();
                        }
                      }}
                    >
                      <select name="user_id" required className="input w-auto">
                        {(selfserviceAccounts ?? []).map((a) => (
                          <option key={a.id} value={a.id}>{a.email} · {a.full_name}</option>
                        ))}
                      </select>
                      <button disabled={linkAccount.isPending} className="btn-secondary">Aktifkan Portal</button>
                    </form>
                  ) : (
                    <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                      Belum ada akun karyawan tersedia — buat lewat menu Pengguna dengan role &ldquo;karyawan&rdquo;.
                    </p>
                  )}
                </div>
                {linkAccount.error && (
                  <p className="mt-2 text-sm text-red-600">{(linkAccount.error as Error).message}</p>
                )}
              </div>

              <div className="card">
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>
                  Lokasi Kerja (Geofencing Absensi)
                </h2>
                <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                  Kosong = absen bebas di mana saja. Terisi = wajib clock-in/out dalam radius
                  lokasi itu (dikelola di halaman Klien, kartu &ldquo;Lokasi Kantor&rdquo;).
                </p>
                <select
                  key={`site-${employee.site_id ?? "none"}`}
                  defaultValue={employee.site_id ?? ""}
                  className="input mt-3 w-auto"
                  onChange={(e) =>
                    updateEmployee.mutate({
                      empId: employee.id,
                      body: { site_id: e.target.value || null },
                    })
                  }
                >
                  <option value="">Bebas (tanpa lokasi)</option>
                  {(clientSites ?? []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.client_name} — {s.name} (radius {s.radius_meters}m)
                    </option>
                  ))}
                </select>
                {updateEmployee.error && (
                  <p className="mt-2 text-sm text-red-600">
                    {(updateEmployee.error as Error).message}
                  </p>
                )}
              </div>

              <div className="card">
                <h2 className="font-semibold" style={{ color: "var(--text)" }}>Shift Kerja</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                  Shift tetap default, ditampilkan di halaman Absensi Portal Saya. Kosong = shift
                  belum diatur (bukan jadwal rotasi per-hari).
                </p>
                <form
                  className="mt-3 flex flex-wrap items-end gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    updateEmployee.mutate({
                      empId: employee.id,
                      body: {
                        shift_start_time: form.get("shift_start_time") || null,
                        shift_end_time: form.get("shift_end_time") || null,
                      },
                    });
                  }}
                >
                  <div className="flex flex-col gap-1">
                    <label className="text-xs" style={{ color: "var(--text-muted)" }}>Mulai</label>
                    <input
                      name="shift_start_time"
                      type="time"
                      defaultValue={employee.shift_start_time ?? ""}
                      className="input w-auto"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs" style={{ color: "var(--text-muted)" }}>Selesai</label>
                    <input
                      name="shift_end_time"
                      type="time"
                      defaultValue={employee.shift_end_time ?? ""}
                      className="input w-auto"
                    />
                  </div>
                  <button type="submit" disabled={updateEmployee.isPending} className="btn-secondary">
                    Simpan Shift
                  </button>
                </form>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
