import { FormEvent, useRef, useState } from "react";
import { PageHeader } from "../components/notion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export interface ClientRow {
  id: string;
  name: string;
  npwp: string | null;
  pic_name: string | null;
  pic_phone: string | null;
  status: string;
  contract_end: string | null;
}

interface LegalDoc {
  id: string;
  document_type: string;
  title: string;
  version: number;
  file_name: string;
  file_size: number;
  uploaded_at: string;
}

const DOC_TYPES = ["perjanjian_kerjasama", "addendum", "npwp", "nib", "lainnya"];

const TYPE_LABELS: Record<string, string> = {
  perjanjian_kerjasama: "Perjanjian Kerjasama",
  addendum: "Addendum",
  npwp: "NPWP",
  nib: "NIB",
  lainnya: "Lainnya",
};

export default function Clients() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const docTypeRef = useRef<HTMLSelectElement>(null);

  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const { data: documents } = useQuery({
    queryKey: ["client-docs", selectedId],
    queryFn: () => api.get<LegalDoc[]>(`/clients/${selectedId}/documents`),
    enabled: Boolean(selectedId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["clients"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const createClient = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/clients", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const uploadDoc = useMutation({
    mutationFn: ({ id, formData }: { id: string; formData: FormData }) =>
      api.upload(`/clients/${id}/documents`, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-docs", selectedId] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createClient.mutate({
      name: form.get("name"),
      npwp: form.get("npwp") || null,
      pic_name: form.get("pic_name") || null,
      pic_phone: form.get("pic_phone") || null,
      contract_end: form.get("contract_end") || null,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader emoji="🎯" title="Klien" />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Klien Baru"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input name="name" required placeholder="Nama perusahaan klien *" className="input" />
          <input name="npwp" placeholder="NPWP" className="input" />
          <input name="pic_name" placeholder="Nama PIC" className="input" />
          <input name="pic_phone" placeholder="Telepon PIC" className="input" />
          <input name="contract_end" type="date" placeholder="Akhir kontrak" className="input" />
          <button type="submit" disabled={createClient.isPending} className="btn sm:col-span-3">
            Simpan Klien
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Perusahaan</th>
              <th className="th">NPWP</th>
              <th className="th">PIC</th>
              <th className="th">Akhir Kontrak</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(clients ?? []).map((c) => (
              <tr
                key={c.id}
                onClick={() => setSelectedId(c.id === selectedId ? null : c.id)}
                className={`cursor-pointer hover:bg-slate-50 ${
                  selectedId === c.id ? "bg-indigo-50/50" : ""
                }`}
              >
                <td className="td font-medium">{c.name}</td>
                <td className="td">{c.npwp ?? "-"}</td>
                <td className="td">{c.pic_name ?? "-"}</td>
                <td className="td">{c.contract_end ?? "-"}</td>
                <td className="td">
                  <span
                    className={`badge ${
                      c.status === "aktif"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
            {clients?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center text-slate-400">
                  Belum ada klien.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <div className="card">
          <h2 className="font-semibold text-slate-700">Dokumen Legalitas</h2>
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
                      `/clients/documents/${d.id}/download-url`
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
      )}
    </div>
  );
}
