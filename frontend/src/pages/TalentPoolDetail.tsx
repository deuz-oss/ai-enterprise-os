import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { Badge, Card, PillTabs } from "../components/ui";
import { initials } from "../components/workspace";
import { IntakeReviewPanel, ScreeningPanel, HistoryPanel } from "./TalentPoolPanels";
import type { JobOrder } from "./JobOrders";
import { PLACEMENT_STAGE_META as PLACEMENT_STAGE_LABEL } from "../lib/pipelineStages";

/** Halaman detail kandidat (`/talent-pool/:id`) -- konsolidasi panel yang
 * dulu jadi baris expand terpisah-pisah di `TalentPool.tsx` (Review/AI/
 * Riwayat) jadi tab dalam satu profil, meniru struktur MYOHRIS. Skills/
 * Notes/Attachments SENGAJA tidak ada tab -- tidak ada model/endpoint apa
 * pun untuk itu di backend, di luar cakupan konsolidasi ini. */

interface CandidateDetail {
  candidate_id: string;
  full_name: string;
  city: string | null;
  email: string | null;
  phone: string | null;
  expected_salary: number | null;
  skills: string | null;
  readiness: string | null;
  tp_status: string;
  intake_status: string | null;
  latest_intake_id: string | null;
  needs_review_count: number;
  latest_cv_version: number;
  latest_cv_version_id: string | null;
  status: string;
  cv_file_name: string | null;
  address: string | null;
  gender: string | null;
  birthdate: string | null;
  birthplace: string | null;
  ktp_no: string | null;
  marital_status: string | null;
  blood_type: string | null;
  religion: string | null;
  education: string | null;
  education_level: string | null;
  school: string | null;
  experience_years: number | null;
  current_company: string | null;
  current_position: string | null;
  position_pool: string | null;
  job_level: string | null;
  languages: string | null;
  reference: string | null;
  source: string | null;
  description: string | null;
  has_photo: boolean;
}

interface CandidateFieldConfig {
  key: string;
  label: string;
  group: string;
  visible: boolean;
}

interface PlacementRow {
  id: string;
  candidate_id: string;
  job_order_id: string;
  status: string;
}

function formatFieldValue(key: string, row: CandidateDetail): string {
  const value = row[key as keyof CandidateDetail];
  if (value === null || value === undefined || value === "") return "-";
  if (key === "birthdate") {
    return new Date(value as string).toLocaleDateString("id-ID", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }
  if (key === "expected_salary") return formatRupiah(value as number);
  return String(value);
}

type TabKey = "ringkasan" | "proses" | "intake" | "ai" | "riwayat";

export default function TalentPoolDetail() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<TabKey>("ringkasan");

  const { data, isLoading, error } = useQuery({
    queryKey: ["talentpool-detail", id],
    queryFn: () => api.get<CandidateDetail>(`/talentpool/${id}`),
    enabled: Boolean(id),
  });
  const { data: fieldSettings } = useQuery({
    queryKey: ["talentpool-field-settings"],
    queryFn: () => api.get<{ fields: CandidateFieldConfig[] }>("/talentpool/field-settings"),
  });
  const { data: placements } = useQuery({
    queryKey: ["placements-for-candidate", id],
    queryFn: () => api.get<PlacementRow[]>(`/recruitment/placements?candidate_id=${id}`),
    enabled: Boolean(id),
  });
  const { data: jobOrders } = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });

  const jobOrderTitle = (jobOrderId: string) =>
    (jobOrders ?? []).find((j) => j.id === jobOrderId)?.title ?? jobOrderId;

  if (isLoading) {
    return <p className="text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>;
  }
  if (error || !data) {
    return (
      <p className="text-sm text-red-600">
        {error ? (error as Error).message : "Kandidat tidak ditemukan."}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <Link
        to="/talent-pool"
        className="inline-flex items-center gap-1.5 text-xs font-medium"
        style={{ color: "var(--text-muted)" }}
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Talent Pool
      </Link>

      <div className="flex items-center gap-4">
        {data.has_photo ? (
          <img
            src={`/api/v1/talentpool/candidates/${id}/photo/download`}
            alt={data.full_name}
            className="h-14 w-14 rounded-full object-cover"
            style={{ border: "1px solid var(--border)" }}
          />
        ) : (
          <span
            className="flex h-14 w-14 items-center justify-center rounded-full text-lg font-bold text-white"
            style={{ backgroundColor: "var(--accent)" }}
          >
            {initials(data.full_name)}
          </span>
        )}
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold leading-tight" style={{ color: "var(--text)" }}>
            {data.full_name}
          </h1>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {data.city ?? "-"} · {data.position_pool ?? data.job_level ?? "-"} ·{" "}
            {data.expected_salary ? formatRupiah(data.expected_salary) : "Ekspektasi gaji belum diisi"}
          </p>
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="info">{data.tp_status}</Badge>
            <Badge tone="neutral">{data.status}</Badge>
            {data.needs_review_count > 0 && (
              <Badge tone="warning">{data.needs_review_count} perlu dicek</Badge>
            )}
          </div>
        </div>
      </div>

      <PillTabs
        tabs={[
          { key: "ringkasan", label: "Ringkasan" },
          { key: "proses", label: "Proses", count: placements?.length ?? 0 },
          { key: "intake", label: "Intake & CV Standar" },
          { key: "ai", label: "AI Screening" },
          { key: "riwayat", label: "Riwayat" },
        ]}
        value={tab}
        onChange={(k) => setTab(k as TabKey)}
      />

      {tab === "ringkasan" && (
        <Card>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {(fieldSettings?.fields ?? []).map((f) => (
              <div key={f.key}>
                <dt
                  className="text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--text-muted)" }}
                >
                  {f.label}
                </dt>
                <dd style={{ color: "var(--text)" }}>{formatFieldValue(f.key, data)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      {tab === "proses" && (
        <Card>
          {(placements ?? []).length === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Belum ada proses rekrutmen untuk kandidat ini.
            </p>
          ) : (
            <ul className="space-y-2">
              {(placements ?? []).map((p) => {
                const stage = PLACEMENT_STAGE_LABEL[p.status];
                return (
                  <li key={p.id} className="flex items-center gap-2 text-sm">
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: stage?.dot ?? "#9f9f9f" }}
                    />
                    <Link to={`/job-orders/${p.job_order_id}`} className="font-medium hover:underline">
                      {jobOrderTitle(p.job_order_id)}
                    </Link>
                    <span style={{ color: "var(--text-muted)" }}>{stage?.label ?? p.status}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      )}

      {tab === "intake" &&
        (data.latest_intake_id ? (
          <IntakeReviewPanel intakeId={data.latest_intake_id} />
        ) : (
          <Card>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Belum ada intake CV untuk kandidat ini.
            </p>
          </Card>
        ))}

      {tab === "ai" && id && (
        <ScreeningPanel candidateId={id} cvFileName={data.cv_file_name} jobOrders={jobOrders ?? []} />
      )}

      {tab === "riwayat" && id && <HistoryPanel candidateId={id} />}
    </div>
  );
}
