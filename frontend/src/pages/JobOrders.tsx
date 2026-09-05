import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Magnet } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { KpiCard, PillTabs, type PillTab } from "../components/ui";
import { Pagination } from "../components/Pagination";
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
  benefits: string[];
  working_days: string[];
  working_hours_start: string | null;
  working_hours_end: string | null;
  has_generated_document: boolean;
  generated_document_at: string | null;
  remote: boolean;
  office_address: string | null;
  experience_level: string | null;
  contract_detail: string | null;
  industry: string | null;
  position: string | null;
  level: string | null;
  package_detail: string | null;
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
  const [workingDays, setWorkingDays] = useState<string[]>([]);
  const [offset, setOffset] = useState(0);
  const [clientFilter, setClientFilter] = useState("");
  // Tab/Pill filter (§1.5) atas business_status -- backend belum expose
  // param filter ini, jadi diambil sekaligus (limit besar, endpoint yang
  // sama persis dipakai tabel) lalu difilter+dipaginasi di klien supaya
  // count tiap pill akurat lintas-halaman.
  const [statusTab, setStatusTab] = useState("");
  const pageLimit = 50;
  // Sengaja cuma filter client_id -- jo_status (pipeline internal
  // open/screening/interview_klien/dst) sudah dihapus dari UI ini
  // sebelumnya atas permintaan eksplisit (dianggap membingungkan
  // berdampingan dengan business_status), tidak dikembalikan di sini.
  const { data: jobOrdersAll } = useQuery({
    queryKey: ["job-orders", clientFilter],
    queryFn: () =>
      api.getPaged<JobOrder>(
        `/recruitment/job-orders?limit=1000&offset=0${clientFilter ? `&client_id=${clientFilter}` : ""}`
      ),
  });
  const allRows = jobOrdersAll?.data ?? [];
  const businessFiltered = useMemo(
    () => allRows.filter((jo) => !statusTab || jo.business_status === statusTab),
    [allRows, statusTab]
  );
  const jobOrders = businessFiltered.slice(offset, offset + pageLimit);
  const jobOrdersTotal = businessFiltered.length;
  const statusTabs: PillTab[] = [
    { key: "", label: "Semua", count: allRows.length },
    ...BUSINESS_STATUSES.map((s) => ({
      key: s,
      label: s[0].toUpperCase() + s.slice(1),
      count: allRows.filter((jo) => jo.business_status === s).length,
    })),
  ];
  const staleCount = allRows.filter((jo) => jo.is_stale).length;
  const openCount = allRows.filter((jo) => jo.business_status === "dibuka").length;
  const filledCount = allRows.filter((jo) => jo.business_status === "terisi").length;
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
      benefits: String(form.get("benefits") || "")
        .split(",")
        .map((b) => b.trim())
        .filter(Boolean),
      working_days: workingDays,
      working_hours_start: form.get("working_hours_start") || null,
      working_hours_end: form.get("working_hours_end") || null,
      remote: form.get("remote") === "on",
      office_address: form.get("office_address") || null,
      experience_level: form.get("experience_level") || null,
      contract_detail: form.get("contract_detail") || null,
      industry: form.get("industry") || null,
      position: form.get("position") || null,
      level: form.get("level") || null,
      package_detail: form.get("package_detail") || null,
    });
  }

  const DAY_OPTIONS = ["senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu"];

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
            setWorkingDays([]);
          }}
          disabled={!clients?.length}
        >
          {showForm ? "Tutup" : "+ Job Order Baru"}
        </button>
      </div>

      {!clients?.length && (
        <p className="text-sm text-[var(--text-muted)]">Tambahkan klien terlebih dahulu untuk membuat job order.</p>
      )}

      {showForm && (
        <div className="card space-y-3">
          <div>
            <label className="text-sm font-medium text-[var(--text)]">
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
              <p className="mt-1 text-xs text-[var(--text-muted)]">AI membaca dokumen...</p>
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

            {/* Fase 24 — field tambahan hasil audit MYOHRIS. */}
            <div className="sm:col-span-3 space-y-2 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
              <label className="input flex items-center gap-2 text-sm">
                <input name="remote" type="checkbox" className="h-4 w-4" />
                Remote
              </label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <input name="office_address" placeholder="Alamat kantor" className="input" />
                <input name="experience_level" placeholder="Level pengalaman (mis. 1-3 tahun)" className="input" />
                <input name="contract_detail" placeholder="Full Time / Part Time" className="input" />
                <input name="industry" placeholder="Industri" className="input" />
                <input name="position" placeholder="Posisi (klasifikasi)" className="input" />
                <input name="level" placeholder="Level (mis. Junior/Senior)" className="input" />
                <input name="package_detail" placeholder="Paket benefit" className="input sm:col-span-3" />
              </div>
            </div>

            {/* Fase 21 item 1 — field terstruktur benefit & jam kerja, bukan
                lagi numpang di teks bebas description/requirements. */}
            <div className="sm:col-span-3 space-y-2 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
              <input
                name="benefits"
                placeholder="Benefit (pisah koma, mis. BPJS Kesehatan, Tunjangan Makan)"
                className="input w-full"
              />
              <div className="flex flex-wrap items-center gap-3">
                <input name="working_hours_start" type="time" title="Jam mulai kerja" className="input w-auto" />
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>s/d</span>
                <input name="working_hours_end" type="time" title="Jam selesai kerja" className="input w-auto" />
              </div>
              <div className="flex flex-wrap gap-2">
                {DAY_OPTIONS.map((d) => (
                  <label key={d} className="flex items-center gap-1 text-xs capitalize" style={{ color: "var(--text-muted)" }}>
                    <input
                      type="checkbox"
                      checked={workingDays.includes(d)}
                      onChange={(e) =>
                        setWorkingDays((days) =>
                          e.target.checked ? [...days, d] : days.filter((x) => x !== d)
                        )
                      }
                    />
                    {d}
                  </label>
                ))}
              </div>
            </div>

            <div className="sm:col-span-3 space-y-2 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
              <label className="flex items-center gap-2 text-sm font-medium text-[var(--text)]">
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
                    <p className="text-xs font-medium text-[var(--text-muted)]">
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
                        <label className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
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

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Job Order" value={allRows.length} icon={Magnet} iconTone="info" />
        <KpiCard label="Dibuka" value={openCount} icon={Magnet} iconTone="accent" />
        <KpiCard label="Terisi" value={filledCount} icon={CheckCircle2} iconTone="success" />
        <KpiCard
          label="Lewat 30 Hari"
          value={staleCount}
          icon={AlertTriangle}
          iconTone="danger"
          context="Belum filled sejak request date"
          badge={staleCount > 0 ? { label: "Kritis", tone: "danger" } : undefined}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <PillTabs
          tabs={statusTabs}
          value={statusTab}
          onChange={(k) => {
            setStatusTab(k);
            setOffset(0);
          }}
        />
        <select
          value={clientFilter}
          onChange={(e) => {
            setClientFilter(e.target.value);
            setOffset(0);
          }}
          className="input w-auto"
        >
          <option value="">Semua klien</option>
          {(clients ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-[var(--border)] bg-[var(--hover)]">
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
          <tbody className="divide-y divide-[var(--border)]">
            {jobOrders.map((jo) => (
              <tr key={jo.id} className="hover:bg-[var(--hover)]">
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
                <td className="td font-medium">
                  <Link to={`/job-orders/${jo.id}`} className="hover:opacity-80" style={{ color: "var(--accent)" }}>
                    {jo.title}
                  </Link>
                </td>
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
            {jobOrders.length === 0 && (
              <tr>
                <td colSpan={8} className="td py-8 text-center text-[var(--text-muted)]">
                  {allRows.length === 0 ? "Belum ada job order." : "Tidak ada job order untuk status ini."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination offset={offset} limit={pageLimit} total={jobOrdersTotal} onOffsetChange={setOffset} />

      {(match.isPending || match.error || matchResults) && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-[var(--text)]">
              Hasil AI Matching
            </h2>
            {matchJoId && (
              <span className="text-xs text-[var(--text-muted)]">
                {allRows.find((j) => j.id === matchJoId)?.title}
              </span>
            )}
          </div>
          <p className="text-[11px] text-[var(--text-muted)]">
            Matching native — dikenakan Rp2.000 per pencarian job order, bukan per
            kandidat.
          </p>
          {match.isPending && (
            <p className="text-sm text-[var(--text-muted)]">
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
                    <span className="w-6 pt-0.5 text-right text-sm font-bold text-[var(--text-muted)]">
                      {idx + 1}.
                    </span>
                    <div className="min-w-0 flex-1 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                      <p className="text-sm font-medium text-[var(--text)]">
                        {cand?.full_name ?? item.candidate_id}{" "}
                        <span className="ml-1 text-xs">
                          (skor <ScoreBadge score={item.match_score} />/100)
                        </span>
                      </p>
                      <p className="text-xs text-[var(--text-muted)]">
                        {cand?.city ?? "-"}
                        {cand?.expected_salary ? ` · ${formatRupiah(cand.expected_salary)}` : ""}
                      </p>
                      <p className="mt-1 text-sm text-[var(--text)]">{item.explain}</p>
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
                <li className="text-sm text-[var(--text-muted)]">
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
