import { Fragment, FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile, formatRupiah } from "../api/client";
import { CalloutBlock, PageHeader } from "../components/notion";

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

const GROUP_LABELS: Record<string, string> = {
  identitas: "Identitas",
  pendidikan: "Pendidikan",
  pengalaman: "Pengalaman",
  skill: "Skill & Sertifikasi",
  penempatan: "Data Penempatan",
};

const READINESS_LABELS: Record<string, string> = {
  segera: "Segera",
  n_minggu: "n minggu",
  belum_tentu: "Belum tentu",
};

function IntakeReviewPanel({ intakeId }: { intakeId: string }) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const [reviewed, setReviewed] = useState<string[]>([]);

  const detail = useQuery({
    queryKey: ["talentpool-intake", intakeId],
    queryFn: () => api.get<IntakeDetail>(`/talentpool/intake/${intakeId}`),
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["talentpool-intake", intakeId] });
    void qc.invalidateQueries({ queryKey: ["talentpool"] });
  };

  const review = useMutation({
    mutationFn: () =>
      api.post(`/talentpool/intake/${intakeId}/review`, {
        corrections: edits,
        reviewed,
      }),
    onSuccess: () => {
      setEdits({});
      setReviewed([]);
      invalidate();
    },
  });
  const finalize = useMutation({
    mutationFn: () => api.post(`/talentpool/intake/${intakeId}/finalize`, {}),
    onSuccess: invalidate,
  });
  const reprocess = useMutation({
    mutationFn: () => api.post(`/talentpool/intake/${intakeId}/reprocess`, {}),
    onSuccess: invalidate,
  });

  if (detail.isLoading) return <p className="text-xs">Memuat profil…</p>;
  if (detail.error) return <p className="text-xs text-red-600">{(detail.error as Error).message}</p>;
  const d = detail.data!;
  const p = d.extracted ?? {};

  const field = (key: string, label: string) => (
    <label className="block text-xs">
      <span style={{ color: "var(--n-text-muted)" }}>{label}</span>
      <input
        className="input mt-0.5"
        defaultValue={String(p[key] ?? "")}
        onChange={(e) => setEdits((prev) => ({ ...prev, [key]: e.target.value || null }))}
      />
    </label>
  );

  return (
    <div className="space-y-3 rounded p-3" style={{ backgroundColor: "var(--n-hover)" }}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`${d.status === "gagal" ? "pill p-red" : d.status === "finalisasi" ? "pill p-green" : "pill p-yellow"}`}>
          {d.status.replace("_", " ")}
        </span>
        <span style={{ color: "var(--n-text-muted)" }}>{d.file_name} · skema v{d.schema_version}/prompt v{d.prompt_version}</span>
        {d.status === "gagal" && (
          <button
            onClick={() => reprocess.mutate()}
            disabled={reprocess.isPending}
            className="font-medium text-blue-600 hover:text-blue-800"
          >
            Proses Ulang
          </button>
        )}
      </div>

      {d.status === "gagal" && (
        <CalloutBlock emoji="⚠️" tone="warning">
          Ekstraksi gagal: {d.needs_review.length ? "" : ""}
          {"AI belum dikonfigurasi atau dokumen tidak terbaca. Coba proses ulang."}
        </CalloutBlock>
      )}

      {d.extracted && (
        <>
          {d.needs_review.length > 0 && d.status === "menunggu_review" && (
            <div className="rounded border p-2 text-xs" style={{ borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,.08)" }}>
              <b>Wajib dicek recruiter:</b>{" "}
              {d.needs_review.map((g) => GROUP_LABELS[g] ?? g).join(", ")} — centang setelah verifikasi:
              {d.needs_review.map((g) => (
                <label key={g} className="ml-3 inline-flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={reviewed.includes(g)}
                    onChange={(e) =>
                      setReviewed((prev) =>
                        e.target.checked ? [...prev, g] : prev.filter((x) => x !== g)
                      )
                    }
                  />
                  {GROUP_LABELS[g] ?? g}
                </label>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {field("full_name", "Nama lengkap")}
            {field("phone", "No. HP")}
            {field("email", "Email")}
            {field("domisili", "Domisili")}
            {field("birth_date", "Tanggal lahir (YYYY-MM-DD)")}
            {field("expected_salary", "Ekspektasi gaji")}
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {field("summary", "Ringkasan profil")}
            {field("contract_preference", "Preferensi kontrak")}
          </div>

          <details className="text-xs">
            <summary className="cursor-pointer font-medium">Skema lengkap (JSON)</summary>
            <pre className="mt-1 max-h-56 overflow-auto rounded p-2" style={{ backgroundColor: "var(--n-hover)" }}>
              {JSON.stringify(p, null, 2)}
            </pre>
          </details>

          <div className="flex flex-wrap items-center gap-3 text-xs">
            {d.status === "menunggu_review" && (
              <>
                <button
                  onClick={() => review.mutate()}
                  disabled={review.isPending || Object.keys(edits).length === 0}
                  className="rounded bg-[var(--accent)] px-3 py-1.5 font-medium text-white disabled:opacity-40"
                >
                  Simpan Koreksi
                </button>
                <button
                  onClick={() => finalize.mutate()}
                  disabled={finalize.isPending}
                  className="rounded bg-emerald-600 px-3 py-1.5 font-medium text-white disabled:opacity-40"
                >
                  Finalisasi → CV Standar v{(d.versions[0]?.seq ?? 0) + 1}
                </button>
              </>
            )}
          </div>
        </>
      )}

      {(review.error || finalize.error || reprocess.error) && (
        <p className="text-xs text-red-600">
          {((review.error || finalize.error || reprocess.error) as Error).message}
        </p>
      )}

      {d.versions.length > 0 && (
        <div className="text-xs">
          <b>Versi CV standar:</b>
          <ul className="mt-1 space-y-0.5">
            {d.versions.map((v) => (
              <li key={v.id}>
                v{v.seq}{" "}
                <button
                  onClick={() => void downloadFile(v.download_url)}
                  className="font-medium text-blue-600 hover:text-blue-800"
                >
                  Unduh PDF
                </button>
                {v.is_locked && <span className="pill p-gray ml-1">terkunci submission</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
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
  return (
    <div className="card space-y-2 p-4">
      <h3 className="text-sm font-semibold">🎨 Branding CV Standar</h3>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {b.has_logo && b.logo_url && (
          <img
            src={`/api/v1${b.logo_url}`}
            alt="Logo"
            className="h-10 rounded border"
            style={{ borderColor: "var(--n-border)" }}
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
          <input ref={fileRef} type="file" accept=".png,.jpg,image/png,image/jpeg" className="input w-auto" />
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
              style={{ color: "var(--n-text-muted)" }}
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

export default function TalentPool() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [domisili, setDomisili] = useState("");
  const [skill, setSkill] = useState("");
  const [readiness, setReadiness] = useState("");
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (domisili) params.set("domisili", domisili);
  if (skill) params.set("skill", skill);
  if (readiness) params.set("readiness", readiness);

  const pool = useQuery({
    queryKey: ["talentpool", q, domisili, skill, readiness],
    queryFn: () => api.get<TpRow[]>(`/talentpool?${params.toString()}`),
  });

  const intake = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("consent", String(consent));
      return api.upload<IntakeDetail>("/talentpool/intake", fd);
    },
    onSuccess: (data) => {
      setOpenRow(data.candidate_id);
      void qc.invalidateQueries({ queryKey: ["talentpool"] });
    },
  });

  function handleFilter(e: FormEvent) {
    e.preventDefault();
    void pool.refetch();
  }

  return (
    <div className="space-y-4">
      <PageHeader
        emoji="🧬"
        title="Talent Pool"
        subtitle="CV terstandar otomatis: unggah → ekstraksi AI → review recruiter → CV standar berversi (PRD §10)"
      />

      <BrandingCard />

      <div className="card space-y-2 p-4">
        <h3 className="text-sm font-semibold">Unggah CV Kandidat</h3>
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          PDF (teks atau hasil scan), DOCX, atau foto. File asli tersimpan sebagai bukti sumber.
        </p>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <input ref={fileRef} type="file" accept=".pdf,.docx,image/png,image/jpeg,image/webp" className="input w-auto" />
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
            className="btn-secondary disabled:opacity-40"
          >
            {intake.isPending ? "Memproses…" : "Proses CV"}
          </button>
        </div>
        {!consent && <p className="text-[11px]" style={{ color: "var(--n-text-muted)" }}>Centang persetujuan untuk mengaktifkan tombol.</p>}
        {intake.error && <p className="text-xs text-red-600">{(intake.error as Error).message}</p>}
      </div>

      <form onSubmit={handleFilter} className="card flex flex-wrap items-center gap-2 p-4 text-xs">
        <input placeholder="Cari nama…" value={q} onChange={(e) => setQ(e.target.value)} className="input w-40" />
        <input placeholder="Domisili" value={domisili} onChange={(e) => setDomisili(e.target.value)} className="input w-32" />
        <input placeholder="Skill" value={skill} onChange={(e) => setSkill(e.target.value)} className="input w-32" />
        <select value={readiness} onChange={(e) => setReadiness(e.target.value)} className="input w-auto">
          <option value="">Semua kesiapan</option>
          <option value="segera">Segera</option>
          <option value="n_minggu">n minggu</option>
          <option value="belum_tentu">Belum tentu</option>
        </select>
        <button type="submit" className="btn-secondary">Filter</button>
      </form>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)" }}>
            <tr>
              <th className="th">Kandidat</th>
              <th className="th">Domisili</th>
              <th className="th">Skill</th>
              <th className="th">Kesiapan</th>
              <th className="th">Ekspektasi</th>
              <th className="th">Status TP</th>
              <th className="th">CV Standar</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(pool.data ?? []).map((r) => (
              <Fragment key={r.candidate_id}>
                <tr>
                  <td className="td font-medium">{r.full_name}</td>
                  <td className="td">{r.city ?? "-"}</td>
                  <td className="td max-w-[180px] truncate">{r.skills ?? "-"}</td>
                  <td className="td">{r.readiness ? READINESS_LABELS[r.readiness] ?? r.readiness : "-"}</td>
                  <td className="td">{r.expected_salary ? formatRupiah(r.expected_salary) : "-"}</td>
                  <td className="td">
                    <span className="pill p-gray">{r.tp_status}</span>
                    {r.needs_review_count > 0 && (
                      <span className="pill p-yellow ml-1">{r.needs_review_count} perlu cek</span>
                    )}
                  </td>
                  <td className="td">{r.latest_cv_version ? `v${r.latest_cv_version}` : "—"}</td>
                  <td className="td">
                    {r.latest_intake_id && (
                      <button
                        onClick={() => setOpenRow(openRow === r.candidate_id ? null : r.candidate_id)}
                        className="font-medium text-blue-600 hover:text-blue-800"
                      >
                        {openRow === r.candidate_id ? "Tutup" : "Review"}
                      </button>
                    )}
                  </td>
                </tr>
                {openRow === r.candidate_id && r.latest_intake_id && (
                  <tr>
                    <td colSpan={8} className="td">
                      <IntakeReviewPanel intakeId={r.latest_intake_id} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {pool.data?.length === 0 && (
              <tr>
                <td colSpan={8} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Talent pool kosong pada filter ini. Unggah CV untuk memulai.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
