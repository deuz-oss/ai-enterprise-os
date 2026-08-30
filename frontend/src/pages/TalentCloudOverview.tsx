import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Briefcase,
  Building2,
  Calendar,
  CalendarPlus,
  ChevronLeft,
  ChevronRight,
  Database,
  Filter,
  Gift,
  GitBranch,
  Sparkles,
  Zap,
} from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { CalloutBlock, IconBadge, initials, PageHeader, RowFrame, SeeAllLink } from "../components/notion";
import { ScoreBadge } from "../components/Ai";
import type { Lead } from "./Leads";
import type { ClientRow } from "./Clients";
import type { JobOrder } from "./JobOrders";

interface Overview {
  leads: { total: number; won: number; by_stage: Record<string, number> };
  job_orders: { open: number; filled: number };
  candidates: { total: number; by_status: Record<string, number> };
  recruitment_talent: {
    job_orders_by_stage: Record<string, number>;
    interviews_this_week: number;
  };
  ai_insight: { hint: string };
}

interface Candidate {
  id: string;
  full_name: string;
  city: string | null;
  expected_salary: number | null;
  status: string;
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
}

interface UserOption {
  id: string;
  full_name: string;
}

interface MatchItem {
  candidate_id: string;
  match_score: number;
  explain: string;
  missing: string[];
}

interface OfferingItem {
  placement_id: string;
  candidate_name: string;
  job_order_title: string;
  client_name: string;
  offered_salary: number | null;
  esign_status: string | null;
}

interface OfferingSummary {
  total_active: number;
  awaiting_signature: number;
  items: OfferingItem[];
}

interface AuditItem {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
}

interface Placement {
  id: string;
  candidate_id: string;
  job_order_id: string;
  status: string;
}

const CANDIDATE_STATUS_LABELS: Record<string, string> = {
  baru: "Baru",
  screening: "Screening",
  interview: "Interview",
  offered: "Offered",
  placed: "Placed",
  gagal: "Gagal",
  arsip: "Arsip",
};

// Warna senada dengan STATUS_DOT di Candidates.tsx — supaya bar funnel di
// sini konsisten dengan badge status di halaman Kandidat.
const CANDIDATE_STATUS_COLORS: Record<string, string> = {
  baru: "#9f9f9f",
  screening: "#2383e2",
  interview: "#5b5bd6",
  offered: "#cb912f",
  placed: "#0f7b6c",
  gagal: "#e03e3e",
  arsip: "#787774",
};

const ESIGN_STATUS_LABELS: Record<string, string> = {
  terkirim: "Terkirim",
  dilihat: "Dilihat",
  selesai: "Ditandatangani",
  ditolak: "Ditolak",
  kedaluwarsa: "Kedaluwarsa",
  gagal: "Gagal",
};

const ESIGN_STATUS_PILL: Record<string, string> = {
  terkirim: "pill p-yellow",
  dilihat: "pill p-blue",
  selesai: "pill p-green",
  ditolak: "pill p-red",
  kedaluwarsa: "pill p-gray",
  gagal: "pill p-red",
};

const ACTION_LABELS: Record<string, string> = {
  "cv.upload": "unggah CV",
  "client.auto_activated": "klien otomatis aktif",
  "recruitment.offering_sent": "kirim surat penawaran",
  "interview.scheduled": "jadwalkan interview",
  "recruitment.match_executed": "jalankan AI matching",
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/[._]/g, " ");
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "baru saja";
  if (min < 60) return `${min} menit lalu`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} jam lalu`;
  return `${Math.floor(hr / 24)} hari lalu`;
}


export default function TalentCloudOverview() {
  const qc = useQueryClient();
  const [matchJoId, setMatchJoId] = useState<string | null>(null);
  const [matchResults, setMatchResults] = useState<MatchItem[] | null>(null);
  const [matchPage, setMatchPage] = useState(0);
  const [interviewCandidateId, setInterviewCandidateId] = useState("");
  const MATCH_PAGE_SIZE = 6;

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
  });

  const overview = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });
  const leads = useQuery({ queryKey: ["leads"], queryFn: () => api.get<Lead[]>("/leads") });
  const clients = useQuery({ queryKey: ["clients"], queryFn: () => api.get<ClientRow[]>("/clients") });
  const jobOrders = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });
  const candidates = useQuery({
    queryKey: ["candidates-for-match"],
    queryFn: () => api.get<Candidate[]>("/recruitment/candidates"),
  });
  const interviews = useQuery({
    queryKey: ["interviews"],
    queryFn: () => api.get<Interview[]>("/recruitment/interviews"),
  });
  const users = useQuery({
    queryKey: ["users-for-interview"],
    queryFn: () => api.get<UserOption[]>("/auth/users"),
  });
  const offering = useQuery({
    queryKey: ["offering-summary"],
    queryFn: () => api.get<OfferingSummary>("/recruitment/placements/offering-summary"),
  });
  const placements = useQuery({
    queryKey: ["placements"],
    queryFn: () => api.get<Placement[]>("/recruitment/placements"),
  });

  const canSeeActivity = me.data?.role === "admin" || me.data?.role === "management";
  const auditCandidate = useQuery({
    queryKey: ["audit-activity", "candidate"],
    queryFn: () => api.get<{ total: number; items: AuditItem[] }>("/audit/logs?entity_type=candidate&limit=5"),
    enabled: canSeeActivity,
    retry: false,
  });
  const auditPlacement = useQuery({
    queryKey: ["audit-activity", "placement"],
    queryFn: () => api.get<{ total: number; items: AuditItem[] }>("/audit/logs?entity_type=placement&limit=5"),
    enabled: canSeeActivity,
    retry: false,
  });
  const auditJobOrder = useQuery({
    queryKey: ["audit-activity", "job_order"],
    queryFn: () => api.get<{ total: number; items: AuditItem[] }>("/audit/logs?entity_type=job_order&limit=5"),
    enabled: canSeeActivity,
    retry: false,
  });
  const activityFeed = useMemo(() => {
    const merged = [
      ...(auditCandidate.data?.items ?? []),
      ...(auditPlacement.data?.items ?? []),
      ...(auditJobOrder.data?.items ?? []),
    ];
    return merged
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 3);
  }, [auditCandidate.data, auditPlacement.data, auditJobOrder.data]);

  const match = useMutation({
    mutationFn: (id: string) =>
      api.post<MatchItem[]>(`/recruitment/job-orders/${id}/match`, { top_k: 50 }),
    onSuccess: (data) => {
      setMatchResults(data);
      setMatchPage(0);
    },
  });

  const scheduleInterview = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/recruitment/interviews", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["interviews"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const clientsActive = (clients.data ?? []).filter((c) => c.status === "aktif");
  const today = new Date();
  const overdueJO = (jobOrders.data ?? []).filter(
    (j) => j.due_date && new Date(j.due_date) < today && !["filled", "closed"].includes(j.status),
  );
  const activeJO = (jobOrders.data ?? []).filter((j) => !["filled", "closed"].includes(j.status));
  const upcomingInterviews = (interviews.data ?? [])
    .filter((i) => i.status === "terjadwal" && new Date(i.scheduled_at) >= today)
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 3);

  const clientName = (id: string) => clients.data?.find((c) => c.id === id)?.name ?? "-";
  const candidateName = (id: string) => candidates.data?.find((c) => c.id === id)?.full_name ?? "-";
  const joTitle = (id: string) => jobOrders.data?.find((j) => j.id === id)?.title ?? "-";
  const actorName = (userId: string | null) =>
    userId ? (users.data?.find((u) => u.id === userId)?.full_name ?? "Pengguna") : "Sistem";
  const filledCount = (jobOrderId: string) =>
    (placements.data ?? []).filter((p) => p.job_order_id === jobOrderId && p.status !== "dibatalkan").length;
  const activeJoCount = (clientId: string) =>
    activeJO.filter((j) => j.client_id === clientId).length;
  const totalMatchPages = matchResults ? Math.ceil(matchResults.length / MATCH_PAGE_SIZE) : 0;
  const pagedMatchResults = (matchResults ?? []).slice(
    matchPage * MATCH_PAGE_SIZE,
    matchPage * MATCH_PAGE_SIZE + MATCH_PAGE_SIZE,
  );
  const candidateTotal = overview.data?.candidates.total ?? 0;

  function handleScheduleInterview(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const joId = form.get("job_order_id");
    const scheduledAt = form.get("scheduled_at");
    if (!interviewCandidateId || !joId || !scheduledAt) return;
    scheduleInterview.mutate({
      candidate_id: interviewCandidateId,
      job_order_id: joId,
      interviewer_id: form.get("interviewer_id") || null,
      scheduled_at: new Date(String(scheduledAt)).toISOString(),
      location: form.get("location") || null,
      meeting_url: form.get("meeting_url") || null,
    });
    e.currentTarget.reset();
    setInterviewCandidateId("");
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          icon={Sparkles}
          title="Talent Cloud"
          subtitle={`${(candidates.data ?? []).length} talent pool · ${activeJO.length} JO aktif · ${clientsActive.length} klien aktif.`}
        />
        <Link to="/candidates" className="btn shrink-0">
          + Tambah Kandidat
        </Link>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>Klien Aktif</span>
            <IconBadge icon={Building2} tone="green" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {clientsActive.length}
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>Leads</span>
            <IconBadge icon={Filter} tone="violet" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {overview.data?.leads.total ?? "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: "var(--n-text-muted)" }}>
            {overview.data?.leads.won ?? 0} deal
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>Job Order Terbuka</span>
            <IconBadge icon={Briefcase} tone="orange" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {overview.data?.job_orders.open ?? "-"}
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: overdueJO.length ? "#e03e3e" : "var(--n-text-muted)" }}>
            {overdueJO.length} lewat target
          </p>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>Talent Pool</span>
            <IconBadge icon={Database} tone="accent" shape="circle" />
          </div>
          <p className="mt-2 text-2xl font-semibold" style={{ color: "var(--n-text)" }}>
            {overview.data?.candidates.total ?? "-"}
          </p>
        </div>
      </div>

      {/* Recruitment funnel */}
      <div className="card">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={GitBranch} tone="accent" />
            <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Recruitment Funnel</h2>
          </div>
          <span className="pill p-gray">{candidateTotal} total</span>
        </div>
        <div className="flex items-end gap-1">
          {Object.keys(CANDIDATE_STATUS_LABELS).map((s) => {
            const count = overview.data?.candidates.by_status[s] ?? 0;
            const pct = candidateTotal > 0 ? (count / candidateTotal) * 100 : 0;
            if (pct <= 0) return null;
            return (
              <div key={s} className="min-w-0" style={{ width: `${pct}%` }} title={`${CANDIDATE_STATUS_LABELS[s]}: ${count}`}>
                <div className="h-2.5 rounded-full" style={{ backgroundColor: CANDIDATE_STATUS_COLORS[s] }} />
                <p className="mt-1.5 truncate text-center text-xs font-semibold" style={{ color: "var(--n-text)" }}>
                  {count}
                </p>
                <p className="truncate text-center text-[10px]" style={{ color: "var(--n-text-muted)" }}>
                  {CANDIDATE_STATUS_LABELS[s]}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {overview.data?.ai_insight.hint && (
            <CalloutBlock icon={Sparkles} tone="info">
              {overview.data.ai_insight.hint}
            </CalloutBlock>
          )}

          {/* AI Matching */}
          <div className="card space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <IconBadge icon={Sparkles} tone="accent" />
                <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Talent Pool & AI Matching</h2>
              </div>
              <button
                type="button"
                className="btn flex shrink-0 items-center gap-1.5 text-xs"
                disabled={!matchJoId || match.isPending}
                onClick={() => matchJoId && match.mutate(matchJoId)}
              >
                <Zap className="h-3.5 w-3.5" /> {match.isPending ? "AI menilai..." : "Match"}
              </button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <select
                className="input w-auto py-1 text-xs"
                value={matchJoId ?? ""}
                onChange={(e) => setMatchJoId(e.target.value || null)}
              >
                <option value="">-- Pilih Job Order --</option>
                {(jobOrders.data ?? []).map((j) => (
                  <option key={j.id} value={j.id}>{j.title}</option>
                ))}
              </select>
              <div className="flex shrink-0 gap-3 text-xs">
                <Link to="/candidates" className="font-medium hover:underline" style={{ color: "var(--accent)" }}>
                  Database kandidat →
                </Link>
                <Link to="/talent-pool" className="font-medium hover:underline" style={{ color: "var(--accent)" }}>
                  Talent Pool →
                </Link>
              </div>
            </div>
            {match.error && <p className="text-sm text-red-600">{(match.error as Error).message}</p>}
            {matchResults && (
              <ol className="space-y-2">
                {pagedMatchResults.map((item, idx) => (
                  <li key={item.candidate_id} className="flex gap-3">
                    <span className="w-5 pt-2 text-right text-sm font-bold" style={{ color: "var(--n-text-muted)" }}>
                      {matchPage * MATCH_PAGE_SIZE + idx + 1}.
                    </span>
                    <div
                      className="flex min-w-0 flex-1 gap-3 rounded-lg border p-3"
                      style={{ borderColor: "var(--n-border)" }}
                    >
                      <span
                        className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                        style={{ backgroundColor: "var(--accent)" }}
                      >
                        {initials(candidateName(item.candidate_id))}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium" style={{ color: "var(--n-text)" }}>
                            {candidateName(item.candidate_id)}{" "}
                            <span className="ml-1 text-xs">(skor <ScoreBadge score={item.match_score} />/100)</span>
                          </p>
                          <button
                            type="button"
                            className="shrink-0 text-xs font-medium hover:underline"
                            style={{ color: "var(--accent)" }}
                            onClick={() => setInterviewCandidateId(item.candidate_id)}
                          >
                            Jadwalkan →
                          </button>
                        </div>
                        <p className="mt-1 text-sm" style={{ color: "var(--n-text)" }}>{item.explain}</p>
                        {item.missing.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {item.missing.map((m) => (
                              <span key={m} className="pill p-red text-[10px]">{m}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
                {matchResults.length === 0 && (
                  <li className="text-sm" style={{ color: "var(--n-text-muted)" }}>
                    Tidak ada kandidat aktif untuk job order ini.
                  </li>
                )}
              </ol>
            )}
            {matchResults && matchResults.length > MATCH_PAGE_SIZE && (
              <div className="flex items-center justify-between border-t pt-2 text-xs" style={{ borderColor: "var(--n-border)" }}>
                <span style={{ color: "var(--n-text-muted)" }}>
                  Menampilkan {pagedMatchResults.length} dari {matchResults.length}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="grid h-7 w-7 place-items-center rounded-full border disabled:opacity-40"
                    style={{ borderColor: "var(--n-border)" }}
                    disabled={matchPage === 0}
                    onClick={() => setMatchPage((p) => Math.max(0, p - 1))}
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <span className="px-2 font-medium" style={{ color: "var(--n-text)" }}>
                    {matchPage + 1} / {totalMatchPages}
                  </span>
                  <button
                    type="button"
                    className="grid h-7 w-7 place-items-center rounded-full border disabled:opacity-40"
                    style={{ borderColor: "var(--n-border)" }}
                    disabled={matchPage >= totalMatchPages - 1}
                    onClick={() => setMatchPage((p) => Math.min(totalMatchPages - 1, p + 1))}
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Set interview schedule */}
          <div className="card space-y-3">
            <div className="flex items-center gap-2">
              <IconBadge icon={CalendarPlus} tone="accent" />
              <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Jadwalkan Interview</h2>
            </div>
            <form className="grid grid-cols-1 gap-2 sm:grid-cols-6" onSubmit={handleScheduleInterview}>
              <select
                className="input py-1 text-xs sm:col-span-2"
                value={interviewCandidateId}
                onChange={(e) => setInterviewCandidateId(e.target.value)}
                required
              >
                <option value="">-- Kandidat --</option>
                {(candidates.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{c.full_name}</option>
                ))}
              </select>
              <select name="job_order_id" required className="input py-1 text-xs">
                <option value="">-- Job Order --</option>
                {(jobOrders.data ?? []).map((j) => (
                  <option key={j.id} value={j.id}>{j.title}</option>
                ))}
              </select>
              <input name="scheduled_at" type="datetime-local" required className="input py-1 text-xs" />
              <select name="interviewer_id" className="input py-1 text-xs">
                <option value="">-- Interviewer --</option>
                {(users.data ?? []).map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name}</option>
                ))}
              </select>
              <input name="location" placeholder="Lokasi" className="input py-1 text-xs" />
              <button type="submit" disabled={scheduleInterview.isPending} className="btn py-1 text-xs sm:col-span-6">
                Jadwalkan
              </button>
            </form>
            {scheduleInterview.error && (
              <p className="text-sm text-red-600">{(scheduleInterview.error as Error).message}</p>
            )}
            {scheduleInterview.isSuccess && (
              <CalloutBlock tone="success">Interview berhasil dijadwalkan.</CalloutBlock>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {/* Job orders aktif */}
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Briefcase} tone="accent" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Job Orders Aktif</h2>
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                  {activeJO.length} aktif · {overdueJO.length} overdue
                </p>
              </div>
            </div>
            <div className="space-y-1.5">
              {activeJO.slice(0, 2).map((j) => (
                <RowFrame key={j.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>{j.title}</span>
                    <span className="ml-2 shrink-0 text-xs" style={{ color: "var(--n-text-muted)" }}>
                      {filledCount(j.id)}/{j.headcount} terisi
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>{clientName(j.client_id)}</p>
                </RowFrame>
              ))}
              {activeJO.length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada job order aktif.</p>
              )}
            </div>
            <SeeAllLink to="/job-orders">Lihat semua JO →</SeeAllLink>
          </div>

          {/* Klien aktif */}
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Building2} tone="green" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Klien Aktif</h2>
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>{clientsActive.length} aktif</p>
              </div>
            </div>
            <div className="space-y-1.5">
              {clientsActive.slice(0, 2).map((c) => (
                <RowFrame key={c.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>{c.name}</span>
                    <span className="ml-2 shrink-0 text-xs" style={{ color: "var(--n-text-muted)" }}>
                      {activeJoCount(c.id)} JO aktif
                    </span>
                  </div>
                </RowFrame>
              ))}
              {clientsActive.length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada klien aktif.</p>
              )}
            </div>
            <SeeAllLink to="/clients">Lihat semua klien →</SeeAllLink>
          </div>

          {/* List leads */}
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Filter} tone="violet" />
              <div>
                <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Leads</h2>
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                  {leads.data?.length ?? 0} total
                </p>
              </div>
            </div>
            <div className="space-y-1.5">
              {(leads.data ?? []).slice(0, 3).map((l) => (
                <RowFrame key={l.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate font-medium" style={{ color: "var(--n-text)" }}>{l.company_name}</span>
                    <span className="pill p-gray ml-2 shrink-0 text-[10px]">{l.stage}</span>
                  </div>
                </RowFrame>
              ))}
              {(leads.data ?? []).length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada leads.</p>
              )}
            </div>
            <SeeAllLink to="/leads">Lihat semua leads →</SeeAllLink>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Interview schedule */}
        <div className="card space-y-2">
          <div className="flex items-center gap-2">
            <IconBadge icon={Calendar} tone="accent" />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Interview Terjadwal</h2>
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                {overview.data?.recruitment_talent.interviews_this_week ?? 0} minggu ini
              </p>
            </div>
          </div>
          <div className="space-y-1.5">
            {upcomingInterviews.map((i) => (
              <RowFrame key={i.id}>
                <p className="text-sm font-medium" style={{ color: "var(--n-text)" }}>
                  {candidateName(i.candidate_id)} · {joTitle(i.job_order_id)}
                </p>
                <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>
                  {new Date(i.scheduled_at).toLocaleString("id-ID")}
                  {i.location ? ` · ${i.location}` : ""}
                </p>
              </RowFrame>
            ))}
            {upcomingInterviews.length === 0 && (
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Tidak ada interview terjadwal.</p>
            )}
          </div>
          <SeeAllLink to="/candidates">Kelola di Kandidat →</SeeAllLink>
        </div>

        {/* Aktivitas terbaru */}
        {canSeeActivity && (
          <div className="card space-y-2">
            <div className="flex items-center gap-2">
              <IconBadge icon={Activity} tone="green" />
              <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Aktivitas Terbaru</h2>
            </div>
            <div className="space-y-1.5">
              {activityFeed.map((a) => (
                <RowFrame key={a.id}>
                  <p className="text-sm font-medium" style={{ color: "var(--n-text)" }}>{actionLabel(a.action)}</p>
                  <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>
                    oleh {actorName(a.user_id)} · {timeAgo(a.created_at)}
                  </p>
                </RowFrame>
              ))}
              {activityFeed.length === 0 && (
                <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada aktivitas.</p>
              )}
            </div>
          </div>
        )}

        {/* Offering */}
        <div className="card space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <IconBadge icon={Gift} tone="orange" />
              <h2 className="text-sm font-semibold" style={{ color: "var(--n-text)" }}>Offering</h2>
            </div>
            {offering.data && (
              <span className="text-xs" style={{ color: "var(--n-text-muted)" }}>
                {offering.data.total_active} aktif · {offering.data.awaiting_signature} menunggu ttd
              </span>
            )}
          </div>
          <div className="space-y-1.5">
            {(offering.data?.items ?? []).slice(0, 3).map((o) => (
              <RowFrame key={o.placement_id}>
                <div className="flex items-start justify-between gap-2 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium" style={{ color: "var(--n-text)" }}>{o.candidate_name} · {o.job_order_title}</p>
                    <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>
                      {o.client_name}
                      {o.offered_salary ? ` · ${formatRupiah(o.offered_salary)}` : ""}
                    </p>
                  </div>
                  {o.esign_status && (
                    <span className={`shrink-0 text-[10px] ${ESIGN_STATUS_PILL[o.esign_status] ?? "pill p-gray"}`}>
                      {ESIGN_STATUS_LABELS[o.esign_status] ?? o.esign_status}
                    </span>
                  )}
                </div>
              </RowFrame>
            ))}
            {(offering.data?.items ?? []).length === 0 && (
              <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Belum ada offering aktif.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
