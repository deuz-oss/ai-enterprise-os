import { FormEvent, useState } from "react";
import { Ban } from "lucide-react";
import { PageHeader } from "../components/notion";
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

  const { data: entries } = useQuery({
    queryKey: ["blacklist-entries", tab],
    queryFn: () => api.get<BlacklistEntry[]>(`/blacklist/entries?status=${tab}`),
  });
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
            <label className="text-xs font-medium text-[var(--n-text-muted)]">Kandidat *</label>
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

      <div className="flex gap-2 border-b" style={{ borderColor: "var(--n-border)" }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`px-3 py-2 text-sm ${
              tab === t.key
                ? "border-b-2 font-medium text-[var(--n-text)]"
                : "text-[var(--n-text-muted)]"
            }`}
            style={tab === t.key ? { borderColor: "var(--n-accent)" } : undefined}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="card space-y-0 p-0">
        {(entries ?? []).length === 0 && (
          <p className="p-3 text-sm text-[var(--n-text-muted)]">Tidak ada data.</p>
        )}
        {(entries ?? []).map((entry) => (
          <div key={entry.id} className="border-t p-3" style={{ borderColor: "var(--n-border)" }}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-[var(--n-text)]">{entry.candidate_name}</p>
                <p className="mt-1 text-xs text-[var(--n-text-muted)]">{entry.reason}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className={`pill ${STATUS_PILL[entry.status]}`}>
                    {STATUS_LABEL[entry.status]}
                  </span>
                  <span className="text-xs text-[var(--n-text-muted)]">
                    Diajukan {entry.requested_by_name ?? "?"} ·{" "}
                    {new Date(entry.requested_at).toLocaleDateString("id-ID")}
                  </span>
                  {entry.reviewed_by_name && (
                    <span className="text-xs text-[var(--n-text-muted)]">
                      Direview {entry.reviewed_by_name}
                    </span>
                  )}
                </div>
                {entry.review_notes && (
                  <p className="mt-1 text-xs italic text-[var(--n-text-muted)]">
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
