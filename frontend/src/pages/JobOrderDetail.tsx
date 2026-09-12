import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  PIPELINE_STAGES as PIPELINE_STEPS_BASE,
  TERMINAL_STAGE_DOT as TERMINAL_DOT,
  TERMINAL_STAGE_LABEL as TERMINAL_STATUS_LABEL,
} from "../lib/pipelineStages";
import {
  ArrowLeft,
  Bot,
  Briefcase,
  Building2,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  CircleDollarSign,
  Download,
  FileText,
  Gift,
  Mail,
  Magnet,
  MapPin,
  Package,
  Phone,
  Plus,
  Users,
  User as UserIcon,
} from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { Badge, Button, Card, PillTabs } from "../components/ui";
import { CalloutBlock, PageHeader, PropertiesPanel, PropertyRow, initials } from "../components/workspace";
import type { JobOrder } from "./JobOrders";
import type { ClientRow } from "./Clients";

/** Detail Job Order (Fase 21 item 3) — rumah baru untuk unifikasi "satu
 * tombol Jadwalkan Interview" yang bercabang ke sistem human (InterviewSchedule,
 * existing) atau AI (AIInterviewResponse, existing) — backend TETAP 2 sistem
 * terpisah sesuai PRD, cuma UI-nya disatukan di sini. Juga rumah untuk
 * "Catat Offering Call" (item 2), independen dari offering letter+esign
 * yang sudah ada di Candidates.tsx.
 */

interface Placement {
  id: string;
  candidate_id: string;
  job_order_id: string;
  status: string;
  offering_call_done: boolean;
  offering_call_at: string | null;
  offering_letter_object_key: string | null;
  offering_signed_at: string | null;
  rejection_note: string | null;
}

interface OnboardingInvite {
  id: string;
  placement_id: string;
  status: "invited" | "submitted" | "applied" | "revoked";
  submitted_at: string | null;
  expires_at: string;
  applied_at: string | null;
}

interface OnboardingInviteDetail {
  invite: OnboardingInvite;
  submitted_data: Record<string, unknown>;
  documents: {
    id: string;
    document_type: string;
    file_name: string;
    file_size: number;
    uploaded_at: string;
    download_url: string;
  }[];
}

const ONBOARDING_INVITE_STATUS_LABEL: Record<string, string> = {
  invited: "Diundang",
  submitted: "Disubmit",
  applied: "Diterapkan",
  revoked: "Dibatalkan",
};

/** Katalog jenis dokumen onboarding -- HR memilih subset dari daftar ini
 * saat "Kirim Link Onboarding" (pola MYOHRIS "Setup job assessments for
 * onboard"). Kandidat di halaman self-service hanya melihat jenis yang
 * dipilih di sini, bukan semuanya. */
const ONBOARDING_DOC_TYPES: { key: string; label: string }[] = [
  { key: "ktp", label: "KTP" },
  { key: "npwp", label: "NPWP" },
  { key: "kartu_keluarga", label: "Kartu Keluarga (KK)" },
  { key: "ijazah", label: "Ijazah" },
  { key: "skck", label: "SKCK" },
  { key: "sim", label: "SIM" },
  { key: "buku_tabungan", label: "Buku Tabungan" },
  { key: "paklaring", label: "Paklaring" },
  { key: "surat_keterangan_sehat", label: "Surat Keterangan Sehat" },
  { key: "bpjs_kesehatan", label: "BPJS Kesehatan" },
  { key: "bpjs_ketenagakerjaan", label: "BPJS Ketenagakerjaan" },
];
const DEFAULT_ONBOARDING_DOC_TYPES = ["ktp", "npwp", "skck"];

interface Candidate {
  id: string;
  full_name: string;
}

interface Interview {
  id: string;
  candidate_id: string;
  job_order_id: string;
  interviewer_id: string | null;
  scheduled_at: string;
  location: string | null;
  meeting_url: string | null;
  status: string;
  interview_type: string;
  feedback: string | null;
  score: number | null;
}

interface UserOption {
  id: string;
  full_name: string;
}

interface JobOrderTemplateT {
  id: string;
  name: string;
  is_active: boolean;
}

// Kolom Kanban tab "Candidates" (§1.8) -- ikuti tahap PlacementStatus persis,
// menggantikan tab "Pipeline Kandidat" (list+ProgressStep) sejak migrasi
// Candidates.tsx (2026-09-06). Sumber label/warna tahap: lib/pipelineStages.ts
// (riwayat penyederhanaan tahap ada di komentar file itu).

/** OJT kondisional per Job Order (`requires_ojt`) -- sebagian posisi/klien
 * tidak butuh tahap ini sama sekali, jadi dilewati di Kanban+dropdown
 * daripada selalu ditampilkan sebagai kolom kosong yang membingungkan. */
function pipelineSteps(requiresOjt: boolean) {
  return requiresOjt ? PIPELINE_STEPS_BASE : PIPELINE_STEPS_BASE.filter((s) => s.key !== "ojt");
}
function kanbanColumns(requiresOjt: boolean) {
  return [
    ...pipelineSteps(requiresOjt).map((s) => ({ ...s, statuses: [s.key] })),
    { key: "terminal", label: "Gagal / Dibatalkan", dot: TERMINAL_DOT, statuses: ["gagal", "dibatalkan"] },
  ];
}
function allStatusOptions(requiresOjt: boolean) {
  return [
    ...pipelineSteps(requiresOjt).map((s) => ({ value: s.key, label: s.label })),
    { value: "gagal", label: "Gagal" },
    { value: "dibatalkan", label: "Dibatalkan" },
  ];
}

export default function JobOrderDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [interviewModeFor, setInterviewModeFor] = useState<string | null>(null);
  const [docTemplateId, setDocTemplateId] = useState("");
  // Archetype C (Detail/Profile) -- tab horizontal menggantikan seksi yang
  // sebelumnya ditumpuk vertikal, tanpa mengubah logic/section-nya sendiri.
  const [tab, setTab] = useState<"info" | "dokumen" | "candidates">("info");
  // Tab "Candidates" (Kanban §1.8, pindahan dari Candidates.tsx 2026-09-06):
  // klik kartu Placement -> panel detail lebar penuh di bawah board (bukan
  // expand sempit di dalam kolom), pola sama seperti Leads.tsx.
  const [selectedPlacementId, setSelectedPlacementId] = useState<string | null>(null);
  const [showAddCandidate, setShowAddCandidate] = useState(false);
  const [showOfferingForm, setShowOfferingForm] = useState(false);
  const [showOnboardForm, setShowOnboardForm] = useState(false);
  const [showOnboardingInviteReview, setShowOnboardingInviteReview] = useState(false);
  const [feedbackOpenId, setFeedbackOpenId] = useState<string | null>(null);
  // Alasan gagal/batal (pengganti tahap "kirim klien"/"screening klien" yang
  // dibuang 2026-09-07) -- ditanya lewat modal kecil ini SEBELUM status
  // benar-benar dipindah ke terminal, bukan field opsional yang gampang
  // dilewatkan.
  const [pendingTerminal, setPendingTerminal] = useState<{ placementId: string; status: string } | null>(
    null
  );
  const [terminalNote, setTerminalNote] = useState("");
  // Pilih dokumen yang diminta SEBELUM link onboarding dikirim (pola MYOHRIS
  // "Setup job assessments for onboard") -- bukan langsung kirim dengan set
  // dokumen tetap seperti sebelumnya.
  const [pendingOnboardingInvite, setPendingOnboardingInvite] = useState<string | null>(null);
  const [onboardingDocTypes, setOnboardingDocTypes] = useState<string[]>(
    DEFAULT_ONBOARDING_DOC_TYPES
  );

  const { data: jo } = useQuery({
    queryKey: ["job-order", id],
    queryFn: () => api.get<JobOrder>(`/recruitment/job-orders/${id}`),
    enabled: Boolean(id),
  });
  const { data: docTemplates } = useQuery({
    queryKey: ["job-order-templates"],
    queryFn: () => api.get<JobOrderTemplateT[]>("/recruitment/job-order-templates?active_only=true"),
  });
  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const { data: placements } = useQuery({
    queryKey: ["placements", id],
    queryFn: () => api.get<Placement[]>(`/recruitment/placements?job_order_id=${id}`),
    enabled: Boolean(id),
  });
  const { data: candidates } = useQuery({
    queryKey: ["candidates-lookup"],
    queryFn: () => api.get<Candidate[]>("/recruitment/candidates?limit=1000"),
  });
  const { data: users } = useQuery({
    queryKey: ["users-for-interview"],
    queryFn: () => api.get<UserOption[]>("/auth/users"),
    enabled: Boolean(interviewModeFor),
  });
  const { data: interviews } = useQuery({
    queryKey: ["interviews-jo", id],
    queryFn: () => api.get<Interview[]>("/recruitment/interviews"),
    enabled: tab === "candidates",
  });
  const { data: onboardingInvites } = useQuery({
    queryKey: ["onboarding-invites", selectedPlacementId],
    queryFn: () =>
      api.get<OnboardingInvite[]>(`/employees/onboarding-invites?placement_id=${selectedPlacementId}`),
    enabled: Boolean(selectedPlacementId),
  });
  const currentInvite = onboardingInvites?.[0];
  const { data: onboardingInviteDetail } = useQuery({
    queryKey: ["onboarding-invite-detail", currentInvite?.id],
    queryFn: () =>
      api.get<OnboardingInviteDetail>(`/employees/onboarding-invites/${currentInvite!.id}`),
    enabled: Boolean(currentInvite?.id) && showOnboardingInviteReview,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["placements", id] });
  const invalidateOnboardingInvites = () =>
    qc.invalidateQueries({ queryKey: ["onboarding-invites", selectedPlacementId] });

  const scheduleInterview = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/recruitment/interviews", body),
    onSuccess: () => {
      setInterviewModeFor(null);
      qc.invalidateQueries({ queryKey: ["interviews-jo", id] });
    },
  });
  const updateInterview = useMutation({
    mutationFn: ({ id: interviewId, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/recruitment/interviews/${interviewId}`, body),
    onSuccess: () => {
      setFeedbackOpenId(null);
      qc.invalidateQueries({ queryKey: ["interviews-jo", id] });
    },
  });
  const recordOfferingCall = useMutation({
    mutationFn: (placementId: string) =>
      api.post(`/recruitment/placements/${placementId}/offering-call`, {}),
    onSuccess: invalidate,
  });
  // PRD v3.0 §4 aksi 2/3 "Offering": surat penawaran PDF branded -> esign
  // (pindahan dari Candidates.tsx, 2026-09-06).
  const sendOffering = useMutation({
    mutationFn: ({ placementId, body }: { placementId: string; body: Record<string, unknown> }) =>
      api.post(`/recruitment/placements/${placementId}/offering`, body),
    onSuccess: () => {
      setShowOfferingForm(false);
      invalidate();
    },
  });
  const onboardEmployee = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/employees/onboard", body),
    onSuccess: () => {
      setShowOnboardForm(false);
      invalidate();
    },
  });
  const createOnboardingInvite = useMutation({
    mutationFn: ({ placementId, documentTypes }: { placementId: string; documentTypes: string[] }) =>
      api.post<{ invite: OnboardingInvite; onboarding_url: string }>(
        "/employees/onboarding-invites",
        { placement_id: placementId, document_types: documentTypes }
      ),
    onSuccess: () => {
      setPendingOnboardingInvite(null);
      invalidateOnboardingInvites();
    },
  });
  const applyOnboardingInvite = useMutation({
    mutationFn: (inviteId: string) =>
      api.post(`/employees/onboarding-invites/${inviteId}/apply`, {}),
    onSuccess: () => {
      setShowOnboardingInviteReview(false);
      invalidateOnboardingInvites();
      invalidate();
    },
  });
  const requestOnboardingResubmission = useMutation({
    mutationFn: (inviteId: string) =>
      api.post(`/employees/onboarding-invites/${inviteId}/request-resubmission`, {}),
    onSuccess: () => {
      setShowOnboardingInviteReview(false);
      invalidateOnboardingInvites();
    },
  });
  const revokeOnboardingInvite = useMutation({
    mutationFn: (inviteId: string) =>
      api.post(`/employees/onboarding-invites/${inviteId}/revoke`, {}),
    onSuccess: () => {
      setShowOnboardingInviteReview(false);
      invalidateOnboardingInvites();
    },
  });
  const createPlacement = useMutation({
    mutationFn: (candidateId: string) =>
      api.post("/recruitment/placements", { candidate_id: candidateId, job_order_id: id }),
    onSuccess: () => {
      setShowAddCandidate(false);
      invalidate();
    },
  });
  const changePlacementStatus = useMutation({
    mutationFn: ({ placementId, status, note }: { placementId: string; status: string; note?: string }) =>
      api.patch(`/recruitment/placements/${placementId}`, { status, note }),
    onSuccess: invalidate,
  });
  const TERMINAL_KEYS = ["gagal", "dibatalkan"];
  /** Rute semua perubahan status placement lewat sini -- kalau tujuannya
   * terminal (gagal/dibatalkan), tahan dulu lewat modal alasan, jangan
   * langsung PATCH. */
  function requestPlacementStatus(placementId: string, status: string) {
    if (TERMINAL_KEYS.includes(status)) {
      setTerminalNote("");
      setPendingTerminal({ placementId, status });
    } else {
      changePlacementStatus.mutate({ placementId, status });
    }
  }
  const generateDocument = useMutation({
    mutationFn: () =>
      api.post(`/recruitment/job-orders/${id}/generate-document`, { template_id: docTemplateId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job-order", id] }),
  });

  async function openGeneratedDocument() {
    const { url } = await api.get<{ url: string }>(
      `/recruitment/job-orders/${id}/generated-document/download-url`
    );
    window.open(url, "_blank");
  }

  function candidateName(candidateId: string) {
    return candidates?.find((c) => c.id === candidateId)?.full_name ?? candidateId;
  }
  function clientName(clientId: string) {
    return clients?.find((c) => c.id === clientId)?.name ?? "-";
  }

  function handleScheduleHuman(e: FormEvent<HTMLFormElement>, placement: Placement) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    scheduleInterview.mutate({
      candidate_id: placement.candidate_id,
      job_order_id: id,
      interviewer_id: form.get("interviewer_id") || null,
      scheduled_at: form.get("scheduled_at"),
      location: form.get("location") || null,
      meeting_url: form.get("meeting_url") || null,
      interview_type: form.get("interview_type") || "internal",
    });
  }

  if (!jo) {
    return <p className="text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>;
  }

  const steps = pipelineSteps(jo.requires_ojt);
  const columns = kanbanColumns(jo.requires_ojt);
  const statusOptions = allStatusOptions(jo.requires_ojt);

  return (
    <div className="space-y-4">
      <Link
        to="/job-orders"
        className="inline-flex items-center gap-1.5 text-xs font-medium"
        style={{ color: "var(--text-muted)" }}
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Job Orders
      </Link>

      <PageHeader icon={Magnet} title={jo.title} subtitle={clientName(jo.client_id)} />

      <PillTabs
        tabs={[
          { key: "info", label: "Info" },
          { key: "dokumen", label: "Dokumen" },
          { key: "candidates", label: `Candidates (${placements?.length ?? 0})` },
        ]}
        value={tab}
        onChange={(k) => setTab(k as typeof tab)}
      />

      {tab === "info" && (
      <Card>
        <PropertiesPanel>
          <PropertyRow icon={MapPin} label="Area">{jo.area ?? "—"}</PropertyRow>
          <PropertyRow icon={Users} label="Kebutuhan">{jo.headcount} orang</PropertyRow>
          <PropertyRow icon={CircleDollarSign} label="Range Gaji">
            {formatRupiah(jo.salary_min)} – {formatRupiah(jo.salary_max)}
          </PropertyRow>
          <PropertyRow icon={Clock} label="Jam Kerja">
            {jo.working_hours_start && jo.working_hours_end
              ? `${jo.working_hours_start.slice(0, 5)} – ${jo.working_hours_end.slice(0, 5)}`
              : "—"}
          </PropertyRow>
          <PropertyRow icon={Calendar} label="Hari Kerja">
            {jo.working_days.length ? jo.working_days.join(", ") : "—"}
          </PropertyRow>
          <PropertyRow icon={Gift} label="Benefit">
            {jo.benefits.length ? jo.benefits.join(", ") : "—"}
          </PropertyRow>
          <PropertyRow icon={Building2} label="Lokasi Kerja">
            {jo.remote ? "Remote" : jo.office_address ?? "—"}
          </PropertyRow>
          <PropertyRow icon={Briefcase} label="Posisi / Level">
            {[jo.position, jo.level, jo.industry].filter(Boolean).join(" · ") || "—"}
          </PropertyRow>
          <PropertyRow icon={Clock} label="Detail Kontrak">
            {[jo.contract_detail, jo.experience_level].filter(Boolean).join(" · ") || "—"}
          </PropertyRow>
          <PropertyRow icon={Package} label="Paket Benefit">
            {jo.package_detail ?? "—"}
          </PropertyRow>
        </PropertiesPanel>
      </Card>
      )}

      {tab === "dokumen" && (
      <Card title="Dokumen Job Order" subtitle="Fase 21 item 4 — generate dari template">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={docTemplateId}
            onChange={(e) => setDocTemplateId(e.target.value)}
            className="input w-auto py-1 text-xs"
          >
            <option value="">-- Pilih template --</option>
            {(docTemplates ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            disabled={!docTemplateId}
            loading={generateDocument.isPending}
            onClick={() => generateDocument.mutate()}
          >
            <FileText className="h-3.5 w-3.5" /> Generate Dokumen JO
          </Button>
          {jo.has_generated_document && (
            <Button size="sm" variant="secondary" onClick={openGeneratedDocument}>
              <Download className="h-3.5 w-3.5" /> Unduh Dokumen
              {jo.generated_document_at
                ? ` (${new Date(jo.generated_document_at).toLocaleDateString("id-ID")})`
                : ""}
            </Button>
          )}
        </div>
        {docTemplates?.length === 0 && (
          <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
            Belum ada template Job Order aktif. Buat template dulu lewat API
            /recruitment/job-order-templates.
          </p>
        )}
        {generateDocument.error && (
          <p className="mt-2 text-xs text-red-600 dark:text-red-400">
            {(generateDocument.error as Error).message}
          </p>
        )}
      </Card>
      )}

      {tab === "candidates" && (
      <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
          Candidates
        </h2>
        <Button size="sm" variant="secondary" onClick={() => setShowAddCandidate((v) => !v)}>
          <Plus className="h-3.5 w-3.5" /> Usulkan Kandidat
        </Button>
      </div>

      {showAddCandidate && (
        <Card>
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const candidateId = form.get("candidate_id");
              if (!candidateId) return;
              // Kandidat yang sebelumnya gagal/dibatalkan di JO ini TIDAK bisa
              // dibuatkan Placement baru (unique constraint candidate+JO di
              // backend) -- reaktivasi placement lama ke Sourcing, bukan create.
              const existing = (placements ?? []).find((p) => p.candidate_id === String(candidateId));
              if (existing) {
                changePlacementStatus.mutate({ placementId: existing.id, status: "disourcing" });
                setShowAddCandidate(false);
              } else {
                createPlacement.mutate(String(candidateId));
              }
            }}
          >
            <select name="candidate_id" required className="input w-64 py-1 text-xs">
              <option value="">-- Pilih kandidat dari Talent Pool --</option>
              {(candidates ?? [])
                .filter((c) => {
                  const existing = (placements ?? []).find((p) => p.candidate_id === c.id);
                  return !existing || existing.status in TERMINAL_STATUS_LABEL;
                })
                .map((c) => {
                  const existing = (placements ?? []).find((p) => p.candidate_id === c.id);
                  return (
                    <option key={c.id} value={c.id}>
                      {c.full_name}
                      {existing ? ` (sebelumnya: ${TERMINAL_STATUS_LABEL[existing.status]})` : ""}
                    </option>
                  );
                })}
            </select>
            <Button
              type="submit"
              size="sm"
              loading={createPlacement.isPending || changePlacementStatus.isPending}
            >
              Tambahkan ke Sourcing
            </Button>
          </form>
          {createPlacement.error && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              {(createPlacement.error as Error).message}
            </p>
          )}
        </Card>
      )}

      <div className="flex gap-3 overflow-x-auto pb-2">
        {columns.map((col) => {
          const cards = (placements ?? []).filter((p) => col.statuses.includes(p.status));
          return (
            <div
              key={col.key}
              className="w-56 shrink-0 rounded-md"
              style={{ backgroundColor: "var(--hover)" }}
            >
              <div className="flex items-center gap-2 px-3 pt-3 pb-1">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: col.dot }}
                />
                <span className="truncate text-sm font-medium" style={{ color: "var(--text)" }}>
                  {col.label}
                </span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {cards.length}
                </span>
              </div>
              <div className="space-y-2 px-2 pb-3">
                {cards.map((p) => {
                  const stepIdx = steps.findIndex((s) => s.key === p.status);
                  return (
                    <div
                      key={p.id}
                      onClick={() => setSelectedPlacementId(p.id === selectedPlacementId ? null : p.id)}
                      className="rounded-md p-2.5 shadow-sm transition-shadow hover:shadow"
                      style={{
                        backgroundColor: "var(--bg-elevated)",
                        border:
                          selectedPlacementId === p.id
                            ? "1px solid var(--accent)"
                            : "1px solid var(--border)",
                        cursor: "pointer",
                      }}
                    >
                      <div className="flex items-center gap-1.5">
                        <span
                          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-[var(--accent-contrast)]"
                          style={{ backgroundColor: "var(--accent)" }}
                        >
                          {initials(candidateName(p.candidate_id))}
                        </span>
                        <p className="truncate text-sm font-medium" style={{ color: "var(--text)" }}>
                          {candidateName(p.candidate_id)}
                        </p>
                      </div>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {p.offering_call_done && (
                          <span className="pill p-green text-[10px]">Offering call ✓</span>
                        )}
                        {p.offering_signed_at ? (
                          <span className="pill p-green text-[10px]">Surat ditandatangani ✓</span>
                        ) : p.offering_letter_object_key ? (
                          <span className="pill p-yellow text-[10px]">Surat terkirim</span>
                        ) : null}
                      </div>
                      {p.rejection_note && (
                        <p
                          className="mt-1.5 line-clamp-2 text-[10px]"
                          style={{ color: "var(--text-muted)" }}
                          title={p.rejection_note}
                        >
                          {p.rejection_note}
                        </p>
                      )}
                      {stepIdx >= 0 && (
                        <div
                          className="mt-2 flex items-center justify-between text-xs"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            disabled={stepIdx === 0}
                            onClick={() => requestPlacementStatus(p.id, steps[stepIdx - 1].key)}
                            className="rounded px-1 py-0.5 disabled:opacity-25"
                            style={{ border: "1px solid var(--border)" }}
                            title="Tahap sebelumnya"
                          >
                            <ChevronLeft className="h-3.5 w-3.5" />
                          </button>
                          <select
                            value={p.status}
                            onChange={(e) => requestPlacementStatus(p.id, e.target.value)}
                            className="cursor-pointer rounded bg-transparent text-[11px]"
                            style={{ color: "var(--text-muted)", border: "none", outline: "none" }}
                          >
                            {statusOptions.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                          <button
                            disabled={stepIdx === steps.length - 1}
                            onClick={() => requestPlacementStatus(p.id, steps[stepIdx + 1].key)}
                            className="rounded px-1 py-0.5 disabled:opacity-25"
                            style={{ border: "1px solid var(--border)" }}
                            title="Tahap berikutnya"
                          >
                            <ChevronRight className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                      {stepIdx < 0 && (
                        <div className="mt-2" onClick={(e) => e.stopPropagation()}>
                          <select
                            value={p.status}
                            onChange={(e) => requestPlacementStatus(p.id, e.target.value)}
                            className="input w-full py-0.5 text-[11px]"
                          >
                            {statusOptions.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  );
                })}
                {cards.length === 0 && (
                  <p className="px-1 py-3 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                    Kosong
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {(placements ?? []).length === 0 && (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Belum ada kandidat di-sourcing untuk job order ini.
        </p>
      )}

      {selectedPlacementId && (() => {
        const p = (placements ?? []).find((pl) => pl.id === selectedPlacementId);
        if (!p) return null;
        const candidateInterviews = (interviews ?? []).filter(
          (i) => i.candidate_id === p.candidate_id && i.job_order_id === id
        );
        return (
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <PageHeader icon={UserIcon} title={candidateName(p.candidate_id)} />
              {p.status in TERMINAL_STATUS_LABEL && (
                <Badge tone="danger">{TERMINAL_STATUS_LABEL[p.status]}</Badge>
              )}
            </div>
            {p.rejection_note && (
              <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
                <span className="font-medium" style={{ color: "var(--text)" }}>Alasan:</span>{" "}
                {p.rejection_note}
              </p>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setInterviewModeFor(interviewModeFor === p.id ? null : p.id)}
              >
                Jadwalkan Interview
              </Button>
              <Button
                size="sm"
                variant={p.offering_call_done ? "secondary" : "primary"}
                disabled={p.offering_call_done || recordOfferingCall.isPending}
                onClick={() => recordOfferingCall.mutate(p.id)}
              >
                <Phone className="h-3.5 w-3.5" />
                {p.offering_call_done
                  ? `Offering call ✓ ${p.offering_call_at ? new Date(p.offering_call_at).toLocaleDateString("id-ID") : ""}`
                  : "Catat Offering Call"}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setShowOfferingForm((v) => !v)}>
                <Mail className="h-3.5 w-3.5" />
                {p.offering_signed_at
                  ? `Surat ditandatangani ✓ ${new Date(p.offering_signed_at).toLocaleDateString("id-ID")}`
                  : p.offering_letter_object_key
                    ? "Surat terkirim — kirim ulang?"
                    : "Kirim Surat Penawaran"}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setShowOnboardForm((v) => !v)}>
                Onboard jadi Karyawan
              </Button>
              {!currentInvite || currentInvite.status === "revoked" ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setOnboardingDocTypes(DEFAULT_ONBOARDING_DOC_TYPES);
                    setPendingOnboardingInvite(p.id);
                  }}
                >
                  <Mail className="h-3.5 w-3.5" /> Kirim Link Onboarding
                </Button>
              ) : (
                <>
                  <Badge tone={currentInvite.status === "applied" ? "success" : "info"}>
                    Onboarding: {ONBOARDING_INVITE_STATUS_LABEL[currentInvite.status]}
                  </Badge>
                  {currentInvite.status === "submitted" && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setShowOnboardingInviteReview((v) => !v)}
                    >
                      Review Submission
                    </Button>
                  )}
                </>
              )}
            </div>

            {createOnboardingInvite.data && (
              <CalloutBlock tone="success">
                Link onboarding dibuat (email otomatis terkirim ke kandidat kalau alamat emailnya
                ada). Bagikan juga secara manual kalau perlu (mis. WhatsApp):
                <br />
                <code className="text-xs">{createOnboardingInvite.data.onboarding_url}</code>
                <Button
                  size="sm"
                  variant="secondary"
                  className="ml-2"
                  onClick={() =>
                    navigator.clipboard.writeText(createOnboardingInvite.data!.onboarding_url)
                  }
                >
                  Salin Link
                </Button>
              </CalloutBlock>
            )}

            {showOnboardingInviteReview && currentInvite && onboardingInviteDetail && (
              <div className="mt-3 space-y-3 rounded-lg p-3" style={{ backgroundColor: "var(--hover)" }}>
                <p className="text-xs font-semibold" style={{ color: "var(--text)" }}>
                  Review Data Onboarding
                </p>
                <dl className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                  {Object.entries(onboardingInviteDetail.submitted_data).map(([k, v]) => (
                    <div key={k}>
                      <dt style={{ color: "var(--text-muted)" }}>{k}</dt>
                      <dd style={{ color: "var(--text)" }}>
                        {typeof v === "object" ? JSON.stringify(v) : String(v ?? "-")}
                      </dd>
                    </div>
                  ))}
                </dl>
                {onboardingInviteDetail.documents.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {onboardingInviteDetail.documents.map((d) => (
                      <a
                        key={d.id}
                        href={d.download_url}
                        target="_blank"
                        rel="noreferrer"
                        className="pill p-gray text-xs hover:underline"
                      >
                        <Download className="h-3 w-3" /> {d.document_type}: {d.file_name}
                      </a>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    loading={applyOnboardingInvite.isPending}
                    onClick={() => applyOnboardingInvite.mutate(currentInvite.id)}
                  >
                    Terapkan
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={requestOnboardingResubmission.isPending}
                    onClick={() => requestOnboardingResubmission.mutate(currentInvite.id)}
                  >
                    Tolak, Minta Ulang
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    loading={revokeOnboardingInvite.isPending}
                    onClick={() => revokeOnboardingInvite.mutate(currentInvite.id)}
                  >
                    Batalkan Link
                  </Button>
                </div>
                {(applyOnboardingInvite.error || requestOnboardingResubmission.error) && (
                  <p className="text-xs text-red-600 dark:text-red-400">
                    {(
                      (applyOnboardingInvite.error || requestOnboardingResubmission.error) as Error
                    ).message}
                  </p>
                )}
              </div>
            )}

            {interviewModeFor === p.id && (
              <div className="mt-3 space-y-3 rounded-lg p-3" style={{ backgroundColor: "var(--hover)" }}>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => navigate(`/ai-interview?candidate_id=${p.candidate_id}`)}
                  >
                    <Bot className="h-3.5 w-3.5" /> Mode AI — buka AI Interview
                  </Button>
                  <span className="self-center text-xs" style={{ color: "var(--text-muted)" }}>
                    atau isi jadwal manusia di bawah:
                  </span>
                </div>
                <form
                  onSubmit={(e) => handleScheduleHuman(e, p)}
                  className="grid grid-cols-1 gap-2 sm:grid-cols-2"
                >
                  <select name="interview_type" defaultValue="internal" className="input py-1 text-xs">
                    <option value="internal">Interview Rekruter (internal)</option>
                    <option value="klien">Interview User (klien)</option>
                  </select>
                  <select name="interviewer_id" className="input py-1 text-xs">
                    <option value="">-- Pewawancara (opsional) --</option>
                    {(users ?? []).map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name}
                      </option>
                    ))}
                  </select>
                  <input
                    name="scheduled_at"
                    type="datetime-local"
                    required
                    className="input py-1 text-xs"
                  />
                  <input name="location" placeholder="Lokasi" className="input py-1 text-xs" />
                  <input
                    name="meeting_url"
                    placeholder="Link meeting (opsional)"
                    className="input py-1 text-xs sm:col-span-2"
                  />
                  <Button
                    type="submit"
                    size="sm"
                    loading={scheduleInterview.isPending}
                    className="sm:col-span-2"
                  >
                    <UserIcon className="h-3.5 w-3.5" /> Jadwalkan Interview Manusia
                  </Button>
                </form>
                {scheduleInterview.error && (
                  <p className="text-xs text-red-600 dark:text-red-400">
                    {(scheduleInterview.error as Error).message}
                  </p>
                )}
              </div>
            )}

            <div className="mt-3 space-y-1.5">
              <p className="text-xs font-semibold" style={{ color: "var(--text)" }}>
                Interview terjadwal
              </p>
              {candidateInterviews.map((i) => (
                <div key={i.id} className="text-xs" style={{ color: "var(--text-muted)" }}>
                  <span
                    className={`pill ${i.interview_type === "klien" ? "p-violet" : "p-blue"} mr-1 text-[10px]`}
                  >
                    {i.interview_type === "klien" ? "Klien" : "Internal"}
                  </span>
                  {new Date(i.scheduled_at).toLocaleString("id-ID")}
                  {i.location ? ` · ${i.location}` : ""} · <span className="capitalize">{i.status}</span>
                  {i.score !== null && (
                    <span className="ml-1 pill p-green text-[10px]">Skor {i.score}</span>
                  )}
                  {" · "}
                  <button
                    type="button"
                    className="hover:underline"
                    style={{ color: "var(--accent)" }}
                    onClick={() => setFeedbackOpenId(feedbackOpenId === i.id ? null : i.id)}
                  >
                    {i.feedback ? "Lihat/ubah feedback" : "Isi feedback"}
                  </button>
                  {i.feedback && feedbackOpenId !== i.id && <p className="mt-0.5 italic">"{i.feedback}"</p>}
                  {feedbackOpenId === i.id && (
                    <form
                      className="mt-1 flex flex-col gap-1.5 rounded p-2"
                      style={{ backgroundColor: "var(--hover)" }}
                      onSubmit={(e) => {
                        e.preventDefault();
                        const form = new FormData(e.currentTarget);
                        updateInterview.mutate({
                          id: i.id,
                          body: {
                            feedback: form.get("feedback") || null,
                            score: form.get("score") ? Number(form.get("score")) : null,
                          },
                        });
                      }}
                    >
                      <textarea
                        name="feedback"
                        defaultValue={i.feedback ?? ""}
                        placeholder="Catatan hasil interview..."
                        className="input text-xs"
                        rows={2}
                      />
                      <div className="flex items-center gap-2">
                        <input
                          name="score"
                          type="number"
                          min={0}
                          max={100}
                          defaultValue={i.score ?? ""}
                          placeholder="Skor (0-100)"
                          className="input w-28 py-1 text-xs"
                        />
                        <Button type="submit" size="sm" loading={updateInterview.isPending}>
                          Simpan
                        </Button>
                      </div>
                    </form>
                  )}
                </div>
              ))}
              {candidateInterviews.length === 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Belum ada interview terjadwal.
                </p>
              )}
            </div>

            {showOfferingForm && (
              <div className="mt-3 space-y-3 rounded-lg p-3" style={{ backgroundColor: "var(--hover)" }}>
                <p className="text-xs font-semibold" style={{ color: "var(--text)" }}>
                  Kirim Surat Penawaran
                </p>
                <form
                  className="grid grid-cols-1 gap-2 sm:grid-cols-5"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    sendOffering.mutate({
                      placementId: p.id,
                      body: {
                        signer_name: form.get("signer_name") || candidateName(p.candidate_id),
                        signer_email: form.get("signer_email"),
                        offered_salary: Number(form.get("offered_salary")) || undefined,
                        start_date: form.get("start_date") || undefined,
                      },
                    });
                  }}
                >
                  <input
                    name="offered_salary"
                    type="number"
                    required
                    placeholder="Gaji ditawarkan (Rp) *"
                    className="input py-1 text-xs"
                  />
                  <input name="start_date" type="date" className="input py-1 text-xs" />
                  <input
                    name="signer_email"
                    type="email"
                    required
                    placeholder="Email kandidat *"
                    className="input py-1 text-xs"
                  />
                  <Button type="submit" size="sm" loading={sendOffering.isPending} className="sm:col-span-2">
                    Kirim Penawaran
                  </Button>
                </form>
                {sendOffering.error && (
                  <p className="text-xs text-red-600 dark:text-red-400">
                    {(sendOffering.error as Error).message}
                  </p>
                )}
                {sendOffering.isSuccess && (
                  <CalloutBlock tone="success">
                    Surat penawaran terkirim untuk tanda tangan elektronik.
                  </CalloutBlock>
                )}
              </div>
            )}

            {showOnboardForm && (
              <div className="mt-3 space-y-3 rounded-lg p-3" style={{ backgroundColor: "var(--hover)" }}>
                <p className="text-xs font-semibold" style={{ color: "var(--text)" }}>
                  Angkat jadi Karyawan
                </p>
                <form
                  className="grid grid-cols-1 gap-2 sm:grid-cols-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    onboardEmployee.mutate({
                      placement_id: p.id,
                      employee_no: form.get("employee_no") || null,
                      join_date: form.get("join_date") || null,
                      phone: form.get("phone") || null,
                    });
                  }}
                >
                  <input
                    name="employee_no"
                    placeholder="No. Karyawan (auto jika kosong)"
                    className="input py-1 text-xs"
                  />
                  <input name="join_date" type="date" className="input py-1 text-xs" />
                  <input name="phone" placeholder="Telepon" className="input py-1 text-xs" />
                  <Button type="submit" size="sm" loading={onboardEmployee.isPending}>
                    Angkat jadi Karyawan
                  </Button>
                </form>
                {onboardEmployee.error && (
                  <p className="text-xs text-red-600 dark:text-red-400">
                    {(onboardEmployee.error as Error).message}
                  </p>
                )}
                {onboardEmployee.isSuccess && (
                  <CalloutBlock tone="success">
                    Berhasil diangkat jadi karyawan. Lihat di halaman <b>People & Ops</b> untuk
                    lengkapi kontrak, BPJS, dan asuransi.
                  </CalloutBlock>
                )}
              </div>
            )}
          </Card>
        );
      })()}
      </>
      )}

      {pendingTerminal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(15,15,15,0.45)" }}
          onClick={() => setPendingTerminal(null)}
        >
          <div
            className="w-full max-w-md rounded-md p-4"
            style={{
              backgroundColor: "var(--bg-elevated)",
              boxShadow: "0 12px 40px rgba(15,15,15,0.25)",
              border: "1px solid var(--border)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
              {pendingTerminal.status === "gagal" ? "Tandai Gagal" : "Batalkan Placement"}
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
              Alasan singkat kenapa kandidat ini gugur -- membantu rekruter lain (atau Anda
              sendiri nanti) memahami konteksnya tanpa harus menebak dari tahap terakhirnya.
            </p>
            <textarea
              autoFocus
              value={terminalNote}
              onChange={(e) => setTerminalNote(e.target.value)}
              placeholder="mis. Kandidat mengundurkan diri, dapat tawaran lain"
              rows={3}
              className="input mt-3 w-full"
            />
            <div className="mt-3 flex justify-end gap-2">
              <Button size="sm" variant="secondary" onClick={() => setPendingTerminal(null)}>
                Batal
              </Button>
              <Button
                size="sm"
                loading={changePlacementStatus.isPending}
                onClick={() => {
                  changePlacementStatus.mutate({
                    placementId: pendingTerminal.placementId,
                    status: pendingTerminal.status,
                    note: terminalNote.trim() || undefined,
                  });
                  setPendingTerminal(null);
                }}
              >
                Simpan
              </Button>
            </div>
          </div>
        </div>
      )}

      {pendingOnboardingInvite && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(15,15,15,0.45)" }}
          onClick={() => setPendingOnboardingInvite(null)}
        >
          <div
            className="w-full max-w-md rounded-md p-4"
            style={{
              backgroundColor: "var(--bg-elevated)",
              boxShadow: "0 12px 40px rgba(15,15,15,0.25)",
              border: "1px solid var(--border)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
              Pilih Dokumen yang Diminta
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
              Kandidat hanya akan melihat & bisa mengunggah jenis dokumen yang dicentang di sini.
            </p>
            <div className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {ONBOARDING_DOC_TYPES.map(({ key, label }) => (
                <label key={key} className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={onboardingDocTypes.includes(key)}
                    onChange={(e) =>
                      setOnboardingDocTypes((prev) =>
                        e.target.checked ? [...prev, key] : prev.filter((k) => k !== key)
                      )
                    }
                  />
                  {label}
                </label>
              ))}
            </div>
            {createOnboardingInvite.error && (
              <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                {(createOnboardingInvite.error as Error).message}
              </p>
            )}
            <div className="mt-3 flex justify-end gap-2">
              <Button size="sm" variant="secondary" onClick={() => setPendingOnboardingInvite(null)}>
                Batal
              </Button>
              <Button
                size="sm"
                disabled={onboardingDocTypes.length === 0}
                loading={createOnboardingInvite.isPending}
                onClick={() =>
                  createOnboardingInvite.mutate({
                    placementId: pendingOnboardingInvite,
                    documentTypes: onboardingDocTypes,
                  })
                }
              >
                Kirim
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
