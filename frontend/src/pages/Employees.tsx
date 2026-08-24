import { FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile } from "../api/client";

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
}

interface LeaveBalanceRow {
  id: string;
  year: number;
  total_days: number;
  used_days: number;
  remaining: number;
}

const LEAVE_TYPE_LABELS: Record<string, string> = {
  cuti_tahunan: "Cuti Tahunan",
  izin: "Izin",
  sakit: "Sakit",
  cuti_tak_berbayar: "Cuti Tak Berbayar",
};

const LEAVE_STATUS_BADGES: Record<string, string> = {
  menunggu: "bg-amber-100 text-amber-700",
  disetujui: "bg-emerald-100 text-emerald-700",
  ditolak: "bg-rose-100 text-rose-700",
  dibatalkan: "bg-slate-100 text-slate-500",
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
  terkirim: "bg-amber-100 text-amber-700",
  dilihat: "bg-blue-100 text-blue-700",
  selesai: "bg-emerald-100 text-emerald-700",
  ditolak: "bg-rose-100 text-rose-700",
  kedaluwarsa: "bg-slate-100 text-slate-500",
  gagal: "bg-red-100 text-red-600",
};

const DOC_TYPES = ["ktp", "npwp", "bpjs_kesehatan", "bpjs_ketenagakerjaan", "lainnya"];

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
        <h1 className="text-2xl font-bold text-slate-800">Karyawan</h1>
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
          <p className="self-center text-xs text-slate-400">
            Nomor induk karyawan dibuat otomatis bila dikosongkan.
          </p>
          <button type="submit" disabled={createEmployee.isPending} className="btn sm:col-span-3">
            Simpan Karyawan
          </button>
        </form>
      )}

      {(expiring ?? []).length > 0 && (
        <div className="card border-l-4 border-amber-400">
          <h2 className="font-semibold text-amber-700">Reminder Kontrak ≤30 hari</h2>
          <ul className="mt-2 space-y-1 text-sm text-slate-600">
            {expiring!.map((c) => (
              <li key={c.contract_id}>
                <span className="font-medium">{c.employee_name}</span> — kontrak{" "}
                {c.contract_no} berakhir {c.end_date} ({c.days_left} hari lagi)
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold text-slate-700">Tanya Kontrak (AI)</h2>
          <span className="text-xs text-slate-400">
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
          <p className="mt-1 text-xs text-slate-400">
            Pertanyaan dibatasi pada kontrak karyawan yang sedang dipilih.
          </p>
        )}
        {askAi.error && (
          <p className="mt-2 text-sm text-red-600">{(askAi.error as Error).message}</p>
        )}
        {askResult && (
          <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/60 p-4">
            <p className="text-sm text-slate-700">{askResult.answer}</p>
            {askResult.sources.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-slate-500">
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

      {(leaveRequests ?? []).length > 0 && (
        <div className="card overflow-x-auto p-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 p-4">
            <h2 className="font-semibold text-slate-700">Pengajuan Cuti / Izin</h2>
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
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th className="th">Karyawan</th>
                <th className="th">Jenis</th>
                <th className="th">Tanggal</th>
                <th className="th">Alasan</th>
                <th className="th">Status</th>
                <th className="th">Keputusan</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
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
                      {lv.status === "menunggu" ? (
                        <>
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
                      ) : (
                        (lv.decision_note ?? "-")
                      )}
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
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">No. Induk</th>
              <th className="th">Nama</th>
              <th className="th">Telepon</th>
              <th className="th">Masuk</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(employees ?? []).map((e) => (
              <tr
                key={e.id}
                onClick={() => setSelectedId(e.id === selectedId ? null : e.id)}
                className={`cursor-pointer hover:bg-slate-50 ${
                  selectedId === e.id ? "bg-indigo-50/50" : ""
                }`}
              >
                <td className="td font-mono text-xs">{e.employee_no}</td>
                <td className="td font-medium">{e.full_name}</td>
                <td className="td">{e.phone ?? "-"}</td>
                <td className="td">{e.join_date ?? "-"}</td>
                <td className="td">
                  <span
                    className={`badge ${
                      e.status === "aktif"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {e.status}
                  </span>
                </td>
              </tr>
            ))}
            {employees?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center text-slate-400">
                  Belum ada karyawan.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="card">
            <h2 className="font-semibold text-slate-700">Kontrak Kerja</h2>
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
                    className="flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm"
                  >
                    <div>
                      <p className="font-medium text-slate-700">{c.contract_no}</p>
                      <p className="text-xs text-slate-400">
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
                              className="text-xs font-medium text-indigo-600 hover:text-indigo-800"
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
                        <span className="badge bg-emerald-100 text-emerald-700">
                          ditandatangani
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
              {contracts?.length === 0 && (
                <li className="text-sm text-slate-400">Belum ada kontrak.</li>
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
            <h2 className="font-semibold text-slate-700">Dokumen HR</h2>
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
                  className="flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm"
                >
                  <div>
                    <p className="font-medium text-slate-700">
                      {TYPE_LABELS[d.document_type]} — v{d.version}
                    </p>
                    <p className="text-xs text-slate-400">
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
                    className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
                  >
                    Unduh
                  </a>
                </li>
              ))}
              {documents?.length === 0 && (
                <li className="text-sm text-slate-400">Belum ada dokumen.</li>
              )}
            </ul>
          </div>
        </div>

        <div className="card">
          <h2 className="font-semibold text-slate-700">Jatah Cuti Tahunan</h2>
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
            <p className="mt-2 text-xs text-slate-500">
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
          <h2 className="font-semibold text-slate-700">Akun Portal Karyawan</h2>
          <p className="mt-1 text-xs text-slate-400">
            Tautkan akun login (role karyawan) agar karyawan bisa memakai
            Portal Saya: profil, slip gaji, cuti, dan dokumen.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {selected?.user_id ? (
              <>
                <span className="badge bg-emerald-100 text-emerald-700">
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
              <p className="text-sm text-slate-400">
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
