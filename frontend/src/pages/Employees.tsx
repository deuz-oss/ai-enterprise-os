import { FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export interface EmployeeRow {
  id: string;
  employee_no: string;
  full_name: string;
  phone: string | null;
  ktp_no: string | null;
  npwp_no: string | null;
  join_date: string | null;
  status: string;
}

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

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["employees"] });
    qc.invalidateQueries({ queryKey: ["contracts-expiring"] });
  };

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

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createEmployee.mutate({
      full_name: form.get("full_name"),
      phone: form.get("phone") || null,
      ktp_no: form.get("ktp_no") || null,
      npwp_no: form.get("npwp_no") || null,
      join_date: form.get("join_date") || null,
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
              {(contracts ?? []).map((c) => (
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
                    {c.sign_status === "menunggu_ttd" ? (
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
              ))}
              {contracts?.length === 0 && (
                <li className="text-sm text-slate-400">Belum ada kontrak.</li>
              )}
            </ul>
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
      )}
    </div>
  );
}
