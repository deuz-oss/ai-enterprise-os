import { FormEvent, useState } from "react";
import { PageHeader } from "../components/notion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { api, formatRupiah } from "../api/client";

interface TenantRow {
  id: string;
  name: string;
  slug: string;
  status: string;
  billing_mode: string;
  created_at: string;
}

interface Provisioned {
  id: string;
  name: string;
  slug: string;
  admin_email: string;
  admin_initial_password: string;
}

interface LicenseRow {
  app_key: string;
  name: string;
  status: string | null;
}

interface UsageLine {
  sku: string;
  label: string;
  metric: string;
  qty?: number;
  qty_invoice?: number;
  qty_faktur?: number;
  rate?: number;
  base?: number;
  amount: number | null;
  note?: string;
}

interface UsageReport {
  period: string;
  billing_mode: string;
  lines: UsageLine[];
  total_known: number;
}

function currentPeriod(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const STATUS_BADGES: Record<string, string> = {
  aktif: "pill p-green",
  ditangguhkan: "pill p-red",
};

// Mode billing per-tenant — PRD v3.0 §1: internal bypass semua guard lisensi,
// commercial selalu enforce, inherit ikut APP_MODE global (.env).
const BILLING_MODE_LABELS: Record<string, { label: string; cls: string; hint: string }> = {
  inherit: { label: "inherit", cls: "pill p-gray", hint: "ikut APP_MODE global (.env)" },
  internal: { label: "internal", cls: "pill p-blue", hint: "bypass semua guard lisensi" },
  commercial: { label: "commercial", cls: "pill p-orange", hint: "selalu enforce lisensi" },
};

export default function PlatformTenants() {
  const qc = useQueryClient();
  const [provisioned, setProvisioned] = useState<Provisioned | null>(null);

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ role: string }>("/auth/me"),
  });
  const { data: tenants, isLoading } = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: () => api.get<TenantRow[]>("/platform/tenants"),
    enabled: me.data?.role === "platform_admin",
  });

  const provision = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<Provisioned>("/platform/tenants", body),
    onSuccess: (data) => {
      setProvisioned(data);
      qc.invalidateQueries({ queryKey: ["platform-tenants"] });
    },
  });

  const toggleStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/platform/tenants/${id}`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform-tenants"] }),
  });

  const setBillingMode = useMutation({
    mutationFn: ({ id, billingMode }: { id: string; billingMode: string }) =>
      api.patch(`/platform/tenants/${id}/billing-mode`, { billing_mode: billingMode }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform-tenants"] }),
  });

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { data: licenses } = useQuery({
    queryKey: ["licenses", expandedId],
    queryFn: () => api.get<LicenseRow[]>(`/platform/tenants/${expandedId}/licenses`),
    enabled: Boolean(expandedId),
  });

  const setLicense = useMutation({
    mutationFn: ({
      tenantId,
      appKey,
      status,
    }: {
      tenantId: string;
      appKey: string;
      status: string;
    }) =>
      api.patch(`/platform/tenants/${tenantId}/licenses/${appKey}`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["licenses"] }),
  });

  const [usageExpandedId, setUsageExpandedId] = useState<string | null>(null);
  const [usagePeriod, setUsagePeriod] = useState<string>(currentPeriod);
  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ["tenant-usage", usageExpandedId, usagePeriod],
    queryFn: () =>
      api.get<UsageReport>(
        `/platform/tenants/${usageExpandedId}/usage?period=${usagePeriod}`
      ),
    enabled: Boolean(usageExpandedId),
  });

  if (me.isLoading) return <p className="text-sm" style={{ color: "var(--n-text-muted)" }}>Memuat...</p>;
  if (me.data?.role !== "platform_admin") return <Navigate to="/" replace />;

  function handleProvision(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    provision.mutate({
      name: form.get("name"),
      slug: form.get("slug"),
      admin_email: form.get("admin_email"),
      admin_full_name: form.get("admin_full_name"),
      admin_password: form.get("admin_password"),
    });
  }

  return (
    <div className="space-y-4">
      <div>
        <PageHeader emoji="🏢" title="Manajemen Tenant" />
        <p className="mt-1 text-sm" style={{ color: "var(--n-text-muted)" }}>
          Platform SaaS — satu tenant = satu perusahaan outsourcing pelanggan.
        </p>
      </div>

      <form onSubmit={handleProvision} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
        <input name="name" required placeholder="Nama perusahaan *" className="input" />
        <input
          name="slug"
          required
          pattern="[a-z0-9-]{2,100}"
          title="huruf kecil, angka, tanda minus"
          placeholder="Slug (mis. pt-maju) *"
          className="input"
        />
        <input name="admin_full_name" required placeholder="Nama admin *" className="input" />
        <input
          name="admin_email"
          type="email"
          required
          placeholder="Email admin *"
          className="input"
        />
        <input
          name="admin_password"
          type="text"
          required
          minLength={8}
          placeholder="Password awal admin (min 8) *"
          className="input"
        />
        <button type="submit" disabled={provision.isPending} className="btn">
          {provision.isPending ? "Membuat..." : "+ Provision Tenant"}
        </button>
        {provision.error && (
          <p className="text-sm text-red-600 sm:col-span-3">
            {(provision.error as Error).message}
          </p>
        )}
      </form>

      {provisioned && (
        <div className="card border-l-4 border-emerald-500">
          <h2 className="font-semibold text-emerald-700">
            Tenant "{provisioned.name}" dibuat
          </h2>
          <p className="mt-2 text-sm" style={{ color: "var(--n-text-muted)" }}>
            Kredensial admin pertama — tampilkan <b>sekali ini saja</b>, teruskan ke klien:
          </p>
          <div className="mt-2 flex flex-wrap gap-4 font-mono text-sm">
            <span>Email: {provisioned.admin_email}</span>
            <span>Password: {provisioned.admin_initial_password}</span>
          </div>
          <button
            className="btn-secondary mt-3 text-xs"
            onClick={() => setProvisioned(null)}
          >
            Saya sudah menyimpan
          </button>
        </div>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">Nama</th>
              <th className="th">Slug</th>
              <th className="th">Status</th>
              <th className="th">Mode Billing</th>
              <th className="th">Dibuat</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(tenants ?? []).map((t) => {
              const bm = BILLING_MODE_LABELS[t.billing_mode] ?? BILLING_MODE_LABELS.inherit;
              return (
              <tr key={t.id} className="hover:bg-[var(--n-hover)]">
                <td className="td font-medium">{t.name}</td>
                <td className="td font-mono text-xs">{t.slug}</td>
                <td className="td">
                  <span className={`badge border-0 ${STATUS_BADGES[t.status] ?? ""}`}>
                    {t.status}
                  </span>
                </td>
                <td className="td">
                  <select
                    title={bm.hint}
                    value={t.billing_mode}
                    disabled={setBillingMode.isPending}
                    onChange={(e) =>
                      setBillingMode.mutate({ id: t.id, billingMode: e.target.value })
                    }
                    className={`badge cursor-pointer border-0 ${bm.cls}`}
                  >
                    {Object.entries(BILLING_MODE_LABELS).map(([value, meta]) => (
                      <option key={value} value={value}>
                        {meta.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="td text-xs" style={{ color: "var(--n-text-muted)" }}>
                  {new Date(t.created_at).toLocaleDateString("id-ID")}
                </td>
                <td className="td">
                  {t.status === "aktif" ? (
                    <button
                      className="btn-secondary py-1 text-xs text-rose-600"
                      disabled={toggleStatus.isPending}
                      onClick={() => toggleStatus.mutate({ id: t.id, status: "ditangguhkan" })}
                    >
                      Tangguhkan
                    </button>
                  ) : (
                    <button
                      className="btn-secondary py-1 text-xs text-emerald-700"
                      disabled={toggleStatus.isPending}
                      onClick={() => toggleStatus.mutate({ id: t.id, status: "aktif" })}
                    >
                      Aktifkan
                    </button>
                  )}
                  {" · "}
                  <button
                    className="text-xs font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                    onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}
                  >
                    {expandedId === t.id ? "Tutup Lisensi" : "Lisensi"}
                  </button>
                  {" · "}
                  <button
                    className="text-xs font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                    onClick={() => setUsageExpandedId(usageExpandedId === t.id ? null : t.id)}
                  >
                    {usageExpandedId === t.id ? "Tutup Tagihan" : "Estimasi Tagihan"}
                  </button>
                </td>
              </tr>
              );
            })}
            {(expandedId !== null) && (
              <tr>
                <td colSpan={6} className="td" style={{ backgroundColor: "var(--n-hover)" }}>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    {(licenses ?? []).map((lic) => (
                      <div
                        key={lic.app_key}
                        className="flex items-center justify-between gap-2 rounded-lg border p-2"
                        style={{ backgroundColor: "var(--n-bg-elevated)", borderColor: "var(--n-border)" }}
                      >
                        <span className="truncate text-xs font-medium" style={{ color: "var(--n-text)" }}>
                          {lic.name}
                        </span>
                        <select
                          value={lic.status ?? ""}
                          onChange={(e) =>
                            setLicense.mutate({
                              tenantId: expandedId,
                              appKey: lic.app_key,
                              status: e.target.value,
                            })
                          }
                          className="input w-auto py-1 text-xs"
                        >
                          <option value="">—</option>
                          <option value="aktif">aktif</option>
                          <option value="trial">trial</option>
                          <option value="kedaluwarsa">kedaluwarsa</option>
                        </select>
                      </div>
                    ))}
                  </div>
                </td>
              </tr>
            )}
            {usageExpandedId !== null && (
              <tr>
                <td colSpan={6} className="td" style={{ backgroundColor: "var(--n-hover)" }}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--n-text-muted)" }}>
                      Estimasi tagihan — belum menagih, hanya laporan pemakaian
                    </p>
                    <input
                      type="month"
                      value={usagePeriod}
                      onChange={(e) => setUsagePeriod(e.target.value || currentPeriod())}
                      className="input w-auto py-1 text-xs"
                    />
                  </div>
                  {usageLoading && (
                    <p className="mt-2 text-xs" style={{ color: "var(--n-text-muted)" }}>Memuat...</p>
                  )}
                  {usage && (
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr style={{ color: "var(--n-text-muted)" }}>
                            <th className="py-1 text-left">SKU</th>
                            <th className="py-1 text-right">Jumlah</th>
                            <th className="py-1 text-right">Estimasi</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
                          {usage.lines.map((line, idx) => (
                            <tr key={`${line.sku}-${line.metric}-${idx}`}>
                              <td className="py-1.5" style={{ color: "var(--n-text)" }}>
                                {line.label}
                              </td>
                              <td className="py-1.5 text-right" style={{ color: "var(--n-text-muted)" }}>
                                {line.qty !== undefined
                                  ? line.qty
                                  : line.qty_invoice !== undefined
                                    ? `${line.qty_invoice} inv · ${line.qty_faktur} faktur`
                                    : "—"}
                              </td>
                              <td className="py-1.5 text-right font-medium" style={{ color: "var(--n-text)" }}>
                                {line.amount !== null ? formatRupiah(line.amount) : (
                                  <span title={line.note} style={{ color: "var(--n-text-muted)" }}>
                                    belum diketahui
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                          {usage.lines.length === 0 && (
                            <tr>
                              <td colSpan={3} className="py-3 text-center" style={{ color: "var(--n-text-muted)" }}>
                                Tidak ada SKU berlisensi untuk periode ini.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                      <p className="mt-2 text-right text-sm font-semibold" style={{ color: "var(--n-text)" }}>
                        Total diketahui: {formatRupiah(usage.total_known)}
                      </p>
                    </div>
                  )}
                </td>
              </tr>
            )}
            {isLoading === false && tenants?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada tenant.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
        Menangguhkan tenant langsung memblokir seluruh akun di dalamnya saat login.
      </p>
    </div>
  );
}
