import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Bot,
  Briefcase,
  Building2,
  Calendar,
  Clock,
  CircleDollarSign,
  Download,
  FileText,
  Gift,
  Magnet,
  MapPin,
  Package,
  Phone,
  Users,
  User as UserIcon,
} from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { Badge, Button, Card, ProgressStep } from "../components/ui";
import { PageHeader, PropertiesPanel, PropertyRow } from "../components/workspace";
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
}

interface Candidate {
  id: string;
  full_name: string;
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

const PIPELINE_STEPS: { key: string; label: string }[] = [
  { key: "disourcing", label: "Sourcing" },
  { key: "screening", label: "Screening" },
  { key: "interview_rekruter", label: "Interview Internal" },
  { key: "disubmit", label: "Disubmit" },
  { key: "dikirim_ke_klien", label: "Kirim Klien" },
  { key: "screening_klien", label: "Screening Klien" },
  { key: "interview_klien", label: "Interview Klien" },
  { key: "ojt", label: "OJT" },
  { key: "diusulkan", label: "Diusulkan" },
  { key: "disetujui_klien", label: "Disetujui" },
  { key: "hired", label: "Hired" },
  { key: "onboarded", label: "Onboarded" },
];
const TERMINAL_STATUS_LABEL: Record<string, string> = { gagal: "Gagal", dibatalkan: "Dibatalkan" };

export default function JobOrderDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [interviewModeFor, setInterviewModeFor] = useState<string | null>(null);
  const [docTemplateId, setDocTemplateId] = useState("");

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
    queryFn: () => api.get<Candidate[]>("/recruitment/candidates"),
  });
  const { data: users } = useQuery({
    queryKey: ["users-for-interview"],
    queryFn: () => api.get<UserOption[]>("/auth/users"),
    enabled: Boolean(interviewModeFor),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["placements", id] });

  const scheduleInterview = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/recruitment/interviews", body),
    onSuccess: () => {
      setInterviewModeFor(null);
      invalidate();
    },
  });
  const recordOfferingCall = useMutation({
    mutationFn: (placementId: string) =>
      api.post(`/recruitment/placements/${placementId}/offering-call`, {}),
    onSuccess: invalidate,
  });
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

      <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
        Pipeline Kandidat
      </h2>

      <div className="space-y-3">
        {(placements ?? []).map((p) => (
          <Card key={p.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium" style={{ color: "var(--text)" }}>
                {candidateName(p.candidate_id)}
              </p>
              {p.status in TERMINAL_STATUS_LABEL ? (
                <Badge tone="danger">{TERMINAL_STATUS_LABEL[p.status]}</Badge>
              ) : null}
            </div>

            {!(p.status in TERMINAL_STATUS_LABEL) && (
              <div className="mt-3">
                <ProgressStep
                  steps={PIPELINE_STEPS.map((s) => s.label)}
                  currentIndex={Math.max(
                    0,
                    PIPELINE_STEPS.findIndex((s) => s.key === p.status)
                  )}
                />
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-2">
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
            </div>

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
          </Card>
        ))}
        {(placements ?? []).length === 0 && (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Belum ada kandidat di-sourcing untuk job order ini.
          </p>
        )}
      </div>
    </div>
  );
}
