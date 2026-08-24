import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { api } from "../api/client";

interface TenantRow {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
}

interface Provisioned {
  id: string;
  name: string;
  slug: string;
  admin_email: string;
  admin_initial_password: string;
}

const STATUS_BADGES: Record<string, string> = {
  aktif: "bg-emerald-100 text-emerald-700",
  ditangguhkan: "bg-rose-100 text-rose-700",
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

  if (me.isLoading) return <p className="text-sm text-slate-400">Memuat...</p>;
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
        <h1 className="text-2xl font-bold text-slate-800">Manajemen Tenant</h1>
        <p className="mt-1 text-sm text-slate-500">
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
          <p className="mt-2 text-sm text-slate-600">
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
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Nama</th>
              <th className="th">Slug</th>
              <th className="th">Status</th>
              <th className="th">Dibuat</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(tenants ?? []).map((t) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="td font-medium">{t.name}</td>
                <td className="td font-mono text-xs">{t.slug}</td>
                <td className="td">
                  <span className={`badge border-0 ${STATUS_BADGES[t.status] ?? ""}`}>
                    {t.status}
                  </span>
                </td>
                <td className="td text-xs text-slate-500">
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
                </td>
              </tr>
            ))}
            {isLoading === false && tenants?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center text-slate-400">
                  Belum ada tenant.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-400">
        Menangguhkan tenant langsung memblokir seluruh akun di dalamnya saat login.
      </p>
    </div>
  );
}
