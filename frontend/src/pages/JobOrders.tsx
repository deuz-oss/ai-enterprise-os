import { FormEvent, useState } from "react";
import { Magnet } from "lucide-react";
import { PageHeader } from "../components/notion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { ScoreBadge } from "../components/Ai";
import type { ClientRow } from "./Clients";

export interface JobOrder {
  id: string;
  client_id: string;
  title: string;
  headcount: number;
  salary_min: number | null;
  salary_max: number | null;
  due_date: string | null;
  status: string;
  request_id: string | null;
  request_date: string;
  area: string | null;
  contract_duration_months: number | null;
  gross_salary: number | null;
  business_status: string;
  requires_ojt: boolean;
  is_stale: boolean;
  source_document_file_name: string | null;
  has_source_document: boolean;
  is_public: boolean;
  public_client_label: string | null;
  screening_questions: ScreeningQuestion[];
}

interface ScreeningQuestion {
  id: string;
  prompt: string;
  required: boolean;
}

interface JobOrderExtract {
  object_key: string;
  file_name: string;
  requisition_code: string | null;
  job_title: string | null;
  client_name: string | null;
  area_location: string | null;
  headcount: number | null;
  request_effective_date: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  contract_duration_months: number | null;
  gross_basic_salary: number | null;
  mandatory_criteria: string[];
  preferred_criteria: string[];
  job_description_summary: string | null;
}

interface MatchCandidateRow {
  id: string;
  full_name: string;
  city: string | null;
  expected_salary: number | null;
}

interface MatchItem {
  candidate_id: string;
  match_score: number;
  explain: string;
  missing: string[];
}

const BUSINESS_STATUSES = ["dibuka", "ditahan", "dibatalkan", "terisi"];

const BUSINESS_STATUS_COLORS: Record<string, string> = {
  dibuka: "pill p-blue",
  ditahan: "pill p-yellow",
  dibatalkan: "pill p-red",
  terisi: "pill p-green",
};

export default function JobOrders() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [matchJoId, setMatchJoId] = useState<string | null>(null);
  const [matchResults, setMatchResults] = useState<MatchItem[] | null>(null);
  const [extracted, setExtracted] = useState<JobOrderExtract | null>(null);
  const [isPublic, setIsPublic] = useState(false);
  const [questions, setQuestions] = useState<ScreeningQuestion[]>([]);
  const { data: jobOrders } = useQuery({
    queryKey: ["job-orders"],
    queryFn: () => api.get<JobOrder[]>("/recruitment/job-orders"),
  });
  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const { data: matchCandidates } = useQuery({
    queryKey: ["candidates-for-match"],
    queryFn: () => api.get<MatchCandidateRow[]>("/recruitment/candidates"),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["job-orders"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const createJO = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/recruitment/job-orders", body),
    onSuccess: () => {
      setShowForm(false);
      setExtracted(null);
      invalidate();
    },
  });

  const extractDoc = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.upload<JobOrderExtract>("/recruitment/job-orders/extract", fd);
    },
    onSuccess: (data) => {
      setExtracted(data);
      setShowForm(true);
    },
  });

  const changeBusinessStatus = useMutation({
    mutationFn: ({ id, business_status }: { id: string; business_status: string }) =>
      api.patch(`/recruitment/job-orders/${id}`, { business_status }),
    onSuccess: invalidate,
  });

  const match = useMutation({
    mutationFn: (id: string) =>
      api.post<MatchItem[]>(`/recruitment/job-orders/${id}/match`, { top_k: 20 }),
    onSuccess: (data) => setMatchResults(data),
  });

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createJO.mutate({
      client_id: form.get("client_id"),
      title: form.get("title"),
      headcount: Number(form.get("headcount")) || 1,
      requirements: form.get("requirements") || null,
      salary_min: Number(form.get("salary_min")) || null,
      salary_max: Number(form.get("salary_max")) || null,
      due_date: form.get("due_date") || null,
      request_id: form.get("request_id") || null,
      request_date: form.get("request_date") || null,
      area: form.get("area") || null,
      contract_duration_months: Number(form.get("contract_duration_months")) || null,
      gross_salary: Number(form.get("gross_salary")) || null,
      requires_ojt: form.get("requires_ojt") === "on",
      source_document_object_key: extracted?.object_key ?? null,
      source_document_file_name: extracted?.file_name ?? null,
      is_public: form.get("is_public") === "on",
      public_client_label: form.get("public_client_label") || null,
      screening_questions: questions.filter((q) => q.prompt.trim()),
    });
  }

  const clientName = (id: string) => clients?.find((c) => c.id === id)?.name ?? "-";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader icon={Magnet} title="Job Orders" />
        <button
          className="btn"
          onClick={() => {
            setShowForm(!showForm);
            setExtracted(null);
            setIsPublic(false);
            setQuestions([]);
          }}
          disabled={!clients?.length}
        >
          {showForm ? "Tutup" : "+ Job Order Baru"}
        </button>
      </div>

      {!clients?.length && (
        <p className="text-sm text-[var(--n-text-muted)]">Tambahkan klien terlebih dahulu untuk membuat job order.</p>
      )}

      {showForm && (
        <div className="card space-y-3">
          <div>
            <label className="text-sm font-medium text-[var(--n-text)]">
              Upload Dokumen Job Order (opsional) — field di bawah akan diisi otomatis dari AI
            </label>
            <input
              type="file"
              accept=".pdf,.docx,image/png,image/jpeg,image/webp"
              disabled={extractDoc.isPending}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) extractDoc.mutate(file);
              }}
              className="input mt-1"
            />
            {extractDoc.isPending && (
              <p className="mt-1 text-xs text-[var(--n-text-muted)]">AI membaca dokumen...</p>
            )}
            {extractDoc.error && (
              <p className="mt-1 text-xs text-red-600">{(extractDoc.error as Error).message}</p>
            )}
            {extracted && !extractDoc.isPending && (
              <p className="mt-1 text-xs text-emerald-700">
                Diekstrak dari "{extracted.file_name}" — periksa & lengkapi field di bawah sebelum
                simpan.
                {extracted.client_name && (
                  <> Saran klien dari dokumen: <b>{extracted.client_name}</b> — pilih klien yang sesuai di dropdown.</>
                )}
              </p>
            )}
          </div>

          <form
            key={extracted?.object_key ?? "blank"}
            onSubmit={handleCreate}
            className="grid grid-cols-1 gap-3 sm:grid-cols-3"
          >
            <select name="client_id" required className="input">
              <option value="">-- Pilih klien --</option>
              {(clients ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <input
              name="title"
              required
              placeholder="Posisi *"
              defaultValue={extracted?.job_title ?? ""}
              className="input"
            />
            <input
              name="headcount"
              type="number"
              min={1}
              defaultValue={extracted?.headcount ?? 1}
              placeholder="Jumlah"
              className="input"
            />
            <input name="salary_min" type="number" placeholder="Gaji min (Rp)" className="input" />
            <input name="salary_max" type="number" placeholder="Gaji max (Rp)" className="input" />
            <input name="due_date" type="date" placeholder="Target tanggal" className="input" />
            <input
              name="request_id"
              placeholder="Request ID (kosongkan untuk auto-generate)"
              defaultValue={extracted?.requisition_code ?? ""}
              className="input"
            />
            <input
              name="request_date"
              type="date"
              defaultValue={extracted?.request_effective_date ?? new Date().toISOString().slice(0, 10)}
              title="Request Date"
              className="input"
            />
            <input name="area" placeholder="Area" defaultValue={extracted?.area_location ?? ""} className="input" />
            <input
              name="contract_duration_months"
              type="number"
              min={1}
              defaultValue={extracted?.contract_duration_months ?? undefined}
              placeholder="Durasi kontrak (bulan)"
              className="input"
            />
            <input
              name="gross_salary"
              type="number"
              defaultValue={extracted?.gross_basic_salary ?? undefined}
              placeholder="Gross Salary (Rp)"
              className="input"
            />
            <label className="input flex items-center gap-2 text-sm">
              <input name="requires_ojt" type="checkbox" className="h-4 w-4" />
              Butuh OJT (On Job Training)
            </label>
            <input
              name="requirements"
              placeholder="Kualifikasi"
              defaultValue={extracted?.mandatory_criteria?.join("; ") ?? ""}
              className="input sm:col-span-3"
            />

            <div className="sm:col-span-3 space-y-2 rounded-lg border p-3" style={{ borderColor: "var(--n-border)" }}>
              <label className="flex items-center gap-2 text-sm font-medium text-[var(--n-text)]">
                <input
                  name="is_public"
                  type="checkbox"
                  checked={isPublic}
                  onChange={(e) => setIsPublic(e.target.checked)}
                  className="h-4 w-4"
                />
                Tampilkan di Portal Karir Publik
              </label>
              {isPublic && (
                <div className="space-y-2">
                  <input
                    name="public_client_label"
                    placeholder='Nama klien di iklan (kosongkan = "Klien Konfidensial")'
                    className="input w-full"
                  />
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-[var(--n-text-muted)]">
                      Pertanyaan penyaring (opsional)
                    </p>
                    {questions.map((q, idx) => (
                      <div key={q.id} className="flex items-center gap-2">
                        <input
                          value={q.prompt}
                          onChange={(e) =>
                            setQuestions((qs) =>
                              qs.map((item, i) => (i === idx ? { ...item, prompt: e.target.value } : item))
                            )
                          }
                          placeholder={`Pertanyaan ${idx + 1}`}
                          className="input flex-1 py-1 text-xs"
                        />
                        <label className="flex items-center gap-1 text-xs text-[var(--n-text-muted)]">
                          <input
                            type="checkbox"
                            checked={q.required}
                            onChange={(e) =>
                              setQuestions((qs) =>
                                qs.map((item, i) => (i === idx ? { ...item, required: e.target.checked } : item))
                              )
                            }
                          />
                          Wajib
                        </label>
                        <button
                          type="button"
                          onClick={() => setQuestions((qs) => qs.filter((_, i) => i !== idx))}
                          className="text-xs text-red-600"
                        >
                          Hapus
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() =>
                        setQuestions((qs) => [...qs, { id: `q${qs.length + 1}`, prompt: "", required: true }])
                      }
                      className="btn-secondary py-1 text-xs"
                    >
                      + Tambah Pertanyaan
                    </button>
                  </div>
                </div>
              )}
            </div>

            <button type="submit" disabled={createJO.isPending} className="btn sm:col-span-3">
              Simpan Job Order
            </button>
          </form>
        </div>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-[var(--n-border)] bg-[var(--n-hover)]">
            <tr>
              <th className="th">Request ID</th>
              <th className="th">Posisi</th>
              <th className="th">Klien</th>
              <th className="th">Area</th>
              <th className="th">Kebutuhan</th>
              <th className="th">Range Gaji</th>
              <th className="th">Status</th>
              <th className="th">AI Matching</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--n-border)]">
            {(jobOrders ?? []).map((jo) => (
              <tr key={jo.id} className="hover:bg-[var(--n-hover)]">
                <td className="td">
                  {jo.has_source_document ? (
                    <a
                      href="#"
                      title={jo.source_document_file_name ?? "Lihat dokumen sumber"}
                      onClick={async (e) => {
                        e.preventDefault();
                        const { url } = await api.get<{ url: string }>(
                          `/recruitment/job-orders/${jo.id}/document/download-url`
                        );
                        window.open(url, "_blank");
                      }}
                      className="font-medium text-[var(--accent)] hover:opacity-80"
                    >
                      {jo.request_id ?? "-"}
                    </a>
                  ) : (
                    jo.request_id ?? "-"
                  )}
                  {jo.is_stale && (
                    <span
                      className="pill p-red ml-1 text-[10px]"
                      title={`Request Date: ${jo.request_date} — belum filled >=30 hari`}
                    >
                      &gt;30 hari
                    </span>
                  )}
                </td>
                <td className="td font-medium">{jo.title}</td>
                <td className="td">{clientName(jo.client_id)}</td>
                <td className="td">{jo.area ?? "-"}</td>
                <td className="td">{jo.headcount} orang</td>
                <td className="td">
                  {formatRupiah(jo.salary_min)} – {formatRupiah(jo.salary_max)}
                </td>
                <td className="td">
                  <select
                    value={jo.business_status}
                    onChange={(e) =>
                      changeBusinessStatus.mutate({ id: jo.id, business_status: e.target.value })
                    }
                    className={`cursor-pointer border-0 ${BUSINESS_STATUS_COLORS[jo.business_status]}`}
                  >
                    {BUSINESS_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="td">
                  <button
                    className="btn-secondary py-1 text-xs"
                    disabled={match.isPending}
                    onClick={() => {
                      setMatchJoId(jo.id);
                      match.mutate(jo.id);
                    }}
                  >
                    {match.isPending && matchJoId === jo.id ? "AI menilai..." : "Cari Kandidat"}
                  </button>
                </td>
              </tr>
            ))}
            {jobOrders?.length === 0 && (
              <tr>
                <td colSpan={8} className="td py-8 text-center text-[var(--n-text-muted)]">
                  Belum ada job order.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {(match.isPending || match.error || matchResults) && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-[var(--n-text)]">
              Hasil AI Matching — Talent Cloud
            </h2>
            {matchJoId && (
              <span className="text-xs text-[var(--n-text-muted)]">
                {jobOrders?.find((j) => j.id === matchJoId)?.title}
              </span>
            )}
          </div>
          <p className="text-[11px] text-[var(--n-text-muted)]">
            Matching native Talent Cloud — dikenakan 2k per pencarian job order, bukan per
            kandidat.
          </p>
          {match.isPending && (
            <p className="text-sm text-[var(--n-text-muted)]">
              AI sedang menilai kandidat (bisa memakan waktu beberapa saat)...
            </p>
          )}
          {match.error && (
            <p className="text-sm text-red-600">{(match.error as Error).message}</p>
          )}
          {matchResults && (
            <ol className="space-y-2">
              {matchResults.map((item, idx) => {
                const cand = matchCandidates?.find((c) => c.id === item.candidate_id);
                return (
                  <li key={item.candidate_id} className="flex gap-3">
                    <span className="w-6 pt-0.5 text-right text-sm font-bold text-[var(--n-text-muted)]">
                      {idx + 1}.
                    </span>
                    <div className="min-w-0 flex-1 rounded-lg border p-3" style={{ borderColor: "var(--n-border)" }}>
                      <p className="text-sm font-medium text-[var(--n-text)]">
                        {cand?.full_name ?? item.candidate_id}{" "}
                        <span className="ml-1 text-xs">
                          (skor <ScoreBadge score={item.match_score} />/100)
                        </span>
                      </p>
                      <p className="text-xs text-[var(--n-text-muted)]">
                        {cand?.city ?? "-"}
                        {cand?.expected_salary ? ` · ${formatRupiah(cand.expected_salary)}` : ""}
                      </p>
                      <p className="mt-1 text-sm text-[var(--n-text)]">{item.explain}</p>
                      {item.missing.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {item.missing.map((m) => (
                            <span key={m} className="pill p-red text-[10px]">
                              {m}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
              {matchResults.length === 0 && (
                <li className="text-sm text-[var(--n-text-muted)]">
                  Tidak ada kandidat aktif untuk job order ini.
                </li>
              )}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
