import { Fragment, FormEvent, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile, formatRupiah } from "../api/client";
import { ScoreBadge } from "../components/Ai";
import { CheckCircle2, Clock, Dna, FileCheck2, Palette, Sparkles } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { KpiCard, PillTabs, type PillTab } from "../components/ui";
import { PLACEMENT_STAGE_META as PLACEMENT_STAGE_LABEL } from "../lib/pipelineStages";
import type { JobOrder } from "./JobOrders";

interface TpRow {
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
  // Status funnel rekrutmen keseluruhan (turunan otomatis dari Placement,
  // lihat update_placement_status di backend) -- tidak lagi ditampilkan/
  // diedit manual di sini sejak 2026-09-06; representasi akurat & bisa-aksi
  // ada di kolom "Proses" (job order + status Placement) di bawah.
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
}

interface CandidateFieldConfig {
  key: string;
  label: string;
  group: string;
  visible: boolean;
}

function formatFieldValue(key: string, row: TpRow): string {
  const value = row[key as keyof TpRow];
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

interface PlacementRow {
  id: string;
  candidate_id: string;
  job_order_id: string;
  status: string;
}

interface IntakeDetail {
  id: string;
  candidate_id: string;
  status: string;
  doc_kind: string | null;
  file_name: string;
  schema_version: number;
  prompt_version: number;
  extracted: Record<string, unknown> | null;
  confidences: Record<string, number>;
  needs_review: string[];
  reviewed_fields: string[];
  versions: { id: string; seq: number; is_locked: boolean; created_at: string; download_url: string }[];
}

const READINESS_LABELS: Record<string, string> = {
  segera: "Segera",
  n_minggu: "n minggu",
  belum_tentu: "Belum tentu",
};

interface MatchItem {
  candidate_id: string;
  match_score: number;
  explain: string;
  missing: string[];
}

function BrandingCard() {
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
  });
  const canEdit = me.data?.role === "admin" || me.data?.role === "management";
  const branding = useQuery({
    queryKey: ["cv-branding"],
    queryFn: () =>
      api.get<{
        accent_color: string;
        footer_text: string;
        show_photo: boolean;
        has_logo: boolean;
        logo_url: string | null;
      }>("/talentpool/branding"),
  });
  const [footer, setFooter] = useState<string | null>(null);
  const [accent, setAccent] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  // Pengaturan tenant (logo/warna/footer template PDF), bukan aksi per-kandidat
  // -- disembunyikan default supaya tidak terlihat seperti "kartu upload
  // ketiga" di samping Tambah Kandidat / Unggah CV (feedback 2026-09-06).
  const [open, setOpen] = useState(false);

  const invalidate = () => void qc.invalidateQueries({ queryKey: ["cv-branding"] });

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      if (footer !== null) body.footer_text = footer;
      if (accent !== null) body.accent_color = accent;
      return api.put("/talentpool/branding", body);
    },
    onSuccess: () => {
      setFooter(null);
      setAccent(null);
      invalidate();
    },
  });
  const uploadLogo = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.upload("/talentpool/branding/logo", fd);
    },
    onSuccess: invalidate,
  });
  const removeLogo = useMutation({
    mutationFn: () => api.delete("/talentpool/branding/logo"),
    onSuccess: invalidate,
  });

  const b = branding.data;
  if (!b) return null;
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-xs font-medium hover:underline"
        style={{ color: "var(--text-muted)" }}
      >
        <Palette className="h-3.5 w-3.5" /> Pengaturan CV Standar
      </button>
    );
  }
  return (
    <div className="card space-y-2 p-4">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          <Palette className="h-4 w-4" /> Branding CV Standar
        </h3>
        <button
          onClick={() => setOpen(false)}
          className="text-xs font-medium hover:underline"
          style={{ color: "var(--text-muted)" }}
        >
          Tutup
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {b.has_logo && b.logo_url && (
          <img
            src={`/api/v1${b.logo_url}`}
            alt="Logo"
            className="h-10 rounded border"
            style={{ borderColor: "var(--border)" }}
          />
        )}
        <label className="inline-flex items-center gap-1">
          Warna aksen
          <input
            type="color"
            defaultValue={b.accent_color}
            onChange={(e) => setAccent(e.target.value)}
            disabled={!canEdit}
            className="h-7 w-12 cursor-pointer"
          />
        </label>
        <input
          placeholder="Footer CV (mis. kontak HR)"
          value={footer ?? b.footer_text}
          onChange={(e) => setFooter(e.target.value)}
          disabled={!canEdit}
          className="input w-64"
        />
        {canEdit && (
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending || (footer === null && accent === null)}
            className="btn-secondary disabled:opacity-40"
          >
            Simpan
          </button>
        )}
      </div>
      {canEdit && (
        <div className="flex items-center gap-2 text-xs">
          <input ref={fileRef} type="file" accept=".png,.jpg,image/png,image/jpeg" className="input w-auto" aria-label="Unggah logo" />
          <button
            onClick={() => {
              const f = fileRef.current?.files?.[0];
              if (f) uploadLogo.mutate(f);
            }}
            disabled={uploadLogo.isPending}
            className="btn-secondary"
          >
            Unggah Logo
          </button>
          {b.has_logo && (
            <button
              onClick={() => removeLogo.mutate()}
              disabled={removeLogo.isPending}
              className="hover:text-rose-600"
              style={{ color: "var(--text-muted)" }}
            >
              Hapus Logo
            </button>
          )}
        </div>
      )}
      {(save.error || uploadLogo.error) && (
        <p className="text-xs text-red-600">
          {((save.error || uploadLogo.error) as Error).message}
        </p>
      )}
    </div>
  );
}

function FieldSettingsCard() {
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ email: string; full_name: string; role: string }>("/auth/me"),
  });
  const canEdit = me.data?.role === "admin" || me.data?.role === "management";
  const settings = useQuery({
    queryKey: ["talentpool-field-settings"],
    queryFn: () => api.get<{ fields: CandidateFieldConfig[] }>("/talentpool/field-settings"),
  });
  const [checked, setChecked] = useState<Set<string> | null>(null);
  const [open, setOpen] = useState(false);

  const save = useMutation({
    mutationFn: (visible_fields: string[]) =>
      api.put("/talentpool/field-settings", { visible_fields }),
    onSuccess: () => {
      setChecked(null);
      void qc.invalidateQueries({ queryKey: ["talentpool-field-settings"] });
    },
  });

  const fields = settings.data?.fields ?? [];
  if (!settings.data) return null;
  const active = checked ?? new Set(fields.filter((f) => f.visible).map((f) => f.key));
  const groups = Array.from(new Set(fields.map((f) => f.group)));

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-xs font-medium hover:underline"
        style={{ color: "var(--text-muted)" }}
      >
        <Palette className="h-3.5 w-3.5" /> Pengaturan Field Kandidat
      </button>
    );
  }
  return (
    <div className="card space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          <Palette className="h-4 w-4" /> Field Kandidat di Tabel
        </h3>
        <button
          onClick={() => setOpen(false)}
          className="text-xs font-medium hover:underline"
          style={{ color: "var(--text-muted)" }}
        >
          Tutup
        </button>
      </div>
      {groups.map((group) => (
        <div key={group}>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            {group}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {fields
              .filter((f) => f.group === group)
              .map((f) => (
                <label key={f.key} className="inline-flex items-center gap-1.5 text-xs">
                  <input
                    type="checkbox"
                    checked={active.has(f.key)}
                    disabled={!canEdit}
                    onChange={(e) => {
                      const next = new Set(active);
                      if (e.target.checked) next.add(f.key);
                      else next.delete(f.key);
                      setChecked(next);
                    }}
                  />
                  {f.label}
                </label>
              ))}
          </div>
        </div>
      ))}
      {canEdit && (
        <button
          onClick={() => save.mutate(Array.from(active))}
          disabled={save.isPending || checked === null}
          className="btn-secondary disabled:opacity-40"
        >
          Simpan
        </button>
      )}
      {save.error && <p className="text-xs text-red-600">{(save.error as Error).message}</p>}
    </div>
  );
}

export default function TalentPool() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [domisili, setDomisili] = useState("");
  const [skill, setSkill] = useState("");
  const [readiness, setReadiness] = useState("");
  const [matchJobOrderId, setMatchJobOrderId] = useState("");
  const [minMatchScore, setMinMatchScore] = useState("");
  const [consent, setConsent] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  // Pindahan dari Candidates.tsx (dihapus 2026-09-06) -- create manual tanpa
  // CV, AI screening per-kandidat, dan riwayat pengalaman/aktivitas.
  const [showCreateForm, setShowCreateForm] = useState(false);
  const cvRef = useRef<HTMLInputElement>(null);

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (domisili) params.set("domisili", domisili);
  if (skill) params.set("skill", skill);
  if (readiness) params.set("readiness", readiness);

  const pool = useQuery({
    queryKey: ["talentpool", q, domisili, skill, readiness],
    queryFn: () => api.get<TpRow[]>(`/talentpool?${params.toString()}`),
  });

  const { data: jobOrders } = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });

  const { data: fieldSettings } = useQuery({
    queryKey: ["talentpool-field-settings"],
    queryFn: () => api.get<{ fields: CandidateFieldConfig[] }>("/talentpool/field-settings"),
  });
  const visibleFields = (fieldSettings?.fields ?? []).filter((f) => f.visible);

  // Skor matching native (PRD v3.0 §4) — hanya diambil saat JO dipilih.
  const { data: matchScores } = useQuery({
    queryKey: ["talentpool-match-scores", matchJobOrderId, minMatchScore],
    queryFn: () =>
      api.get<MatchItem[]>(
        `/recruitment/job-orders/${matchJobOrderId}/matches?top_k=500&min_score=${minMatchScore || 0}`
      ),
    enabled: Boolean(matchJobOrderId),
  });
  const scoreByCandidate = new Map((matchScores ?? []).map((m) => [m.candidate_id, m]));
  const matchedIds = matchJobOrderId ? new Set((matchScores ?? []).map((m) => m.candidate_id)) : null;
  const matchFilteredRows = (pool.data ?? []).filter((r) => !matchedIds || matchedIds.has(r.candidate_id));

  // Tab/Pill filter (§1.5) atas tp_status -- difilter di klien atas hasil
  // fetch yang sama (endpoint `/talentpool` sudah mendukung param `tp_status`
  // tapi sengaja tidak dipakai di sini, supaya count tiap pill tetap
  // mencerminkan seluruh hasil pencarian/filter lain yang sedang aktif).
  const [tpStatusTab, setTpStatusTab] = useState("");
  const tpFilteredRows = matchFilteredRows.filter((r) => !tpStatusTab || r.tp_status === tpStatusTab);
  const tpStatusTabs: PillTab[] = [
    { key: "", label: "Semua", count: matchFilteredRows.length },
    ...["baru", "diproses", "placed", "non_aktif"].map((s) => ({
      key: s,
      label: s === "non_aktif" ? "Non-aktif" : s[0].toUpperCase() + s.slice(1),
      count: matchFilteredRows.filter((r) => r.tp_status === s).length,
    })),
  ];

  const visibleRows = tpFilteredRows;

  // Talent Pool cuma database kandidat -- "sedang diproses di Job Order mana"
  // ditunjukkan dari Placement langsung (bukan Candidate.status yang cuma
  // funnel turunan), feedback 2026-09-06. Fetch tanpa filter (pola sama
  // seperti dulu di Candidates.tsx yang sudah dihapus) lalu dikelompokkan
  // per kandidat di klien.
  const { data: placements } = useQuery({
    queryKey: ["placements-all"],
    queryFn: () => api.get<PlacementRow[]>("/recruitment/placements"),
  });
  const placementsByCandidate = new Map<string, PlacementRow[]>();
  for (const p of placements ?? []) {
    const list = placementsByCandidate.get(p.candidate_id) ?? [];
    list.push(p);
    placementsByCandidate.set(p.candidate_id, list);
  }
  const jobOrderTitle = (id: string) => (jobOrders ?? []).find((j) => j.id === id)?.title ?? id;

  // KPI row (§1.3) -- dari data talent pool yang sudah di-fetch (`pool.data`).
  const needsReviewCount = matchFilteredRows.filter((r) => r.needs_review_count > 0).length;
  const cvStandarReadyCount = matchFilteredRows.filter((r) => r.latest_cv_version > 0).length;
  const readySoonCount = matchFilteredRows.filter((r) => r.readiness === "segera").length;

  const intake = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("consent", String(consent));
      return api.upload<IntakeDetail>("/talentpool/intake", fd);
    },
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["talentpool"] });
      navigate(`/talent-pool/${data.candidate_id}`);
    },
  });

  function handleFilter(e: FormEvent) {
    e.preventDefault();
    void pool.refetch();
  }

  const createCandidate = useMutation({
    mutationFn: async ({ body, cv }: { body: Record<string, unknown>; cv: File | null }) => {
      const created = await api.post<{ id: string }>("/recruitment/candidates", body);
      if (cv) {
        const fd = new FormData();
        fd.append("file", cv);
        await api.upload(`/recruitment/candidates/${created.id}/cv`, fd);
      }
      return created;
    },
    onSuccess: () => {
      setShowCreateForm(false);
      void qc.invalidateQueries({ queryKey: ["talentpool"] });
    },
  });

  const generateStandardCv = useMutation({
    mutationFn: (candidateId: string) =>
      api.post(`/talentpool/candidates/${candidateId}/standard-cv`, {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["talentpool"] }),
  });

  function handleCreateCandidate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createCandidate.mutate({
      body: {
        full_name: form.get("full_name"),
        phone: form.get("phone") || null,
        city: form.get("city") || null,
        education: form.get("education") || null,
        expected_salary: Number(form.get("expected_salary")) || null,
        source: form.get("source") || null,
        referral_code: form.get("referral_code") || null,
        skills: form.get("skills") || null,
        skills_list: String(form.get("skills_list") || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        gender: form.get("gender") || null,
        current_position: form.get("current_position") || null,
        birthdate: form.get("birthdate") || null,
        birthplace: form.get("birthplace") || null,
        address: form.get("address") || null,
        ktp_no: form.get("ktp_no") || null,
        marital_status: form.get("marital_status") || null,
        blood_type: form.get("blood_type") || null,
        religion: form.get("religion") || null,
        languages: String(form.get("languages") || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        description: form.get("description") || null,
        position_pool: form.get("position_pool") || null,
        job_level: form.get("job_level") || null,
        school: form.get("school") || null,
        education_level: form.get("education_level") || null,
      },
      cv: cvRef.current?.files?.[0] ?? null,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <PageHeader
          icon={Dna}
          title="Talent Pool"
          subtitle="Database kandidat terpusat: input manual atau unggah CV → data terstandar → CV Standar siap diekspor"
        />
        <div className="flex flex-col items-end gap-1.5">
          <BrandingCard />
          <FieldSettingsCard />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Talent" value={matchFilteredRows.length} icon={Dna} iconTone="info" />
        <KpiCard
          label="Perlu Review"
          value={needsReviewCount}
          icon={Clock}
          iconTone="warning"
          badge={needsReviewCount > 0 ? { label: "Perlu Tindakan", tone: "warning" } : undefined}
        />
        <KpiCard label="CV Standar Siap" value={cvStandarReadyCount} icon={FileCheck2} iconTone="success" />
        <KpiCard label="Siap Ditempatkan Segera" value={readySoonCount} icon={CheckCircle2} iconTone="accent" />
      </div>

      <PillTabs tabs={tpStatusTabs} value={tpStatusTab} onChange={setTpStatusTab} />

      <div className="card space-y-3 p-4">
        <h3 className="text-sm font-semibold">Tambah Kandidat</h3>

        <div className="space-y-2">
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Punya CV? Unggah di sini — sistem membaca datanya otomatis (PDF, hasil scan, DOCX,
            atau foto). File asli tersimpan sebagai bukti sumber.
          </p>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,image/png,image/jpeg,image/webp"
              className="input w-auto"
              aria-label="Unggah CV kandidat"
            />
            <label className="inline-flex items-center gap-1">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              Persetujuan pemrosesan data pribadi (UU PDP)
            </label>
            <button
              onClick={() => {
                const f = fileRef.current?.files?.[0];
                if (f) intake.mutate(f);
              }}
              disabled={!consent || intake.isPending}
              className="btn disabled:opacity-40"
            >
              {intake.isPending ? "Memproses…" : "Proses dengan AI"}
            </button>
          </div>
          {!consent && (
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
              Centang persetujuan untuk mengaktifkan tombol.
            </p>
          )}
          {intake.error && <p className="text-xs text-red-600">{(intake.error as Error).message}</p>}
        </div>

        <div className="flex items-center gap-2" style={{ color: "var(--text-muted)" }}>
          <div className="h-px flex-1" style={{ backgroundColor: "var(--border)" }} />
          <span className="text-[11px]">atau isi manual kalau belum ada CV</span>
          <div className="h-px flex-1" style={{ backgroundColor: "var(--border)" }} />
        </div>

        <button className="btn-secondary text-xs" onClick={() => setShowCreateForm((v) => !v)}>
          {showCreateForm ? "Tutup form manual" : "+ Kandidat Manual"}
        </button>
        {showCreateForm && (
          <form onSubmit={handleCreateCandidate} className="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-3">
            <input name="full_name" required placeholder="Nama lengkap *" className="input" />
            <input name="phone" placeholder="Telepon" className="input" />
            <input name="city" placeholder="Kota" className="input" />
            <input name="education" placeholder="Pendidikan terakhir" className="input" />
            <input name="expected_salary" type="number" placeholder="Ekspektasi gaji (Rp)" className="input" />
            <input name="source" placeholder="Sumber (referral/loker/dll)" className="input" />
            <input name="referral_code" placeholder="Kode referral (jika ada)" className="input" />
            <input name="skills" placeholder="Skill (teks bebas)" className="input" />
            <input
              name="skills_list"
              placeholder="Skill terstruktur (pisah koma, mis. excel, forklift)"
              className="input sm:col-span-2"
            />
            <input ref={cvRef} type="file" accept=".pdf,.doc,.docx" className="input" title="CV (opsional)" aria-label="CV (opsional)" />

            <details className="rounded-lg border p-3 sm:col-span-3" style={{ borderColor: "var(--border)" }}>
              <summary className="cursor-pointer text-sm font-medium" style={{ color: "var(--text)" }}>
                Detail Tambahan (opsional)
              </summary>
              <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                <select name="gender" defaultValue="" className="input">
                  <option value="">Jenis kelamin</option>
                  <option value="L">Laki-laki</option>
                  <option value="P">Perempuan</option>
                </select>
                <input name="current_position" placeholder="Posisi saat ini" className="input" />
                <input name="birthdate" type="date" placeholder="Tanggal lahir" className="input" />
                <input name="birthplace" placeholder="Tempat lahir" className="input" />
                <input name="ktp_no" placeholder="No. KTP" className="input" />
                <select name="marital_status" defaultValue="" className="input">
                  <option value="">Status pernikahan</option>
                  <option value="tk">Belum menikah</option>
                  <option value="k">Menikah</option>
                </select>
                <select name="blood_type" defaultValue="" className="input">
                  <option value="">Golongan darah</option>
                  {["A", "B", "AB", "O"].map((b) => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
                <input name="religion" placeholder="Agama" className="input" />
                <input name="school" placeholder="Sekolah/kampus" className="input" />
                <input name="education_level" placeholder="Jenjang pendidikan" className="input" />
                <input name="job_level" placeholder="Level posisi" className="input" />
                <input name="position_pool" placeholder="Kategori posisi diminati" className="input" />
                <input name="languages" placeholder="Bahasa (pisah koma, mis. Indonesia, Inggris)" className="input" />
                <input name="address" placeholder="Alamat" className="input sm:col-span-3" />
                <textarea name="description" placeholder="Bio singkat" className="input sm:col-span-3" rows={2} />
              </div>
            </details>

            <button type="submit" disabled={createCandidate.isPending} className="btn sm:col-span-3">
              Simpan Kandidat
            </button>
            {createCandidate.error && (
              <p className="text-xs text-red-600 sm:col-span-3">{(createCandidate.error as Error).message}</p>
            )}
          </form>
        )}
      </div>

      <form onSubmit={handleFilter} className="card flex flex-wrap items-center gap-2 p-4 text-xs">
        <input placeholder="Cari nama…" value={q} onChange={(e) => setQ(e.target.value)} className="input w-40" />
        <input placeholder="Domisili" value={domisili} onChange={(e) => setDomisili(e.target.value)} className="input w-32" />
        <input placeholder="Skill" value={skill} onChange={(e) => setSkill(e.target.value)} className="input w-32" />
        <select value={readiness} onChange={(e) => setReadiness(e.target.value)} className="input w-auto" aria-label="Filter kesiapan">
          <option value="">Semua kesiapan</option>
          <option value="segera">Segera</option>
          <option value="n_minggu">n minggu</option>
          <option value="belum_tentu">Belum tentu</option>
        </select>
        <button type="submit" className="btn-secondary">Filter</button>
        <span className="mx-1" style={{ color: "var(--border)" }}>|</span>
        <select
          value={matchJobOrderId}
          onChange={(e) => {
            setMatchJobOrderId(e.target.value);
            if (!e.target.value) setMinMatchScore("");
          }}
          className="input w-auto"
          title="Nilai kecocokan terhadap job order (AI matching native)"
          aria-label="Filter skor kecocokan job order"
        >
          <option value="">Skor match: semua talent</option>
          {(jobOrders ?? []).map((jo) => (
            <option key={jo.id} value={jo.id}>
              Skor match vs {jo.title}
            </option>
          ))}
        </select>
        {matchJobOrderId && (
          <input
            type="number"
            min={0}
            max={100}
            placeholder="Skor min."
            value={minMatchScore}
            onChange={(e) => setMinMatchScore(e.target.value)}
            className="input w-24"
          />
        )}
      </form>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--hover)" }}>
            <tr>
              <th className="th">Kandidat</th>
              {visibleFields.map((f) => (
                <th key={f.key} className="th">
                  {f.label}
                </th>
              ))}
              <th className="th">Kesiapan</th>
              <th className="th">Status TP</th>
              <th className="th">Proses</th>
              <th className="th">CV Standar</th>
              {matchJobOrderId && <th className="th">Skor Match</th>}
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {visibleRows.map((r) => {
              const match = scoreByCandidate.get(r.candidate_id);
              return (
                <tr key={r.candidate_id}>
                  <td className="td font-medium">
                    <Link to={`/talent-pool/${r.candidate_id}`} className="hover:underline">
                      {r.full_name}
                    </Link>
                  </td>
                  {visibleFields.map((f) => (
                    <td key={f.key} className="td max-w-[180px] truncate">
                      {formatFieldValue(f.key, r)}
                    </td>
                  ))}
                  <td className="td">{r.readiness ? READINESS_LABELS[r.readiness] ?? r.readiness : "-"}</td>
                  <td className="td">
                    <span className="pill p-gray">{r.tp_status}</span>
                    {r.needs_review_count > 0 && (
                      <span className="pill p-yellow ml-1">{r.needs_review_count} perlu cek</span>
                    )}
                  </td>
                  <td className="td">
                    <div className="flex flex-wrap gap-1">
                      {(placementsByCandidate.get(r.candidate_id) ?? []).map((p) => {
                        const stage = PLACEMENT_STAGE_LABEL[p.status];
                        return (
                          <Link
                            key={p.id}
                            to={`/job-orders/${p.job_order_id}`}
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium hover:underline"
                            style={{ backgroundColor: "var(--hover)", color: "var(--text)" }}
                            title={`${jobOrderTitle(p.job_order_id)} · ${stage?.label ?? p.status}`}
                          >
                            <span
                              className="inline-block h-1.5 w-1.5 rounded-full"
                              style={{ backgroundColor: stage?.dot ?? "#9f9f9f" }}
                            />
                            <span className="max-w-[90px] truncate">{jobOrderTitle(p.job_order_id)}</span>
                            <span style={{ color: "var(--th-color)" }}>{stage?.label ?? p.status}</span>
                          </Link>
                        );
                      })}
                      {(placementsByCandidate.get(r.candidate_id) ?? []).length === 0 && (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </div>
                  </td>
                  <td className="td">
                    <div className="flex items-center gap-1.5 text-xs">
                      {r.latest_cv_version_id ? (
                        <button
                          onClick={() => void downloadFile(`/talentpool/cv-versions/${r.latest_cv_version_id}/download`)}
                          className="font-medium text-blue-600 hover:text-blue-800"
                        >
                          Unduh v{r.latest_cv_version}
                        </button>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                      <button
                        onClick={() => generateStandardCv.mutate(r.candidate_id)}
                        disabled={generateStandardCv.isPending}
                        className="inline-flex items-center gap-1 btn-secondary py-0.5 text-[11px] disabled:opacity-40"
                        title="Generate CV Standar dari data kandidat saat ini"
                      >
                        <Sparkles className="h-3 w-3" />
                        {r.latest_cv_version_id ? "Perbarui" : "Generate"}
                      </button>
                    </div>
                  </td>
                  {matchJobOrderId && (
                    <td className="td" title={match?.explain}>
                      {match ? <ScoreBadge score={match.match_score} /> : "-"}
                    </td>
                  )}
                </tr>
              );
            })}
            {visibleRows.length === 0 && (
              <tr>
                <td
                  colSpan={(matchJobOrderId ? 6 : 5) + visibleFields.length}
                  className="td py-8 text-center"
                  style={{ color: "var(--text-muted)" }}
                >
                  {matchJobOrderId
                    ? "Tidak ada talent yang memenuhi skor minimum untuk job order ini."
                    : tpStatusTab
                      ? "Tidak ada talent dengan status ini."
                      : "Talent pool kosong pada filter ini. Unggah CV untuk memulai."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
