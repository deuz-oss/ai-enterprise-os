import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";

export interface Lead {
  id: string;
  company_name: string;
  industry: string | null;
  contact_name: string | null;
  estimated_headcount: number | null;
  estimated_value: number | null;
  stage: string;
  created_at: string;
}

const STAGES = ["lead", "kontak", "presentasi", "penawaran", "negosiasi", "deal", "gagal"];

const BADGE_COLORS: Record<string, string> = {
  lead: "bg-slate-100 text-slate-600",
  kontak: "bg-blue-100 text-blue-700",
  presentasi: "bg-indigo-100 text-indigo-700",
  penawaran: "bg-violet-100 text-violet-700",
  negosiasi: "bg-amber-100 text-amber-700",
  deal: "bg-emerald-100 text-emerald-700",
  gagal: "bg-red-100 text-red-700",
};

interface Activity {
  id: string;
  activity_type: string;
  content: string;
  created_at: string;
}

export default function Leads() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: leads } = useQuery({
    queryKey: ["leads"],
    queryFn: () => api.get<Lead[]>("/leads"),
  });
  const { data: activities } = useQuery({
    queryKey: ["lead-activities", selectedId],
    queryFn: () => api.get<Activity[]>(`/leads/${selectedId}/activities`),
    enabled: Boolean(selectedId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["leads"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const createLead = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/leads", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const changeStage = useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: string }) =>
      api.patch(`/leads/${id}`, { stage }),
    onSuccess: invalidate,
  });

  const addActivity = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      api.post(`/leads/${id}/activities`, { activity_type: "catatan", content }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead-activities", selectedId] });
    },
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createLead.mutate({
      company_name: form.get("company_name"),
      industry: form.get("industry") || null,
      contact_name: form.get("contact_name") || null,
      contact_phone: form.get("contact_phone") || null,
      estimated_headcount: Number(form.get("estimated_headcount")) || null,
      estimated_value: Number(form.get("estimated_value")) || null,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Pipeline Calon Klien</h1>
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Lead Baru"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input name="company_name" required placeholder="Nama perusahaan *" className="input" />
          <input name="industry" placeholder="Industri" className="input" />
          <input name="contact_name" placeholder="Nama PIC" className="input" />
          <input name="contact_phone" placeholder="Telepon PIC" className="input" />
          <input name="estimated_headcount" type="number" placeholder="Estimasi jumlah TKI" className="input" />
          <input name="estimated_value" type="number" placeholder="Nilai potensi (Rp)" className="input" />
          <button type="submit" disabled={createLead.isPending} className="btn sm:col-span-3">
            Simpan Lead
          </button>
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Perusahaan</th>
              <th className="th">PIC</th>
              <th className="th">Est. TKI</th>
              <th className="th">Nilai Potensi</th>
              <th className="th">Tahapan</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(leads ?? []).map((lead) => (
              <tr
                key={lead.id}
                onClick={() => setSelectedId(lead.id === selectedId ? null : lead.id)}
                className={`cursor-pointer hover:bg-slate-50 ${
                  selectedId === lead.id ? "bg-indigo-50/50" : ""
                }`}
              >
                <td className="td font-medium">{lead.company_name}</td>
                <td className="td">{lead.contact_name ?? "-"}</td>
                <td className="td">{lead.estimated_headcount ?? "-"}</td>
                <td className="td">{formatRupiah(lead.estimated_value)}</td>
                <td className="td">
                  <select
                    value={lead.stage}
                    onChange={(e) => {
                      e.stopPropagation();
                      changeStage.mutate({ id: lead.id, stage: e.target.value });
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className={`badge cursor-pointer border-0 ${BADGE_COLORS[lead.stage]}`}
                  >
                    {STAGES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
            {leads?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center text-slate-400">
                  Belum ada lead. Klik "+ Lead Baru" untuk mulai.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId && (
        <div className="card">
          <h2 className="font-semibold text-slate-700">Aktivitas</h2>
          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const input = e.currentTarget.elements.namedItem("content") as HTMLInputElement;
              if (input.value.trim()) {
                addActivity.mutate({ id: selectedId, content: input.value });
                input.value = "";
              }
            }}
          >
            <input name="content" placeholder="Tambah catatan aktivitas..." className="input" />
            <button className="btn-secondary">Tambah</button>
          </form>
          <ul className="mt-3 space-y-2">
            {(activities ?? []).map((a) => (
              <li key={a.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                <span className="font-medium text-slate-600">[{a.activity_type}]</span>{" "}
                {a.content}
              </li>
            ))}
            {activities?.length === 0 && <li className="text-sm text-slate-400">Belum ada aktivitas.</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
