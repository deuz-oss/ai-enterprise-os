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
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">Perusahaan</th>
              <th className="th">NPWP</th>
              <th className="th">PIC</th>
              <th className="th">Akhir Kontrak</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(clients ?? []).map((c) => (
              <tr
                key={c.id}
                onClick={() => setSelectedId(c.id === selectedId ? null : c.id)}
                className="cursor-pointer transition-colors hover:bg-[var(--n-hover)]"
                style={{ backgroundColor: selectedId === c.id ? "var(--accent-tint)" : undefined }}
              >
                <td className="td font-medium">{c.name}</td>
                <td className="td">{c.npwp ?? "-"}</td>
                <td className="td">{c.pic_name ?? "-"}</td>
                <td className="td">{c.contract_end ?? "-"}</td>
                <td className="td">
                  <span
                    className={`pill ${
                      c.status === "aktif"
                        ? "p-green"
                        : "p-gray"
                    }`}
                  >
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
            {clients?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada klien.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <div className="card">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Dokumen Legalitas</h2>
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
                      `/clients/documents/${d.id}/download-url`
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
      )}
    </div>
  );
}
