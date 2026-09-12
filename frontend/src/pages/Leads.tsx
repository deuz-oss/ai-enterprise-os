import { FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile, formatRupiah } from "../api/client";
import {
  Briefcase,
  Building2,
  CalendarClock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleDollarSign,
  Clock,
  LayoutGrid,
  List,
  MapPin,
  MessageSquareText,
  User,
  Users,
  X,
} from "lucide-react";
import { CalloutBlock, PageHeader, PropertiesPanel, PropertyRow, initials } from "../components/workspace";
import { Badge, KpiCard } from "../components/ui";
import { Pagination } from "../components/Pagination";
import { CustomFieldsSection } from "../components/CustomFieldsSection";

export interface Lead {
  id: string;
  company_id: string;
  company_name: string;
  company_source: string;
  industry: string | null;
  contact_name: string | null;
  contact_email: string | null;
  estimated_headcount: number | null;
  estimated_value: number | null;
  stage: string;
  notes: string | null;
  owner_id: string | null;
  owner_name: string | null;
  expected_close_date: string | null;
  stage_changed_at: string | null;
  closed_reason: string | null;
  last_activity_at: string | null;
  created_at: string;
}

interface LeadImportRowFailure {
  row: number;
  company_name: string;
  error: string;
}

interface LeadImportResult {
  companies_created: number;
  leads_created: number;
  failed: LeadImportRowFailure[];
}

// Fase 20 item 5 (revisi) -- alternatif aman dari scraping LinkedIn: impor
// CSV manual/legal, bukan scraping otomatis. Label sumber ditampilkan di
// tabel supaya staf tahu asal tiap lead.
const SOURCE_LABEL: Record<string, string> = {
  manual: "Manual",
  csv_import: "Impor CSV",
};

interface UserOption {
  id: string;
  full_name: string;
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

// B1: pill status pakai palet hex persis mockup (lihat index.css).
const STAGE_PILL: Record<string, string> = {
  lead: "pill p-gray",
  kontak: "pill p-blue",
  presentasi: "pill p-indigo",
  penawaran: "pill p-violet",
  negosiasi: "pill p-yellow",
  deal: "pill p-green",
  gagal: "pill p-red",
};

interface Activity {
  id: string;
  activity_type: string;
  content: string;
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// Fase 43 -- baris widget "Tugas Jatuh Tempo" lintas lead.
interface DueTask {
  id: string;
  lead_id: string;
  company_name: string;
  activity_type: string;
  content: string;
  due_at: string;
  completed_at: string | null;
  owner_name: string | null;
}

interface Contact {
  id: string;
  company_id: string;
  name: string;
  department: string | null;
  email: string | null;
  phone: string | null;
  is_primary: boolean;
}

// Fase 40: satu lead/deal bisa punya beberapa PIC dengan peran berbeda
// (Decision Maker, Champion, dst.), dipilih dari kontak company yang sama
// -- lihat `presales/models.py::LeadContact`.
interface LeadContact {
  id: string;
  lead_id: string;
  role: string | null;
  created_at: string;
  contact: Contact;
}

// Badge tipe di kartu Kanban (§1.8) -- Lead/Company belum punya field
// "tipe layanan" outsourcing sungguhan (mis. Payroll Only/Full
// Outsourcing), cuma `industry` (sektor bisnis klien, teks bebas). Warna
// di-hash deterministik dari string industri supaya tetap konsisten per
// klien tanpa mengarang kategori baru yang tidak ada datanya.
const INDUSTRY_BADGE_CLASSES = ["p-blue", "p-violet", "p-green", "p-orange", "p-yellow", "p-indigo", "p-red", "p-gray"];
function industryBadgeClass(industry: string): string {
  let hash = 0;
  for (let i = 0; i < industry.length; i++) hash = (hash * 31 + industry.charCodeAt(i)) >>> 0;
  return INDUSTRY_BADGE_CLASSES[hash % INDUSTRY_BADGE_CLASSES.length];
}

// Fase 42 -- "sudah berapa lama di tahap ini", dihitung dari
// `stage_changed_at` (server-side, auto-diisi) supaya sinyal kecepatan
// pipeline terlihat langsung tanpa perlu laporan terpisah.
function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  const diffMs = Date.now() - new Date(iso).getTime();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
}

export default function Leads() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const importFileRef = useRef<HTMLInputElement>(null);
  const [importResult, setImportResult] = useState<LeadImportResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<"tabel" | "papan">("tabel");
  const [offset, setOffset] = useState(0);
  const [stageFilter, setStageFilter] = useState("");
  const [expandedContactFields, setExpandedContactFields] = useState<Record<string, boolean>>({});
  const pageLimit = 50;
  // Tabel (satu halaman) terpisah dari `leadsLookup` (semua lead) --
  // papan Kanban, drag-and-drop, dan panel detail (bisa dipilih dari
  // tabel MAUPUN papan) semuanya butuh dataset penuh, bukan satu halaman.
  // Filter tahap cuma berlaku di tabel -- papan sudah mengelompokkan
  // per tahap secara visual, memfilternya di sana tidak masuk akal.
  const { data: leadsPage } = useQuery({
    queryKey: ["leads", offset, stageFilter],
    queryFn: () =>
      api.getPaged<Lead>(
        `/leads?limit=${pageLimit}&offset=${offset}${stageFilter ? `&stage=${stageFilter}` : ""}`
      ),
  });
  const leadsTable = leadsPage?.data;
  const leadsTotal = leadsPage?.total ?? 0;
  const { data: leadsLookup } = useQuery({
    queryKey: ["leads-lookup"],
    queryFn: () => api.get<Lead[]>("/leads?limit=1000"),
  });
  const { data: activities } = useQuery({
    queryKey: ["lead-activities", selectedId],
    queryFn: () => api.get<Activity[]>(`/leads/${selectedId}/activities`),
    enabled: Boolean(selectedId),
  });
  const { data: leadContacts } = useQuery({
    queryKey: ["lead-contacts", selectedId],
    queryFn: () => api.get<LeadContact[]>(`/leads/${selectedId}/contacts`),
    enabled: Boolean(selectedId),
  });
  const selectedCompanyId = leadsLookup?.find((l) => l.id === selectedId)?.company_id;
  // Daftar kontak company untuk dropdown "tambah PIC" -- terpisah dari
  // `leadContacts` (yang sudah ditautkan ke lead ini).
  const { data: companyContacts } = useQuery({
    queryKey: ["company-contacts", selectedCompanyId],
    queryFn: () => api.get<Contact[]>(`/companies/${selectedCompanyId}/contacts`),
    enabled: Boolean(selectedCompanyId),
  });
  // Untuk avatar+nama "Pemilik Deal" (§1.8) & dropdown assign owner. Endpoint
  // ini admin-only di backend -- sama seperti dipakai Candidates.tsx untuk
  // pilihan interviewer, jadi kalau gagal (403) dropdown cuma kosong, tidak
  // memblokir fitur lain di halaman ini.
  const { data: users } = useQuery({
    queryKey: ["users-lite"],
    queryFn: () => api.get<UserOption[]>("/auth/users"),
    retry: false,
  });
  const { data: dueTasks } = useQuery({
    queryKey: ["due-tasks"],
    queryFn: () => api.get<DueTask[]>("/leads/activities/due"),
  });

  // KPI row (§2 archetype F) -- archetype F spec menyebut 4 kartu contoh
  // (total nilai, win rate, target, estimasi komisi), tapi "target" dan
  // "estimasi komisi" tidak punya data pendukung sama sekali di backend
  // presales (dicek, tidak ada field/endpoint terkait) -- diganti 2 kartu
  // lain yang genuinely real dari data yang sama.
  const allLeads = leadsLookup ?? [];
  const activeLeads = allLeads.filter((l) => l.stage !== "deal" && l.stage !== "gagal");
  const wonLeads = allLeads.filter((l) => l.stage === "deal");
  const lostLeads = allLeads.filter((l) => l.stage === "gagal");
  const pipelineValue = activeLeads.reduce((sum, l) => sum + Number(l.estimated_value ?? 0), 0);
  const wonValue = wonLeads.reduce((sum, l) => sum + Number(l.estimated_value ?? 0), 0);
  const winRateDenom = wonLeads.length + lostLeads.length;
  const winRate = winRateDenom > 0 ? Math.round((wonLeads.length / winRateDenom) * 100) : null;

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["leads"] });
    qc.invalidateQueries({ queryKey: ["leads-lookup"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const createLead = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/leads", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const importLeads = useMutation({
    mutationFn: (formData: FormData) => api.upload<LeadImportResult>("/companies/import", formData),
    onSuccess: (data) => {
      setImportResult(data);
      if (importFileRef.current) importFileRef.current.value = "";
      invalidate();
    },
  });

  const changeStage = useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: string }) =>
      api.patch(`/leads/${id}`, { stage }),
    onSuccess: invalidate,
    // C3: rollback bila server menolak perpindahan tahap
    onError: invalidate,
  });

  // Fase 42 -- bundel field sales-ops (target closing, alasan menang/kalah).
  const updateLeadFields = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/leads/${id}`, body),
    onSuccess: invalidate,
  });

  const assignOwner = useMutation({
    mutationFn: ({ id, ownerId }: { id: string; ownerId: string | null }) =>
      api.patch(`/leads/${id}`, { owner_id: ownerId }),
    onSuccess: invalidate,
  });

  const convertLead = useMutation({
    mutationFn: (id: string) => api.post<{ id: string; name: string }>(`/leads/${id}/convert`, {}),
  });

  // C3: drag-and-drop native (tanpa lib) — optimis update lalu mutasi.
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOverStage, setDragOverStage] = useState<string | null>(null);

  function dropToStage(stage: string) {
    const id = dragId;
    setDragId(null);
    setDragOverStage(null);
    if (!id) return;
    const lead = (leadsLookup ?? []).find((l) => l.id === id);
    if (!lead || lead.stage === stage) return;
    qc.setQueryData<Lead[]>(["leads-lookup"], (prev) =>
      (prev ?? []).map((l) => (l.id === id ? { ...l, stage } : l))
    );
    changeStage.mutate({ id, stage });
  }

  const addActivity = useMutation({
    mutationFn: ({ id, content, dueAt }: { id: string; content: string; dueAt?: string }) =>
      api.post(`/leads/${id}/activities`, {
        activity_type: dueAt ? "tugas" : "catatan",
        content,
        due_at: dueAt || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead-activities", selectedId] });
      qc.invalidateQueries({ queryKey: ["due-tasks"] });
    },
  });

  const completeActivity = useMutation({
    mutationFn: ({ activityId, completed }: { activityId: string; completed: boolean }) =>
      api.patch(`/leads/activities/${activityId}`, { completed }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead-activities", selectedId] });
      qc.invalidateQueries({ queryKey: ["due-tasks"] });
    },
  });

  const addLeadContact = useMutation({
    mutationFn: ({ id, contactId, role }: { id: string; contactId: string; role: string }) =>
      api.post(`/leads/${id}/contacts`, { contact_id: contactId, role: role || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead-contacts", selectedId] });
    },
  });

  const updateLeadContactRole = useMutation({
    mutationFn: ({ leadContactId, role }: { leadContactId: string; role: string }) =>
      api.patch(`/leads/contacts/${leadContactId}`, { role: role || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead-contacts", selectedId] });
    },
  });

  const removeLeadContact = useMutation({
    mutationFn: (leadContactId: string) => api.delete(`/leads/contacts/${leadContactId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead-contacts", selectedId] });
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
        <PageHeader icon={Briefcase} title="Pipeline Calon Klien" />
        <div className="flex items-center gap-2">
          <div
            className="flex overflow-hidden rounded text-sm"
            style={{ border: "1px solid var(--border)" }}
          >
            {(["tabel", "papan"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className="px-3 py-1.5 capitalize transition-colors"
                style={{
                  backgroundColor: view === v ? "var(--hover)" : "transparent",
                  color: view === v ? "var(--text)" : "var(--text-muted)",
                  fontWeight: view === v ? 500 : 400,
                }}
              >
                {v === "tabel" ? <List className="inline h-3.5 w-3.5" /> : <LayoutGrid className="inline h-3.5 w-3.5" />}{" "}
                {v}
              </button>
            ))}
          </div>
          <button
            className="btn-secondary"
            onClick={() => {
              setShowImport(!showImport);
              setImportResult(null);
            }}
          >
            {showImport ? "Tutup" : "Impor CSV"}
          </button>
          <button className="btn" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Tutup" : "+ Lead Baru"}
          </button>
        </div>
      </div>

      {showImport && (
        <div className="card space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Impor lead massal dari CSV (mis. hasil pameran dagang atau daftar prospek yang
              sudah dikumpulkan manual/legal) — bukan scraping otomatis.
            </p>
            <button
              type="button"
              className="text-xs font-medium hover:opacity-80"
              style={{ color: "var(--accent)" }}
              onClick={() => downloadFile("/companies/import/template")}
            >
              Unduh Template CSV
            </button>
          </div>
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const file = importFileRef.current?.files?.[0];
              if (!file) return;
              const fd = new FormData();
              fd.append("file", file);
              importLeads.mutate(fd);
            }}
          >
            <input ref={importFileRef} type="file" accept=".csv" required className="input w-auto" />
            <button className="btn-secondary" disabled={importLeads.isPending}>
              {importLeads.isPending ? "Mengimpor..." : "Impor"}
            </button>
          </form>
          {importLeads.error && (
            <p className="text-sm text-red-600 dark:text-red-400">{(importLeads.error as Error).message}</p>
          )}
          {importResult && (
            <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: "var(--hover)" }}>
              <p style={{ color: "var(--text)" }}>
                {importResult.leads_created} lead dibuat ({importResult.companies_created} perusahaan
                baru).
                {importResult.failed.length > 0 && ` ${importResult.failed.length} baris gagal.`}
              </p>
              {importResult.failed.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs" style={{ color: "var(--th-color)" }}>
                  {importResult.failed.map((f) => (
                    <li key={f.row}>
                      Baris {f.row} ({f.company_name}): {f.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Nilai Pipeline"
          value={formatRupiah(pipelineValue)}
          icon={CircleDollarSign}
          iconTone="info"
          context={`${activeLeads.length} lead aktif`}
        />
        <KpiCard
          label="Win Rate"
          value={winRate !== null ? `${winRate}%` : "-"}
          icon={Briefcase}
          iconTone="success"
          context={winRateDenom > 0 ? `${wonLeads.length} menang dari ${winRateDenom}` : "Belum ada deal selesai"}
        />
        <KpiCard label="Lead Aktif" value={activeLeads.length} icon={Users} iconTone="neutral" />
        <KpiCard
          label="Deal Menang"
          value={wonLeads.length}
          icon={Building2}
          iconTone="accent"
          context={formatRupiah(wonValue)}
        />
      </div>

      {dueTasks && dueTasks.length > 0 && (
        <div className="card">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>
            Tugas Jatuh Tempo ({dueTasks.length})
          </h2>
          <ul className="mt-3 space-y-2">
            {dueTasks.slice(0, 5).map((t) => {
              const isOverdue = new Date(t.due_at) < new Date();
              return (
                <li key={t.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    onChange={() => completeActivity.mutate({ activityId: t.id, completed: true })}
                    aria-label={`Tandai selesai: ${t.content}`}
                  />
                  <button
                    type="button"
                    onClick={() => setSelectedId(t.lead_id)}
                    className="min-w-0 flex-1 truncate text-left hover:underline"
                    style={{ color: "var(--text)" }}
                  >
                    <span className="font-medium">{t.company_name}</span> — {t.content}
                  </button>
                  <span
                    className={`shrink-0 text-xs ${isOverdue ? "text-red-600 dark:text-red-400 font-medium" : ""}`}
                    style={isOverdue ? undefined : { color: "var(--text-muted)" }}
                  >
                    {new Date(t.due_at).toLocaleDateString("id-ID", { day: "numeric", month: "short" })}
                  </span>
                </li>
              );
            })}
          </ul>
          {dueTasks.length > 5 && (
            <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
              +{dueTasks.length - 5} tugas lainnya -- buka detail lead untuk lihat semua.
            </p>
          )}
        </div>
      )}

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

      {leadsLookup?.length === 0 && (
        <CalloutBlock tone="info">
          Belum ada lead. Klik <b>"+ Lead Baru"</b> untuk mulai mengisi pipeline.
        </CalloutBlock>
      )}

      {view === "tabel" && (
        <select
          value={stageFilter}
          onChange={(e) => {
            setStageFilter(e.target.value);
            setOffset(0);
          }}
          className="input w-auto"
          aria-label="Filter tahap lead"
        >
          <option value="">Semua tahap</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      )}

      {/* ===== View Tabel ===== */}
      {view === "tabel" && (
        <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead
            style={{
              borderBottom: "1px solid var(--border)",
              backgroundColor: "var(--hover)",
            }}
          >
            <tr>
              <th className="th">Perusahaan</th>
              <th className="th">Sumber</th>
              <th className="th">PIC</th>
              <th className="th">Est. TKI</th>
              <th className="th">Nilai Potensi</th>
              <th className="th">Tahapan</th>
            </tr>
          </thead>
          <tbody
            style={{ borderTop: "1px solid var(--border)" }}
          >
            {(leadsTable ?? []).map((lead) => (
              <tr
                key={lead.id}
                onClick={() => setSelectedId(lead.id === selectedId ? null : lead.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedId(lead.id === selectedId ? null : lead.id);
                  }
                }}
                tabIndex={0}
                className="cursor-pointer transition-colors"
                style={{
                  backgroundColor:
                    selectedId === lead.id ? "var(--accent-tint)" : undefined,
                }}
              >
                <td className="td font-medium">{lead.company_name}</td>
                <td className="td">
                  <Badge tone={lead.company_source === "csv_import" ? "info" : "neutral"}>
                    {SOURCE_LABEL[lead.company_source] ?? lead.company_source}
                  </Badge>
                </td>
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
                    className={`cursor-pointer border-0 ${STAGE_PILL[lead.stage] ?? "pill p-gray"}`}
                    aria-label={`Ubah tahap lead ${lead.company_name ?? ""}`}
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
            {leadsTable?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada lead.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
      )}

      {view === "tabel" && (
        <Pagination offset={offset} limit={pageLimit} total={leadsTotal} onOffsetChange={setOffset} />
      )}

      {/* ===== View Papan (kanban drag-and-drop C3) ===== */}
      {view === "papan" && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STAGES.map((stage) => {
            const cards = (leadsLookup ?? []).filter((l) => l.stage === stage);
            const total = cards.reduce((s, l) => s + Number(l.estimated_value ?? 0), 0);
            const isOver = dragOverStage === stage;
            return (
              <div
                key={stage}
                className="w-64 shrink-0 rounded-md transition-colors"
                style={{
                  backgroundColor: "var(--hover)",
                  boxShadow: isOver ? "inset 0 0 0 2px var(--accent)" : undefined,
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                  setDragOverStage(stage);
                }}
                onDragLeave={() => setDragOverStage((s) => (s === stage ? null : s))}
                onDrop={(e) => {
                  e.preventDefault();
                  dropToStage(stage);
                }}
              >
                <div className="flex items-center justify-between px-3 pt-3">
                  <span className="flex items-center gap-2 text-sm font-medium" style={{ color: "var(--text)" }}>
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: STAGE_DOT[stage] }}
                    />
                    <span className="capitalize">{stage}</span>
                    <span style={{ color: "var(--th-color)" }}>{cards.length}</span>
                  </span>
                </div>
                <p className="px-3 pb-1 text-xs" style={{ color: "var(--th-color)" }}>
                  {formatRupiah(total)}
                </p>
                <div className="space-y-2 px-2 pb-3">
                  {cards.map((lead) => (
                    <div
                      key={lead.id}
                      draggable
                      onDragStart={(e) => {
                        setDragId(lead.id);
                        e.dataTransfer.effectAllowed = "move";
                        e.dataTransfer.setData("text/plain", lead.id);
                      }}
                      onDragEnd={() => setDragId(null)}
                      className="rounded-md p-3 shadow-sm transition-shadow hover:shadow"
                      style={{
                        backgroundColor: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        cursor: dragId === lead.id ? "grabbing" : "grab",
                        opacity: dragId === lead.id ? 0.5 : 1,
                      }}
                      onClick={() => setSelectedId(lead.id === selectedId ? null : lead.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedId(lead.id === selectedId ? null : lead.id);
                        }
                      }}
                      tabIndex={0}
                      title={lead.industry ?? undefined}
                    >
                      {lead.industry && (
                        <span className={`pill ${industryBadgeClass(lead.industry)} mb-1.5 text-[10px]`}>
                          {lead.industry}
                        </span>
                      )}
                      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
                        {lead.company_name}
                      </p>
                      <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                        {lead.contact_name ?? "—"}
                        {lead.estimated_headcount ? ` · ${lead.estimated_headcount} TKI` : ""}
                      </p>
                      <p className="mt-1 text-xs font-medium">
                        {formatRupiah(lead.estimated_value)}
                      </p>
                      {/* Avatar + pemilik deal, chip status kontekstual dari `notes` (§1.8) */}
                      <div
                        className="mt-2 flex items-center justify-between gap-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex min-w-0 items-center gap-1.5">
                          <span
                            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-[var(--accent-contrast)]"
                            style={{ backgroundColor: "var(--accent)" }}
                          >
                            {lead.owner_name ? initials(lead.owner_name) : "?"}
                          </span>
                          <select
                            value={lead.owner_id ?? ""}
                            onChange={(e) =>
                              assignOwner.mutate({ id: lead.id, ownerId: e.target.value || null })
                            }
                            className="min-w-0 cursor-pointer truncate rounded bg-transparent text-xs"
                            style={{ color: "var(--text-muted)", border: "none", outline: "none" }}
                            title="Pemilik deal"
                            aria-label="Pemilik deal"
                          >
                            <option value="">Belum ditugaskan</option>
                            {(users ?? []).map((u) => (
                              <option key={u.id} value={u.id}>
                                {u.full_name}
                              </option>
                            ))}
                          </select>
                        </div>
                        {lead.notes && (
                          <span
                            className="pill p-gray shrink-0 truncate text-[10px]"
                            style={{ maxWidth: "40%" }}
                            title={lead.notes}
                          >
                            {lead.notes}
                          </span>
                        )}
                      </div>
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
                          style={{ border: "1px solid var(--border)" }}
                          title="Tahap sebelumnya"
                        >
                          <ChevronLeft className="h-3.5 w-3.5" />
                        </button>
                        <select
                          value={lead.stage}
                          onChange={(e) => changeStage.mutate({ id: lead.id, stage: e.target.value })}
                          className="cursor-pointer rounded bg-transparent text-xs capitalize"
                          style={{ color: "var(--text-muted)", border: "none", outline: "none" }}
                          aria-label="Ubah tahap lead"
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
                          style={{ border: "1px solid var(--border)" }}
                          title="Tahap berikutnya"
                        >
                          <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                  {cards.length === 0 && (
                    <p className="px-1 py-3 text-center text-xs" style={{ color: "var(--th-color)" }}>
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
            const lead = leadsLookup?.find((l) => l.id === selectedId);
            if (!lead) return null;
            return (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <PageHeader icon={Building2} title={lead.company_name} subtitle={lead.industry ?? undefined} />
                  {lead.stage === "deal" && !(convertLead.isSuccess && convertLead.variables === lead.id) && (
                    <button
                      className="btn-secondary"
                      disabled={convertLead.isPending}
                      onClick={() => convertLead.mutate(lead.id)}
                    >
                      {convertLead.isPending ? "Mengonversi..." : "Konversi ke Klien"}
                    </button>
                  )}
                </div>
                {convertLead.isSuccess && convertLead.variables === lead.id && (
                  <p className="mt-2 text-sm text-emerald-700 dark:text-emerald-400">
                    Berhasil dikonversi menjadi klien "{convertLead.data.name}".
                  </p>
                )}
                {convertLead.error && convertLead.variables === lead.id && (
                  <p className="mt-2 text-sm text-red-600 dark:text-red-400">{(convertLead.error as Error).message}</p>
                )}
                <PropertiesPanel className="mt-4 max-w-xl">
                  <PropertyRow icon={User} label="PIC">
                    {lead.contact_name ?? "—"}
                  </PropertyRow>
                  <PropertyRow icon={Users} label="Est. TKI">
                    {lead.estimated_headcount ?? "—"}
                  </PropertyRow>
                  <PropertyRow icon={CircleDollarSign} label="Nilai Potensi">
                    {formatRupiah(lead.estimated_value)}
                  </PropertyRow>
                  <PropertyRow icon={MapPin} label="Tahapan">
                    <div className="flex items-center gap-2">
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
                      {daysSince(lead.stage_changed_at) !== null && (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                          sudah {daysSince(lead.stage_changed_at)} hari di tahap ini
                        </span>
                      )}
                    </div>
                  </PropertyRow>
                  <PropertyRow icon={CalendarClock} label="Target Closing">
                    <input
                      type="date"
                      defaultValue={lead.expected_close_date ?? ""}
                      className="input w-auto py-1 text-sm"
                      onBlur={(e) => {
                        if (e.target.value !== (lead.expected_close_date ?? "")) {
                          updateLeadFields.mutate({
                            id: lead.id,
                            body: { expected_close_date: e.target.value || null },
                          });
                        }
                      }}
                    />
                  </PropertyRow>
                  {(lead.stage === "deal" || lead.stage === "gagal") && (
                    <PropertyRow icon={MessageSquareText} label="Alasan Menang/Kalah">
                      <input
                        defaultValue={lead.closed_reason ?? ""}
                        placeholder="mis. Harga cocok / Kalah tender"
                        className="input w-64 py-1 text-sm"
                        onBlur={(e) => {
                          if (e.target.value !== (lead.closed_reason ?? "")) {
                            updateLeadFields.mutate({
                              id: lead.id,
                              body: { closed_reason: e.target.value || null },
                            });
                          }
                        }}
                      />
                    </PropertyRow>
                  )}
                  {lead.last_activity_at && (
                    <PropertyRow icon={Clock} label="Aktivitas Terakhir">
                      {new Date(lead.last_activity_at).toLocaleDateString("id-ID", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </PropertyRow>
                  )}
                </PropertiesPanel>
              </>
            );
          })()}

          {selectedCompanyId && (
            <CustomFieldsSection
              entity="company"
              entityId={selectedCompanyId}
              title="Field Kustom Perusahaan"
              description="Field tambahan di level perusahaan (mis. NPWP) -- berlaku untuk semua lead dari company ini, bukan cuma lead yang sedang dibuka."
            />
          )}

          <h2 className="mt-6 font-semibold" style={{ color: "var(--text)" }}>Kontak Terlibat</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            PIC yang relevan untuk deal ini beserta perannya (mis. Decision Maker, Champion) —
            beda lead pada company yang sama boleh punya kontak/peran berbeda.
          </p>
          <ul className="mt-3 space-y-2">
            {(leadContacts ?? []).map((lc) => {
              const fieldsOpen = expandedContactFields[lc.contact.id] ?? false;
              return (
                <li
                  key={lc.id}
                  className="rounded-lg p-3 text-sm"
                  style={{ backgroundColor: "var(--hover)" }}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-[var(--accent-contrast)]"
                        style={{ backgroundColor: "var(--accent)" }}
                      >
                        {initials(lc.contact.name)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate font-medium" style={{ color: "var(--text)" }}>
                          {lc.contact.name}
                        </p>
                        {(lc.contact.email || lc.contact.phone) && (
                          <p className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
                            {lc.contact.email ?? lc.contact.phone}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        defaultValue={lc.role ?? ""}
                        placeholder="Peran (mis. Decision Maker)"
                        aria-label={`Peran ${lc.contact.name} di lead ini`}
                        className="input w-auto py-1 text-xs"
                        onBlur={(e) => {
                          const role = e.target.value.trim();
                          if (role !== (lc.role ?? "")) {
                            updateLeadContactRole.mutate({ leadContactId: lc.id, role });
                          }
                        }}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedContactFields((prev) => ({
                            ...prev,
                            [lc.contact.id]: !fieldsOpen,
                          }))
                        }
                        className="flex items-center gap-1 rounded p-1 text-xs hover:opacity-70"
                        style={{ color: "var(--text-muted)" }}
                        aria-label={`${fieldsOpen ? "Sembunyikan" : "Tampilkan"} field kustom ${lc.contact.name}`}
                        title="Field kustom kontak ini"
                      >
                        {fieldsOpen ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => removeLeadContact.mutate(lc.id)}
                        className="rounded p-1 hover:opacity-70"
                        style={{ color: "var(--text-muted)" }}
                        aria-label={`Hapus ${lc.contact.name} dari lead ini`}
                        title="Hapus"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  {fieldsOpen && (
                    <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--border)" }}>
                      <CustomFieldsSection
                        entity="contact"
                        entityId={lc.contact.id}
                        title="Field Kustom Kontak"
                        compact
                      />
                    </div>
                  )}
                </li>
              );
            })}
            {leadContacts?.length === 0 && (
              <li className="text-sm" style={{ color: "var(--text-muted)" }}>
                Belum ada kontak yang ditautkan ke lead ini.
              </li>
            )}
          </ul>
          <form
            className="mt-3 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const contactId = (form.elements.namedItem("contact_id") as HTMLSelectElement).value;
              const role = (form.elements.namedItem("role") as HTMLInputElement).value;
              if (!selectedId || !contactId) return;
              addLeadContact.mutate({ id: selectedId, contactId, role });
              form.reset();
            }}
          >
            <select name="contact_id" required className="input w-auto" aria-label="Pilih kontak">
              <option value="">Pilih kontak company...</option>
              {(companyContacts ?? [])
                .filter((c) => !(leadContacts ?? []).some((lc) => lc.contact.id === c.id))
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </select>
            <input name="role" placeholder="Peran (opsional)" className="input w-auto" />
            <button className="btn-secondary" disabled={addLeadContact.isPending}>
              + Tambah PIC
            </button>
          </form>
          {addLeadContact.error && (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">
              {(addLeadContact.error as Error).message}
            </p>
          )}

          {selectedId && (
            <CustomFieldsSection
              entity="lead"
              entityId={selectedId}
              title="Field Kustom Lead"
              description="Field tambahan yang dikonfigurasi untuk semua lead (mis. Tipe Layanan) -- hapus/tambah field di sini berlaku untuk seluruh pipeline, bukan cuma lead ini."
            />
          )}

          <h2 className="mt-6 font-semibold" style={{ color: "var(--text)" }}>Aktivitas</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            Isi "Jadwalkan follow-up" untuk membuat tugas dengan pengingat -- muncul di
            widget "Tugas Jatuh Tempo" di bagian atas Pipeline.
          </p>
          <form
            className="mt-3 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const input = form.elements.namedItem("content") as HTMLInputElement;
              const dueInput = form.elements.namedItem("due_at") as HTMLInputElement;
              if (input.value.trim()) {
                addActivity.mutate({
                  id: selectedId,
                  content: input.value,
                  dueAt: dueInput.value ? new Date(dueInput.value).toISOString() : undefined,
                });
                form.reset();
              }
            }}
          >
            <input name="content" placeholder="Tambah catatan aktivitas..." className="input flex-1" />
            <input
              name="due_at"
              type="datetime-local"
              className="input w-auto"
              title="Jadwalkan follow-up (opsional)"
            />
            <button className="btn-secondary">Tambah</button>
          </form>
          <ul className="mt-3 space-y-2">
            {(activities ?? []).map((a) => {
              const isTask = a.due_at !== null;
              const isDone = a.completed_at !== null;
              const isOverdue = isTask && !isDone && new Date(a.due_at as string) < new Date();
              return (
                <li
                  key={a.id}
                  className="flex items-start gap-2 rounded-lg p-3 text-sm"
                  style={{ backgroundColor: "var(--hover)" }}
                >
                  {isTask && (
                    <input
                      type="checkbox"
                      checked={isDone}
                      onChange={(e) =>
                        completeActivity.mutate({ activityId: a.id, completed: e.target.checked })
                      }
                      className="mt-0.5"
                      aria-label={`Tandai selesai: ${a.content}`}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <span className="font-medium" style={{ color: "var(--th-color)" }}>
                      [{a.activity_type}]
                    </span>{" "}
                    <span
                      style={
                        isDone
                          ? { textDecoration: "line-through", color: "var(--text-muted)" }
                          : undefined
                      }
                    >
                      {a.content}
                    </span>
                    {isTask && !isDone && (
                      <span
                        className={`ml-2 text-xs font-medium ${
                          isOverdue ? "text-red-600 dark:text-red-400" : ""
                        }`}
                        style={isOverdue ? undefined : { color: "var(--text-muted)" }}
                      >
                        {isOverdue ? "Terlambat — " : "Jatuh tempo "}
                        {new Date(a.due_at as string).toLocaleDateString("id-ID", {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
            {activities?.length === 0 && (
              <li className="text-sm" style={{ color: "var(--text-muted)" }}>
                Belum ada aktivitas.
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
