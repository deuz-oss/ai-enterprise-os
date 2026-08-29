import { FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile } from "../api/client";
import { CalloutBlock, PageHeader, PropertiesPanel, PropertyRow } from "../components/notion";

export interface EmployeeRow {
  id: string;
  employee_no: string;
  full_name: string;
  phone: string | null;
  ktp_no: string | null;
  npwp_no: string | null;
  join_date: string | null;
  status: string;
  user_id: string | null;
  bpjs_kesehatan_no: string | null;
  bpjs_ketenagakerjaan_no: string | null;
  bpjs_kesehatan_status: string | null;
  bpjs_ketenagakerjaan_status: string | null;
  bpjs_kesehatan_valid_until: string | null;
  bpjs_ketenagakerjaan_valid_until: string | null;
  bpjs_kesehatan_card_key: string | null;
  bpjs_ketenagakerjaan_card_key: string | null;
}

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

interface LeaveBalanceRow {
  id: string;
  year: number;
  total_days: number;
  used_days: number;
  remaining: number;
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

interface ContractRow {
  id: string;
  contract_no: string;
  start_date: string | null;
  end_date: string | null;
  sign_status: string;
  signed_at: string | null;
  file_name: string | null;
}

interface ExpiringContract {
  contract_id: string;
  contract_no: string;
  employee_id: string;
  employee_name: string;
  end_date: string;
  days_left: number;
}

interface HrDoc {
  id: string;
  document_type: string;
  title: string;
  version: number;
  file_name: string;
  file_size: number;
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

const ESIGN_STATUS_BADGES: Record<string, string> = {
  terkirim: "pill p-yellow",
  dilihat: "pill p-blue",
  selesai: "pill p-green",
  ditolak: "pill p-red",
  kedaluwarsa: "pill p-gray",
  gagal: "pill p-red",
};

const DOC_TYPES = ["ktp", "npwp", "bpjs_kesehatan", "bpjs_ketenagakerjaan", "lainnya"];

// BPJS + Asuransi — PRD v3.0 §5 Workforce Cloud.
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

const INSURANCE_PROVIDERS = [
  "prudential",
  "allianz",
  "axa",
  "manulife",
  "bri_life",
  "sinarmas",
  "other",
];

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
  lainnya: "Lainnya",
};

export default function Employees() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [askResult, setAskResult] = useState<AskResult | null>(null);
  const [tteContract, setTteContract] = useState<{ id: string; name: string } | null>(null);
  const [exportPeriod, setExportPeriod] = useState({
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const docTypeRef = useRef<HTMLSelectElement>(null);
  const bpjsKesehatanFileRef = useRef<HTMLInputElement>(null);
  const bpjsKetenagakerjaanFileRef = useRef<HTMLInputElement>(null);
  const [showInsuranceForm, setShowInsuranceForm] = useState(false);

  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => api.get<EmployeeRow[]>("/employees"),
  });
  const { data: contracts } = useQuery({
    queryKey: ["employee-contracts", selectedId],
    queryFn: () => api.get<ContractRow[]>(`/employees/${selectedId}/contracts`),
    enabled: Boolean(selectedId),
  });
  const { data: documents } = useQuery({
    queryKey: ["employee-docs", selectedId],
    queryFn: () => api.get<HrDoc[]>(`/employees/${selectedId}/documents`),
    enabled: Boolean(selectedId),
  });
  const { data: expiring } = useQuery({
    queryKey: ["contracts-expiring"],
    queryFn: () =>
      api.get<ExpiringContract[]>("/employees/contracts/expiring?within_days=30"),
  });
  const { data: indexed } = useQuery({
    queryKey: ["ai-indexed"],
    queryFn: () => api.get<IndexedContract[]>("/ai/contracts/indexed"),
  });
  const { data: esignConfig } = useQuery({
    queryKey: ["esign-config"],
    queryFn: () => api.get<EsignConfig>("/esign/config"),
  });
  const { data: esignRequests } = useQuery({
    queryKey: ["esign-requests"],
    queryFn: () => api.get<EsignRequestRow[]>("/esign/requests"),
    enabled: Boolean(esignConfig?.provider),
  });
  const { data: selfserviceAccounts } = useQuery({
    queryKey: ["selfservice-accounts"],
    queryFn: () =>
      api.get<SelfserviceAccount[]>("/employees/selfservice-accounts"),
  });
  const { data: leaveRequests } = useQuery({
    queryKey: ["leave-requests"],
    queryFn: () => api.get<LeaveRequestRow[]>("/employees/leave-requests"),
  });
  const { data: selectedBalance } = useQuery({
    queryKey: ["leave-balance", selectedId],
    queryFn: () =>
      api.get<LeaveBalanceRow | null>(
        `/employees/${selectedId}/leave-balance?year=${new Date().getFullYear()}`
      ),
    enabled: Boolean(selectedId),
  });
  const { data: attendanceCorrections } = useQuery({
    queryKey: ["attendance-corrections"],
    queryFn: () => api.get<AttendanceCorrectionRow[]>("/employees/attendance-corrections"),
  });
  const { data: insurances } = useQuery({
    queryKey: ["employee-insurances", selectedId],
    queryFn: () => api.get<InsuranceRow[]>(`/employees/${selectedId}/insurances`),
    enabled: Boolean(selectedId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["employees"] });
    qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
    qc.invalidateQueries({ queryKey: ["selfservice-accounts"] });
  };

  const linkAccount = useMutation({
    mutationFn: ({ id, userId }: { id: string; userId: string | null }) =>
      api.patch(`/employees/${id}`, { user_id: userId }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["selfservice-accounts"] }),
  });

  const updateBpjsStatus = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/employees/${id}`, body),
    onSuccess: invalidate,
  });

  const uploadBpjsCard = useMutation({
    mutationFn: ({ id, formData }: { id: string; formData: FormData }) =>
      api.upload(`/employees/${id}/bpjs-card`, formData),
    onSuccess: invalidate,
  });

  const invalidateInsurances = () =>
    qc.invalidateQueries({ queryKey: ["employee-insurances", selectedId] });

  const createInsurance = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.post(`/employees/${id}/insurances`, body),
    onSuccess: () => {
      setShowInsuranceForm(false);
      invalidateInsurances();
    },
  });

  const updateInsurance = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/employees/insurances/${id}`, body),
    onSuccess: invalidateInsurances,
  });

  const deleteInsurance = useMutation({
    mutationFn: (id: string) => api.delete(`/employees/insurances/${id}`),
    onSuccess: invalidateInsurances,
  });

  const uploadInsuranceFile = useMutation({
    mutationFn: ({ id, kind, formData }: { id: string; kind: "card" | "policy"; formData: FormData }) =>
      api.upload(`/employees/insurances/${id}/${kind}`, formData),
    onSuccess: invalidateInsurances,
  });

  const createEmployee = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/employees", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const addContract = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.post(`/employees/${id}/contracts`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employee-contracts", selectedId] }),
  });

  const signContract = useMutation({
    mutationFn: (contractId: string) =>
      api.post(`/employees/contracts/${contractId}/sign`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employee-contracts", selectedId] });
      qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
    },
  });

  const uploadDoc = useMutation({
    mutationFn: ({ id, formData }: { id: string; formData: FormData }) =>
      api.upload(`/employees/${id}/documents`, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employee-docs", selectedId] });
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const indexContract = useMutation({
    mutationFn: (contractId: string) => api.post(`/ai/contracts/${contractId}/index`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai-indexed"] }),
  });

  const askAi = useMutation({
    mutationFn: (body: { question: string; employee_id: string | null }) =>
      api.post<AskResult>("/ai/contracts/ask", body),
    onSuccess: (data) => setAskResult(data),
  });

  const invalidateEsign = () => {
    qc.invalidateQueries({ queryKey: ["esign-requests"] });
    qc.invalidateQueries({ queryKey: ["employee-contracts", selectedId] });
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
      api.post(`/esign/contracts/${contractId}/send`, {
        signer_name: signerName,
        signer_email: signerEmail,
      }),
    onSuccess: () => {
      setTteContract(null);
      invalidateEsign();
    },
  });

  const simulateEsign = useMutation({
    mutationFn: (requestId: string) =>
      api.post(`/esign/requests/${requestId}/simulate-complete`),
    onSuccess: invalidateEsign,
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

  const saveBalance = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.post<LeaveBalanceRow>(`/employees/${id}/leave-balance`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leave-balance"] }),
  });

  const selected = employees?.find((e) => e.id === selectedId);

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
        <PageHeader emoji="💼" title="Karyawan" />
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
          <p className="self-center text-xs" style={{ color: "var(--n-text-muted)" }}>
            Nomor induk karyawan dibuat otomatis bila dikosongkan.
          </p>
          <button type="submit" disabled={createEmployee.isPending} className="btn sm:col-span-3">
            Simpan Karyawan
          </button>
        </form>
      )}

      {(expiring ?? []).length > 0 && (
        <CalloutBlock emoji="⏰" tone="warning">
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

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Tanya Kontrak (AI)</h2>
          <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>
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
            if (q) askAi.mutate({ question: q, employee_id: selectedId });
          }}
        >
          <input
            name="question"
            required
            placeholder={
              selectedId
                ? "Contoh: Berapa gaji pokok karyawan ini?"
                : "Tanyakan apa pun tentang kontrak yang sudah diindeks"
            }
            className="input flex-1"
          />
          <button className="btn" disabled={askAi.isPending || !indexed?.length}>
            {askAi.isPending ? "AI mencari..." : "Tanya"}
          </button>
        </form>
        {selectedId && (
          <p className="mt-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
            Pertanyaan dibatasi pada kontrak karyawan yang sedang dipilih.
          </p>
        )}
        {askAi.error && (
          <p className="mt-2 text-sm text-red-600">{(askAi.error as Error).message}</p>
        )}
        {askResult && (
          <div className="mt-3 rounded-lg border p-4" style={{ backgroundColor: "var(--accent-tint)", borderColor: "var(--n-border)" }}>
            <p className="text-sm" style={{ color: "var(--n-text)" }}>{askResult.answer}</p>
            {askResult.sources.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
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

      {(attendanceCorrections ?? []).length > 0 && (
        <div className="card overflow-x-auto p-0">
          <div className="border-b p-4" style={{ borderColor: "var(--n-border)" }}>
            <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Koreksi Absensi (Portal)</h2>
          </div>
          <table className="w-full">
            <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
              <tr>
                <th className="th">Karyawan</th>
                <th className="th">Periode</th>
                <th className="th">Usulan</th>
                <th className="th">Alasan</th>
                <th className="th">Status</th>
                <th className="th">Keputusan</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
              {(attendanceCorrections ?? []).map((c) => {
                const emp = employees?.find((e) => e.id === c.employee_id);
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
          <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4" style={{ borderColor: "var(--n-border)" }}>
            <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Pengajuan Cuti / Izin</h2>
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
            <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
              <tr>
                <th className="th">Karyawan</th>
                <th className="th">Jenis</th>
                <th className="th">Tanggal</th>
                <th className="th">Alasan</th>
                <th className="th">Status</th>
                <th className="th">Keputusan</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
              {(leaveRequests ?? []).map((lv) => {
                const emp = employees?.find((e) => e.id === lv.employee_id);
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

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">No. Induk</th>
              <th className="th">Nama</th>
              <th className="th">Telepon</th>
              <th className="th">Masuk</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(employees ?? []).map((e) => (
              <tr
                key={e.id}
                onClick={() => setSelectedId(e.id === selectedId ? null : e.id)}
                className="cursor-pointer hover:bg-[var(--n-hover)] transition-colors"
                style={{
                  backgroundColor: selectedId === e.id ? "var(--accent-tint)" : undefined,
                }}
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
            {employees?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada karyawan.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <>
        {/* Header properti ala Notion untuk karyawan terpilih */}
        {selected && (
          <div className="card">
            <h1 className="flex items-center gap-3 text-2xl font-bold text-notion">
              <span className="text-4xl leading-none">👤</span>
              {selected.full_name}
            </h1>
            <PropertiesPanel className="mt-4 max-w-2xl">
              <PropertyRow icon="🆔" label="No. Induk">
                <span className="font-mono text-xs">{selected.employee_no}</span>
              </PropertyRow>
              <PropertyRow icon="📞" label="Telepon">
                {selected.phone ?? "—"}
              </PropertyRow>
              <PropertyRow icon="📅" label="Tanggal Masuk">
                {selected.join_date ?? "—"}
              </PropertyRow>
              <PropertyRow icon="🏷️" label="Status">
                <span
                  className={`badge ${
                    selected.status === "aktif" ? "pill p-green" : "pill p-gray"
                  }`}
                >
                  {selected.status}
                </span>
              </PropertyRow>
            </PropertiesPanel>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="card">
            <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Kontrak Kerja</h2>
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                addContract.mutate({
                  id: selectedId,
                  body: {
                    start_date: form.get("start_date") || null,
                    end_date: form.get("end_date") || null,
                    notes: null,
                  },
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
                return (
                  <li
                    key={c.id}
                    className="flex items-center justify-between rounded-lg p-3 text-sm"
                    style={{ backgroundColor: "var(--n-hover)" }}
                  >
                    <div>
                      <p className="font-medium" style={{ color: "var(--n-text)" }}>{c.contract_no}</p>
                      <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                        {c.start_date ?? "?"} s/d {c.end_date ?? "-"}
                        {c.file_name ? ` · ${c.file_name}` : ""}
                      </p>
                      {req && (
                        <div className="mt-1 flex items-center gap-2">
                          <span
                            className={`badge border-0 ${
                              ESIGN_STATUS_BADGES[req.status] ?? ""
                            }`}
                          >
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
                      {esignConfig?.provider &&
                        active &&
                        esignConfig.provider === "sandbox" &&
                        req && (
                          <button
                            onClick={() => simulateEsign.mutate(req.id)}
                            disabled={simulateEsign.isPending}
                            className="btn text-xs"
                          >
                            Simulasi Selesai
                          </button>
                        )}
                      {esignConfig?.provider &&
                      c.sign_status === "menunggu_ttd" &&
                      !active ? (
                        <button
                          onClick={() =>
                            setTteContract({
                              id: c.id,
                              name:
                                employees?.find((e) => e.id === selectedId)?.full_name ?? "",
                            })
                          }
                          className="btn-secondary text-xs"
                        >
                          Kirim TTE
                        </button>
                      ) : c.sign_status === "menunggu_ttd" ? (
                        <button
                          onClick={() => signContract.mutate(c.id)}
                          className="btn-secondary text-xs"
                        >
                          Tandai TTD
                        </button>
                      ) : (
                        <span className="badge pill p-green">
                          ditandatangani
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
              {contracts?.length === 0 && (
                <li className="text-sm" style={{ color: "var(--n-text-muted)" }}>Belum ada kontrak.</li>
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
                <input
                  name="signer_name"
                  required
                  defaultValue={tteContract.name}
                  placeholder="Nama penandatangan"
                  className="input"
                />
                <input
                  name="signer_email"
                  type="email"
                  required
                  placeholder="Email penandatangan"
                  className="input"
                />
                <div className="flex gap-2">
                  <button className="btn" disabled={sendEsign.isPending}>
                    {sendEsign.isPending ? "Mengirim..." : "Kirim"}
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setTteContract(null)}
                  >
                    Batal
                  </button>
                </div>
                {sendEsign.error && (
                  <p className="text-sm text-red-600 sm:col-span-3">
                    {(sendEsign.error as Error).message}
                  </p>
                )}
              </form>
            )}
          </div>

          <div className="card">
            <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Dokumen HR</h2>
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (!fileRef.current?.files?.[0]) return;
                const fd = new FormData();
                fd.append("file", fileRef.current.files[0]);
                fd.append("document_type", docTypeRef.current?.value ?? "lainnya");
                uploadDoc.mutate({ id: selectedId, formData: fd });
              }}
            >
              <select ref={docTypeRef} className="input w-auto">
                {DOC_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
              <input ref={fileRef} type="file" required className="input w-auto" />
              <button className="btn-secondary">Upload</button>
            </form>
            <ul className="mt-3 space-y-2">
              {(documents ?? []).map((d) => (
                <li
                  key={d.id}
                  className="flex items-center justify-between rounded-lg p-3 text-sm"
                  style={{ backgroundColor: "var(--n-hover)" }}
                >
                  <div>
                    <p className="font-medium" style={{ color: "var(--n-text)" }}>
                      {TYPE_LABELS[d.document_type]} — v{d.version}
                    </p>
                    <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                      {d.file_name} · {(d.file_size / 1024).toFixed(0)} KB
                    </p>
                  </div>
                  <a
                    href="#"
                    onClick={async (e) => {
                      e.preventDefault();
                      const { url } = await api.get<{ url: string }>(
                        `/employees/documents/${d.id}/download-url`
                      );
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
                <li className="text-sm" style={{ color: "var(--n-text-muted)" }}>Belum ada dokumen.</li>
              )}
            </ul>
          </div>
        </div>

        <div className="card">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>BPJS</h2>
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {(
              [
                { type: "kesehatan", label: "BPJS Kesehatan", no: selected?.bpjs_kesehatan_no, statusVal: selected?.bpjs_kesehatan_status, validUntil: selected?.bpjs_kesehatan_valid_until, cardKey: selected?.bpjs_kesehatan_card_key, fileRef: bpjsKesehatanFileRef },
                { type: "ketenagakerjaan", label: "BPJS Ketenagakerjaan", no: selected?.bpjs_ketenagakerjaan_no, statusVal: selected?.bpjs_ketenagakerjaan_status, validUntil: selected?.bpjs_ketenagakerjaan_valid_until, cardKey: selected?.bpjs_ketenagakerjaan_card_key, fileRef: bpjsKetenagakerjaanFileRef },
              ] as const
            ).map((b) => (
              <div key={b.type} className="rounded-lg border p-3" style={{ borderColor: "var(--n-border)" }}>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium" style={{ color: "var(--n-text)" }}>{b.label}</p>
                  {b.statusVal && (
                    <span className={`badge ${BPJS_STATUS_BADGES[b.statusVal] ?? "pill p-gray"}`}>{b.statusVal}</span>
                  )}
                </div>
                <p className="mt-1 font-mono text-xs" style={{ color: "var(--n-text-muted)" }}>
                  {b.no ?? "Nomor belum diisi"}
                </p>
                <form
                  className="mt-2 flex flex-wrap items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!selectedId) return;
                    const form = new FormData(e.currentTarget);
                    updateBpjsStatus.mutate({
                      id: selectedId,
                      body: {
                        [`bpjs_${b.type}_status`]: form.get("status") || null,
                        [`bpjs_${b.type}_valid_until`]: form.get("valid_until") || null,
                      },
                    });
                  }}
                >
                  <select name="status" defaultValue={b.statusVal ?? ""} className="input w-auto py-1 text-xs">
                    <option value="">—</option>
                    <option value="aktif">aktif</option>
                    <option value="nonaktif">nonaktif</option>
                    <option value="menunggu">menunggu</option>
                  </select>
                  <input
                    name="valid_until"
                    type="date"
                    defaultValue={b.validUntil ?? ""}
                    className="input w-auto py-1 text-xs"
                    title="Berlaku hingga"
                  />
                  <button disabled={updateBpjsStatus.isPending} className="btn-secondary py-1 text-xs">
                    Simpan
                  </button>
                </form>
                <form
                  className="mt-2 flex flex-wrap items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!selectedId || !b.fileRef.current?.files?.[0]) return;
                    const fd = new FormData();
                    fd.append("file", b.fileRef.current.files[0]);
                    fd.append("bpjs_type", b.type);
                    uploadBpjsCard.mutate({ id: selectedId, formData: fd });
                    b.fileRef.current.value = "";
                  }}
                >
                  <input ref={b.fileRef} type="file" required className="input w-auto py-1 text-xs" />
                  <button disabled={uploadBpjsCard.isPending} className="btn-secondary py-1 text-xs">
                    Upload Kartu
                  </button>
                  {b.cardKey && (
                    <button
                      type="button"
                      onClick={async () => {
                        if (!selectedId) return;
                        const { url } = await api.get<{ url: string }>(
                          `/employees/${selectedId}/bpjs-card/${b.type}/download-url`
                        );
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
            <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Asuransi</h2>
            <button
              className="btn-secondary text-xs"
              onClick={() => setShowInsuranceForm(!showInsuranceForm)}
            >
              {showInsuranceForm ? "Tutup" : "+ Tambah Polis"}
            </button>
          </div>
          {showInsuranceForm && (
            <form
              className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!selectedId) return;
                const form = new FormData(e.currentTarget);
                createInsurance.mutate({
                  id: selectedId,
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
                  <option key={p} value={p}>
                    {INSURANCE_PROVIDER_LABELS[p]}
                  </option>
                ))}
              </select>
              <input name="policy_no" required placeholder="No. Polis" className="input" />
              <input name="start_date" type="date" placeholder="Mulai" className="input" />
              <input name="valid_until" type="date" placeholder="Berlaku hingga" className="input" />
              <button disabled={createInsurance.isPending} className="btn sm:col-span-4">
                Simpan Polis
              </button>
              {createInsurance.error && (
                <p className="text-sm text-red-600 sm:col-span-4">
                  {(createInsurance.error as Error).message}
                </p>
              )}
            </form>
          )}
          <ul className="mt-3 space-y-2">
            {(insurances ?? []).map((ins) => (
              <li
                key={ins.id}
                className="rounded-lg p-3 text-sm"
                style={{ backgroundColor: "var(--n-hover)" }}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium" style={{ color: "var(--n-text)" }}>
                      {INSURANCE_PROVIDER_LABELS[ins.provider] ?? ins.provider} · {ins.policy_no}
                    </p>
                    <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                      {ins.start_date ?? "?"} s/d {ins.valid_until ?? "-"}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={ins.status}
                      disabled={updateInsurance.isPending}
                      onChange={(e) =>
                        updateInsurance.mutate({ id: ins.id, body: { status: e.target.value } })
                      }
                      className={`badge cursor-pointer border-0 ${INSURANCE_STATUS_BADGES[ins.status] ?? "pill p-gray"}`}
                    >
                      <option value="aktif">aktif</option>
                      <option value="kedaluwarsa">kedaluwarsa</option>
                      <option value="nonaktif">nonaktif</option>
                    </select>
                    <button
                      onClick={() => {
                        if (confirm("Hapus polis ini?")) deleteInsurance.mutate(ins.id);
                      }}
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
                        uploadInsuranceFile.mutate({ id: ins.id, kind: "card", formData: fd });
                        e.target.value = "";
                      }}
                    />
                  </label>
                  {ins.card_object_key && (
                    <button
                      onClick={async () => {
                        const { url } = await api.get<{ url: string }>(
                          `/employees/insurances/${ins.id}/card/download-url`
                        );
                        window.open(url, "_blank");
                      }}
                      className="hover:opacity-80"
                      style={{ color: "var(--n-text-muted)" }}
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
                        uploadInsuranceFile.mutate({ id: ins.id, kind: "policy", formData: fd });
                        e.target.value = "";
                      }}
                    />
                  </label>
                  {ins.policy_object_key && (
                    <button
                      onClick={async () => {
                        const { url } = await api.get<{ url: string }>(
                          `/employees/insurances/${ins.id}/policy/download-url`
                        );
                        window.open(url, "_blank");
                      }}
                      className="hover:opacity-80"
                      style={{ color: "var(--n-text-muted)" }}
                    >
                      Lihat Polis
                    </button>
                  )}
                </div>
              </li>
            ))}
            {insurances?.length === 0 && (
              <li className="text-sm" style={{ color: "var(--n-text-muted)" }}>Belum ada polis asuransi.</li>
            )}
          </ul>
        </div>

        <div className="card">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Jatah Cuti Tahunan</h2>
          <form
            className="mt-3 flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              saveBalance.mutate({
                id: selectedId,
                body: {
                  year: Number(form.get("year")),
                  total_days: Number(form.get("total_days")),
                },
              });
            }}
          >
            <input
              name="year"
              type="number"
              required
              defaultValue={new Date().getFullYear()}
              className="input w-24"
            />
            <input
              key={`${selectedId}-${selectedBalance?.total_days ?? "x"}`}
              name="total_days"
              type="number"
              min={0}
              required
              placeholder="Total hari"
              defaultValue={selectedBalance?.total_days ?? ""}
              className="input w-32"
            />
            <button disabled={saveBalance.isPending} className="btn-secondary">
              Simpan Jatah
            </button>
          </form>
          {selectedBalance && (
            <p className="mt-2 text-xs" style={{ color: "var(--n-text-muted)" }}>
              Terpakai {selectedBalance.used_days} hari · sisa{" "}
              <span className="font-semibold">{selectedBalance.remaining}</span> dari{" "}
              {selectedBalance.total_days} hari ({selectedBalance.year})
            </p>
          )}
          {saveBalance.error && (
            <p className="mt-2 text-sm text-red-600">
              {(saveBalance.error as Error).message}
            </p>
          )}
        </div>

        <div className="card">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Akun Portal Karyawan</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
            Tautkan akun login (role karyawan) agar karyawan bisa memakai
            Portal Saya: profil, slip gaji, cuti, dan dokumen.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {selected?.user_id ? (
              <>
                <span className="badge pill p-green">
                  Akun portal aktif
                </span>
                <button
                  onClick={() => linkAccount.mutate({ id: selected.id, userId: null })}
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
                  if (userId && selected) {
                    linkAccount.mutate({ id: selected.id, userId });
                    e.currentTarget.reset();
                  }
                }}
              >
                <select name="user_id" required className="input w-auto">
                  {(selfserviceAccounts ?? []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.email} · {a.full_name}
                    </option>
                  ))}
                </select>
                <button disabled={linkAccount.isPending} className="btn-secondary">
                  Aktifkan Portal
                </button>
              </form>
            ) : (
              <p className="text-sm" style={{ color: "var(--n-text-muted)" }}>
                Belum ada akun karyawan tersedia — buat lewat menu Pengguna
                dengan role &ldquo;karyawan&rdquo;.
              </p>
            )}
          </div>
          {linkAccount.error && (
            <p className="mt-2 text-sm text-red-600">
              {(linkAccount.error as Error).message}
            </p>
          )}
        </div>
        </>
      )}
    </div>
  );
}
