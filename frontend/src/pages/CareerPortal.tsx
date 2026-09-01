import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";

/** Halaman publik Job Portal (PRD v3.1 Patch 5) — TANPA Layout/sidebar,
 * diakses lintas-tenant via {tenantSlug} di URL, tanpa login sama sekali. */

interface PublicJobOrder {
  id: string;
  title: string;
  client_label: string;
  area: string | null;
  gross_salary: number | null;
  salary_min: number | null;
  salary_max: number | null;
  contract_duration_months: number | null;
  headcount: number;
  requirements: string | null;
  question_count: number;
}

interface ScreeningQuestion {
  id: string;
  prompt: string;
  required: boolean;
}

interface PublicJobOrderDetail extends PublicJobOrder {
  description: string | null;
  screening_questions: ScreeningQuestion[];
}

function CareerShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--n-bg)] px-4 py-10">
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-[var(--n-text)]">Karir</h1>
        {children}
      </div>
    </div>
  );
}

export function CareerListing() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["public-job-orders", tenantSlug],
    queryFn: () => api.get<PublicJobOrder[]>(`/public/${tenantSlug}/job-orders`),
  });

  return (
    <CareerShell>
      <p className="text-sm text-[var(--n-text-muted)]">Lowongan yang sedang dibuka.</p>
      {isLoading && <p className="text-sm text-[var(--n-text-muted)]">Memuat...</p>}
      {error && <p className="text-sm text-red-600">{(error as Error).message}</p>}
      <div className="space-y-3">
        {(data ?? []).map((jo) => (
          <Link
            key={jo.id}
            to={`/careers/${tenantSlug}/${jo.id}`}
            className="card block hover:bg-[var(--n-hover)]"
          >
            <p className="font-semibold text-[var(--n-text)]">{jo.title}</p>
            <p className="text-sm text-[var(--n-text-muted)]">
              {jo.client_label}
              {jo.area ? ` · ${jo.area}` : ""} · {jo.headcount} orang
            </p>
            <p className="mt-1 text-sm text-[var(--n-text)]">
              {jo.gross_salary
                ? formatRupiah(jo.gross_salary)
                : `${formatRupiah(jo.salary_min)} – ${formatRupiah(jo.salary_max)}`}
              {jo.contract_duration_months ? ` · ${jo.contract_duration_months} bulan` : ""}
            </p>
          </Link>
        ))}
        {data?.length === 0 && (
          <p className="text-sm text-[var(--n-text-muted)]">Belum ada lowongan yang dibuka saat ini.</p>
        )}
      </div>
    </CareerShell>
  );
}

export function CareerDetail() {
  const { tenantSlug, jobId } = useParams<{ tenantSlug: string; jobId: string }>();
  const [result, setResult] = useState<{ application_token: string; message: string } | null>(null);

  const { data: jo, isLoading, error } = useQuery({
    queryKey: ["public-job-order", tenantSlug, jobId],
    queryFn: () => api.get<PublicJobOrderDetail>(`/public/${tenantSlug}/job-orders/${jobId}`),
  });

  const apply = useMutation({
    mutationFn: (fd: FormData) =>
      api.upload<{ application_token: string; message: string }>(
        `/public/${tenantSlug}/job-orders/${jobId}/apply`,
        fd
      ),
    onSuccess: setResult,
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const fd = new FormData();
    fd.append("full_name", String(form.get("full_name") ?? ""));
    fd.append("email", String(form.get("email") ?? ""));
    fd.append("phone", String(form.get("phone") ?? ""));
    fd.append("consent", form.get("consent") === "on" ? "true" : "false");
    const file = form.get("file");
    if (file instanceof File) fd.append("file", file);
    const answers: Record<string, string> = {};
    (jo?.screening_questions ?? []).forEach((q) => {
      answers[q.id] = String(form.get(`q_${q.id}`) ?? "");
    });
    fd.append("screening_answers", JSON.stringify(answers));
    apply.mutate(fd);
  }

  if (isLoading) return <CareerShell><p className="text-sm text-[var(--n-text-muted)]">Memuat...</p></CareerShell>;
  if (error) return <CareerShell><p className="text-sm text-red-600">{(error as Error).message}</p></CareerShell>;
  if (!jo) return null;

  return (
    <CareerShell>
      <Link to={`/careers/${tenantSlug}`} className="text-sm text-[var(--accent)]">
        &larr; Kembali ke daftar lowongan
      </Link>
      <div className="card space-y-2">
        <h2 className="text-lg font-semibold text-[var(--n-text)]">{jo.title}</h2>
        <p className="text-sm text-[var(--n-text-muted)]">
          {jo.client_label}
          {jo.area ? ` · ${jo.area}` : ""} · {jo.headcount} orang
        </p>
        <p className="text-sm text-[var(--n-text)]">
          {jo.gross_salary
            ? formatRupiah(jo.gross_salary)
            : `${formatRupiah(jo.salary_min)} – ${formatRupiah(jo.salary_max)}`}
          {jo.contract_duration_months ? ` · Kontrak ${jo.contract_duration_months} bulan` : ""}
        </p>
        {jo.description && <p className="whitespace-pre-line text-sm text-[var(--n-text)]">{jo.description}</p>}
        {jo.requirements && (
          <div>
            <p className="text-sm font-medium text-[var(--n-text)]">Kualifikasi</p>
            <p className="whitespace-pre-line text-sm text-[var(--n-text-muted)]">{jo.requirements}</p>
          </div>
        )}
      </div>

      {result ? (
        <div className="card space-y-2 border-emerald-600">
          <p className="text-sm text-emerald-700">{result.message}</p>
          <p className="text-xs text-[var(--n-text-muted)]">Token lamaran Anda:</p>
          <p className="break-all rounded bg-[var(--n-hover)] p-2 font-mono text-sm">
            {result.application_token}
          </p>
          <Link
            to={`/careers/track/${result.application_token}`}
            className="text-sm text-[var(--accent)]"
          >
            Cek status lamaran &rarr;
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="card space-y-3">
          <h3 className="font-semibold text-[var(--n-text)]">Lamar Posisi Ini</h3>
          <input name="full_name" required placeholder="Nama Lengkap *" className="input w-full" />
          <input name="email" type="email" required placeholder="Email *" className="input w-full" />
          <input name="phone" placeholder="No. HP" className="input w-full" />
          <input name="file" type="file" required accept=".pdf,.docx,image/png,image/jpeg,image/webp" className="input w-full" />
          {jo.screening_questions.map((q) => (
            <div key={q.id}>
              <label className="text-sm text-[var(--n-text)]">{q.prompt}</label>
              <input name={`q_${q.id}`} required={q.required} className="input mt-1 w-full" />
            </div>
          ))}
          <label className="flex items-start gap-2 text-xs text-[var(--n-text-muted)]">
            <input name="consent" type="checkbox" required className="mt-0.5 h-4 w-4" />
            Saya setuju data pribadi saya diproses untuk keperluan rekrutmen ini (UU PDP).
          </label>
          {apply.error && <p className="text-sm text-red-600">{(apply.error as Error).message}</p>}
          <button type="submit" disabled={apply.isPending} className="btn w-full">
            {apply.isPending ? "Mengirim..." : "Kirim Lamaran"}
          </button>
        </form>
      )}
    </CareerShell>
  );
}

export function CareerTrack() {
  const { token: tokenParam } = useParams<{ token?: string }>();
  const [token, setTokenInput] = useState(tokenParam ?? "");
  const [activeToken, setActiveToken] = useState(tokenParam ?? "");

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-application-status", activeToken],
    queryFn: () =>
      api.get<{
        job_title: string;
        candidate_name: string;
        status_label: string;
        submitted_at: string | null;
      }>(`/public/applications/${activeToken}`),
    enabled: !!activeToken,
  });

  return (
    <CareerShell>
      <div className="card space-y-3">
        <h3 className="font-semibold text-[var(--n-text)]">Cek Status Lamaran</h3>
        <div className="flex gap-2">
          <input
            value={token}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="Token lamaran"
            className="input flex-1"
          />
          <button className="btn" onClick={() => setActiveToken(token)} disabled={!token}>
            Cek
          </button>
        </div>
        {isLoading && <p className="text-sm text-[var(--n-text-muted)]">Memuat...</p>}
        {error && <p className="text-sm text-red-600">{(error as Error).message}</p>}
        {data && (
          <div className="rounded-lg border p-3" style={{ borderColor: "var(--n-border)" }}>
            <p className="font-medium text-[var(--n-text)]">{data.job_title}</p>
            <p className="text-sm text-[var(--n-text-muted)]">{data.candidate_name}</p>
            <p className="mt-2 pill p-blue">{data.status_label}</p>
          </div>
        )}
      </div>
    </CareerShell>
  );
}
