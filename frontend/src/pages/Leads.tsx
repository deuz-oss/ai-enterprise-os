import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { CalloutBlock, PageHeader, PropertiesPanel, PropertyRow } from "../components/notion";

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

// Warna aksen kolom papan ala badge pipeline.
const STAGE_DOT: Record<string, string> = {
  lead: "#9f9f9f",
  kontak: "#2383e2",
  presentasi: "#5b5bd6",
  penawaran: "#9065b0",
  negosiasi: "#cb912f",
  deal: "#0f7b6c",
  gagal: "#e03e3e",
};

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
  const [view, setView] = useState<"tabel" | "papan">("tabel");
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader emoji="🎯" title="Pipeline Calon Klien" />
        <div className="flex items-center gap-2">
          <div
            className="flex overflow-hidden rounded text-sm"
            style={{ border: "1px solid var(--n-border)" }}
          >
            {(["tabel", "papan"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className="px-3 py-1.5 capitalize transition-colors"
                style={{
                  backgroundColor: view === v ? "var(--n-hover)" : "transparent",
                  color: view === v ? "var(--n-text)" : "var(--n-text-muted)",
                  fontWeight: view === v ? 500 : 400,
                }}
              >
                {view === v ? "☰ " : "▦ "}
                {v}
              </button>
            ))}
          </div>
          <button className="btn" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Tutup" : "+ Lead Baru"}
          </button>
        </div>
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

      {leads?.length === 0 && (
        <CalloutBlock emoji="🌱" tone="info">
          Belum ada lead. Klik <b>"+ Lead Baru"</b> untuk mulai mengisi pipeline.
        </CalloutBlock>
      )}

      {/* ===== View Tabel ===== */}
      {view === "tabel" && (
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
                  Belum ada lead.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
      )}

      {/* ===== View Papan (kanban ala Notion) ===== */}
      {view === "papan" && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STAGES.map((stage) => {
            const cards = (leads ?? []).filter((l) => l.stage === stage);
            const total = cards.reduce((s, l) => s + Number(l.estimated_value ?? 0), 0);
            return (
              <div
                key={stage}
                className="w-64 shrink-0 rounded-md"
                style={{ backgroundColor: "var(--n-hover)" }}
              >
                <div className="flex items-center justify-between px-3 pt-3">
                  <span className="flex items-center gap-2 text-sm font-medium" style={{ color: "var(--n-text)" }}>
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: STAGE_DOT[stage] }}
                    />
                    <span className="capitalize">{stage}</span>
                    <span style={{ color: "var(--n-text-muted)" }}>{cards.length}</span>
                  </span>
                </div>
                <p className="px-3 pb-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
                  {formatRupiah(total)}
                </p>
                <div className="space-y-2 px-2 pb-3">
                  {cards.map((lead) => (
                    <div
                      key={lead.id}
                      className="rounded-md p-3 shadow-sm transition-shadow hover:shadow"
                      style={{
                        backgroundColor: "var(--n-bg-elevated)",
                        border: "1px solid var(--n-border)",
                        cursor: "pointer",
                      }}
                      onClick={() => setSelectedId(lead.id === selectedId ? null : lead.id)}
                      title={lead.industry ?? undefined}
                    >
                      <p className="text-sm font-medium" style={{ color: "var(--n-text)" }}>
                        {lead.company_name}
                      </p>
                      <p className="mt-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
                        {lead.contact_name ?? "—"}
                        {lead.estimated_headcount ? ` · ${lead.estimated_headcount} TKI` : ""}
                      </p>
                      <p className="mt-1 text-xs font-medium">
                        {formatRupiah(lead.estimated_value)}
                      </p>
                      {/* Pindah tahap cepat: panah kiri/kanan */}
                      <div
                        className="mt-2 flex items-center justify-between text-xs"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          disabled={STAGES.indexOf(lead.stage) === 0}
                          onClick={() =>
                            changeStage.mutate({
                              id: lead.id,
                              stage: STAGES[STAGES.indexOf(lead.stage) - 1],
                            })
                          }
                          className="rounded px-1.5 py-0.5 disabled:opacity-25"
                          style={{ border: "1px solid var(--n-border)" }}
                          title="Tahap sebelumnya"
                        >
                          ←
                        </button>
                        <select
                          value={lead.stage}
                          onChange={(e) => changeStage.mutate({ id: lead.id, stage: e.target.value })}
                          className="cursor-pointer rounded bg-transparent text-xs capitalize"
                          style={{ color: "var(--n-text-muted)", border: "none", outline: "none" }}
                        >
                          {STAGES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                        <button
                          disabled={STAGES.indexOf(lead.stage) === STAGES.length - 1}
                          onClick={() =>
                            changeStage.mutate({
                              id: lead.id,
                              stage: STAGES[STAGES.indexOf(lead.stage) + 1],
                            })
                          }
                          className="rounded px-1.5 py-0.5 disabled:opacity-25"
                          style={{ border: "1px solid var(--n-border)" }}
                          title="Tahap berikutnya"
                        >
                          →
                        </button>
                      </div>
                    </div>
                  ))}
                  {cards.length === 0 && (
                    <p className="px-1 py-3 text-center text-xs" style={{ color: "var(--n-text-muted)" }}>
                      Kosong
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selectedId && (
        <div className="card">
          {(() => {
            const lead = leads?.find((l) => l.id === selectedId);
            if (!lead) return null;
            return (
              <>
                <PageHeader emoji="🏢" title={lead.company_name} subtitle={lead.industry ?? undefined} />
                <PropertiesPanel className="mt-4 max-w-xl">
                  <PropertyRow icon="👤" label="PIC">
                    {lead.contact_name ?? "—"}
                  </PropertyRow>
                  <PropertyRow icon="🧑‍🤝‍🧑" label="Est. TKI">
                    {lead.estimated_headcount ?? "—"}
                  </PropertyRow>
                  <PropertyRow icon="💰" label="Nilai Potensi">
                    {formatRupiah(lead.estimated_value)}
                  </PropertyRow>
                  <PropertyRow icon="📍" label="Tahapan">
                    <select
                      value={lead.stage}
                      onChange={(e) => changeStage.mutate({ id: lead.id, stage: e.target.value })}
                      className="input w-auto py-1 text-sm capitalize"
                    >
                      {STAGES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </PropertyRow>
                </PropertiesPanel>
              </>
            );
          })()}

          <h2 className="mt-6 font-semibold text-notion">Aktivitas</h2>
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
