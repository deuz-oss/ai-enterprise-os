import { FormEvent, useState } from "react";
import { Ban, CheckCircle2, Clock, XCircle } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { KpiCard, PillTabs, type PillTab } from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";

interface Candidate {
  id: string;
  full_name: string;
  email: string | null;
}

interface BlacklistEntry {
  id: string;
  candidate_id: string;
  candidate_name: string;
  reason: string;
  status: "menunggu_review" | "disetujui" | "ditolak";
  requested_by: string | null;
  requested_by_name: string | null;
  requested_at: string;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
}

const STATUS_PILL: Record<string, string> = {
  menunggu_review: "p-yellow",
  disetujui: "p-red",
  ditolak: "p-gray",
};

const STATUS_LABEL: Record<string, string> = {
  menunggu_review: "Menunggu Review",
  disetujui: "Blacklist Aktif",
  ditolak: "Ditolak",
};

const TABS: { key: string; label: string }[] = [
  { key: "menunggu_review", label: "Permintaan" },
  { key: "disetujui", label: "Daftar Hitam" },
  { key: "ditolak", label: "Ditolak" },
];

export default function Blacklist() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<string>("menunggu_review");
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tab/Pill filter (§1.5) butuh count tiap status sekaligus -- endpoint
  // yang sama (`/blacklist/entries?status=`) sudah dipakai, cuma sekarang
  // di-fetch untuk ketiga status secara paralel (bukan cuma tab aktif)
  // supaya count-nya selalu akurat.
  const pending = useQuery({
    queryKey: ["blacklist-entries", "menunggu_review"],
    queryFn: () => api.get<BlacklistEntry[]>("/blacklist/entries?status=menunggu_review"),
  });
  const approved = useQuery({
    queryKey: ["blacklist-entries", "disetujui"],
    queryFn: () => api.get<BlacklistEntry[]>("/blacklist/entries?status=disetujui"),
  });
  const rejected = useQuery({
    queryKey: ["blacklist-entries", "ditolak"],
    queryFn: () => api.get<BlacklistEntry[]>("/blacklist/entries?status=ditolak"),
  });
  const byTab: Record<string, BlacklistEntry[] | undefined> = {
    menunggu_review: pending.data,
    disetujui: approved.data,
    ditolak: rejected.data,
  };
  const entries = byTab[tab];
  const statusTabs: PillTab[] = TABS.map((t) => ({
    key: t.key,
    label: t.label,
    count: (byTab[t.key] ?? []).length,
  }));
  const { data: candidates } = useQuery({
    queryKey: ["candidates-lite"],
    queryFn: () => api.get<Candidate[]>("/recruitment/candidates"),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["blacklist-entries"] });

  const requestBlacklist = useMutation({
    mutationFn: (body: { candidate_id: string; reason: string }) =>
      api.post("/blacklist/entries", body),
    onSuccess: () => {
      setShowForm(false);
      setError(null);
      invalidate();
    },
    onError: (e: unknown) => setError(e instanceof ApiError ? e.message : "Gagal mengajukan"),
  });

  const review = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "disetujui" | "ditolak" }) =>
      api.post(`/blacklist/entries/${id}/review`, { decision }),
    onSuccess: invalidate,
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const candidateId = String(form.get("candidate_id") || "");
    const reason = String(form.get("reason") || "").trim();
    if (!candidateId || !reason) return;
    requestBlacklist.mutate({ candidate_id: candidateId, reason });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader
          icon={Ban}
          title="Black Lists"
          subtitle="Tandai kandidat bermasalah — wajib disetujui sebelum aktif"
        />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Ajukan Blacklist"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card space-y-3">
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div>
            <label className="text-xs font-medium text-[var(--text-muted)]">Kandidat *</label>
            <select name="candidate_id" required className="input mt-1 w-full" defaultValue="">
              <option value="" disabled>
                Pilih kandidat
              </option>
              {(candidates ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} {c.email ? `(${c.email})` : ""}
                </option>
              ))}
            </select>
          </div>
          <textarea
            name="reason"
            required
            placeholder="Alasan pengajuan blacklist *"
            className="input w-full"
            rows={3}
          />
          <button className="btn" type="submit" disabled={requestBlacklist.isPending}>
            Ajukan
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          label="Menunggu Review"
          value={(pending.data ?? []).length}
          icon={Clock}
          iconTone="warning"
          badge={(pending.data ?? []).length > 0 ? { label: "Perlu Tindakan", tone: "warning" } : undefined}
        />
        <KpiCard label="Blacklist Aktif" value={(approved.data ?? []).length} icon={CheckCircle2} iconTone="danger" />
        <KpiCard label="Ditolak" value={(rejected.data ?? []).length} icon={XCircle} iconTone="neutral" />
      </div>

      <PillTabs tabs={statusTabs} value={tab} onChange={setTab} />

      <div className="card space-y-0 p-0">
        {(entries ?? []).length === 0 && (
          <p className="p-3 text-sm text-[var(--text-muted)]">Tidak ada data.</p>
        )}
        {(entries ?? []).map((entry) => (
          <div key={entry.id} className="border-t p-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-[var(--text)]">{entry.candidate_name}</p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">{entry.reason}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className={`pill ${STATUS_PILL[entry.status]}`}>
                    {STATUS_LABEL[entry.status]}
                  </span>
                  <span className="text-xs text-[var(--text-muted)]">
                    Diajukan {entry.requested_by_name ?? "?"} ·{" "}
                    {new Date(entry.requested_at).toLocaleDateString("id-ID")}
                  </span>
                  {entry.reviewed_by_name && (
                    <span className="text-xs text-[var(--text-muted)]">
                      Direview {entry.reviewed_by_name}
                    </span>
                  )}
                </div>
                {entry.review_notes && (
                  <p className="mt-1 text-xs italic text-[var(--text-muted)]">
                    Catatan: {entry.review_notes}
                  </p>
                )}
              </div>
              {entry.status === "menunggu_review" && (
                <div className="flex shrink-0 gap-2">
                  <button
                    className="btn-secondary py-1 text-xs"
                    disabled={review.isPending}
                    onClick={() => review.mutate({ id: entry.id, decision: "disetujui" })}
                  >
                    Setujui
                  </button>
                  <button
                    className="btn-secondary py-1 text-xs text-red-600"
                    disabled={review.isPending}
                    onClick={() => review.mutate({ id: entry.id, decision: "ditolak" })}
                  >
                    Tolak
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
