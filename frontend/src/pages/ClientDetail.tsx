import { FormEvent, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { initials } from "../components/workspace";
import { Badge, PillTabs } from "../components/ui";

interface ClientDetailData {
  id: string;
  name: string;
  npwp: string | null;
  address: string | null;
  pic_name: string | null;
  pic_phone: string | null;
  pic_email: string | null;
  status: string;
  contract_start: string | null;
  contract_end: string | null;
}

interface LegalDoc {
  id: string;
  document_type: string;
  title: string;
  version: number;
  file_name: string;
  file_size: number;
  uploaded_at: string;
}

interface PortalAccessStatus {
  id: string;
  created_at: string;
  last_accessed_at: string | null;
}

interface ClientSite {
  id: string;
  client_id: string;
  name: string;
  address: string | null;
  latitude: string;
  longitude: string;
  radius_meters: number;
}

interface JobOrderRow {
  id: string;
  title: string;
  headcount: number;
  status: string;
  due_date: string | null;
}

interface ClientEmployeeRow {
  id: string;
  full_name: string;
  employee_no: string;
  status: string;
  join_date: string | null;
}

interface AuditLogRow {
  id: string;
  action: string;
  user_id: string | null;
  created_at: string;
}

function getGpsPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Perangkat/browser ini tidak mendukung GPS."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      resolve,
      () => reject(new Error("Gagal mengambil lokasi GPS -- pastikan izin lokasi diaktifkan.")),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });
}

const DOC_TYPES = ["perjanjian_kerjasama", "addendum", "npwp", "nib", "lainnya"];

const TYPE_LABELS: Record<string, string> = {
  perjanjian_kerjasama: "Perjanjian Kerjasama",
  addendum: "Addendum",
  npwp: "NPWP",
  nib: "NIB",
  lainnya: "Lainnya",
};

type TabKey = "ringkasan" | "jobs" | "karyawan" | "dokumen" | "portal-lokasi" | "riwayat";

export default function ClientDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabKey>("ringkasan");
  const fileRef = useRef<HTMLInputElement>(null);
  const docTypeRef = useRef<HTMLSelectElement>(null);
  const [portalUrl, setPortalUrl] = useState<string | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [gpsCoord, setGpsCoord] = useState<{ lat: string; lng: string } | null>(null);
  const siteFormRef = useRef<HTMLFormElement>(null);

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ role: string }>("/auth/me"),
  });
  const isManagement = me?.role === "admin" || me?.role === "management";

  const { data: client, isLoading, error } = useQuery({
    queryKey: ["client", id],
    queryFn: () => api.get<ClientDetailData>(`/clients/${id}`),
    enabled: Boolean(id),
  });

  const { data: documents } = useQuery({
    queryKey: ["client-docs", id],
    queryFn: () => api.get<LegalDoc[]>(`/clients/${id}/documents`),
    enabled: Boolean(id) && tab === "dokumen",
  });
  const { data: portalAccess } = useQuery({
    queryKey: ["client-portal-access", id],
    queryFn: () => api.get<PortalAccessStatus | null>(`/clients/${id}/portal-access`),
    enabled: Boolean(id) && tab === "portal-lokasi",
  });
  const { data: sites } = useQuery({
    queryKey: ["client-sites", id],
    queryFn: () => api.get<ClientSite[]>(`/clients/${id}/sites`),
    enabled: Boolean(id) && tab === "portal-lokasi",
  });
  const { data: jobOrders } = useQuery({
    queryKey: ["client-job-orders", id],
    queryFn: () => api.get<JobOrderRow[]>(`/recruitment/job-orders?client_id=${id}`),
    enabled: Boolean(id),
  });
  const { data: employees } = useQuery({
    queryKey: ["client-employees", id],
    queryFn: () => api.get<ClientEmployeeRow[]>(`/clients/${id}/employees`),
    enabled: Boolean(id),
  });
  const { data: auditLogs } = useQuery({
    queryKey: ["client-audit", id],
    queryFn: () =>
      api.get<{ items: AuditLogRow[] }>(
        `/audit/logs?entity_type=client&entity_id=${id}`
      ),
    enabled: Boolean(id) && tab === "riwayat" && isManagement,
  });

  const invalidateClient = () => qc.invalidateQueries({ queryKey: ["client", id] });

  const updateClient = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch(`/clients/${id}`, body),
    onSuccess: () => {
      invalidateClient();
      qc.invalidateQueries({ queryKey: ["client-audit", id] });
    },
  });

  const uploadDoc = useMutation({
    mutationFn: (formData: FormData) => api.upload(`/clients/${id}/documents`, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-docs", id] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const generatePortalAccess = useMutation({
    mutationFn: () =>
      api.post<{ access: PortalAccessStatus; url: string }>(`/clients/${id}/portal-access`, {}),
    onSuccess: (data) => {
      setPortalUrl(`${window.location.origin}${data.url}`);
      qc.invalidateQueries({ queryKey: ["client-portal-access", id] });
    },
  });
  const revokePortalAccess = useMutation({
    mutationFn: () => api.delete(`/clients/${id}/portal-access`),
    onSuccess: () => {
      setPortalUrl(null);
      qc.invalidateQueries({ queryKey: ["client-portal-access", id] });
    },
  });

  const createSite = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post(`/clients/${id}/sites`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-sites", id] });
      setGpsCoord(null);
      siteFormRef.current?.reset();
    },
  });
  const deleteSite = useMutation({
    mutationFn: (siteId: string) => api.delete(`/clients/sites/${siteId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["client-sites", id] }),
  });

  async function handleUseCurrentLocation() {
    setGpsError(null);
    try {
      const pos = await getGpsPosition();
      setGpsCoord({
        lat: pos.coords.latitude.toFixed(6),
        lng: pos.coords.longitude.toFixed(6),
      });
    } catch (err) {
      setGpsError(err instanceof Error ? err.message : "Gagal mengambil lokasi GPS.");
    }
  }

  function handleCreateSite(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!id) return;
    const form = new FormData(e.currentTarget);
    createSite.mutate({
      name: form.get("name"),
      address: form.get("address") || null,
      latitude: form.get("latitude"),
      longitude: form.get("longitude"),
      radius_meters: Number(form.get("radius_meters")),
    });
  }

  function handleUpdateClient(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    updateClient.mutate({
      name: form.get("name"),
      npwp: form.get("npwp") || null,
      address: form.get("address") || null,
      pic_name: form.get("pic_name") || null,
      pic_phone: form.get("pic_phone") || null,
      pic_email: form.get("pic_email") || null,
      contract_start: form.get("contract_start") || null,
      contract_end: form.get("contract_end") || null,
    });
  }

  if (isLoading) {
    return <p className="text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>;
  }
  if (error || !client || !id) {
    return (
      <p className="text-sm text-red-600">
        {error ? (error as Error).message : "Klien tidak ditemukan."}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <Link
        to="/clients"
        className="inline-flex items-center gap-1.5 text-xs font-medium"
        style={{ color: "var(--text-muted)" }}
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Klien
      </Link>

      <div className="flex items-center gap-4">
        <span
          className="flex h-14 w-14 items-center justify-center rounded-full text-lg font-bold text-[var(--accent-contrast)]"
          style={{ backgroundColor: "var(--accent)" }}
        >
          {initials(client.name)}
        </span>
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold leading-tight" style={{ color: "var(--text)" }}>
            {client.name}
          </h1>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {client.contract_start ?? "?"} — {client.contract_end ?? "?"}
          </p>
          <Badge tone={client.status === "aktif" ? "success" : "neutral"}>{client.status}</Badge>
        </div>
      </div>

      <PillTabs
        tabs={[
          { key: "ringkasan", label: "Ringkasan" },
          { key: "jobs", label: "Jobs", count: jobOrders?.length ?? 0 },
          { key: "karyawan", label: "Karyawan", count: employees?.length ?? 0 },
          { key: "dokumen", label: "Dokumen", count: documents?.length ?? 0 },
          { key: "portal-lokasi", label: "Portal & Lokasi" },
          ...(isManagement ? [{ key: "riwayat", label: "Riwayat" }] : []),
        ]}
        value={tab}
        onChange={(k) => setTab(k as TabKey)}
      />

      {tab === "ringkasan" && (
        <div className="card space-y-4">
          <form onSubmit={handleUpdateClient} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <input name="name" required defaultValue={client.name} placeholder="Nama perusahaan" className="input" />
            <input name="npwp" defaultValue={client.npwp ?? ""} placeholder="NPWP" className="input" />
            <input name="address" defaultValue={client.address ?? ""} placeholder="Alamat" className="input" />
            <input name="pic_name" defaultValue={client.pic_name ?? ""} placeholder="Nama PIC" className="input" />
            <input name="pic_phone" defaultValue={client.pic_phone ?? ""} placeholder="Telepon PIC" className="input" />
            <input name="pic_email" defaultValue={client.pic_email ?? ""} placeholder="Email PIC" className="input" />
            <input name="contract_start" type="date" defaultValue={client.contract_start ?? ""} className="input" />
            <input name="contract_end" type="date" defaultValue={client.contract_end ?? ""} className="input" />
            <button type="submit" disabled={updateClient.isPending} className="btn sm:col-span-3">
              Simpan Perubahan
            </button>
          </form>
        </div>
      )}

      {tab === "jobs" && (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
              <tr>
                <th className="th">Judul</th>
                <th className="th">Headcount</th>
                <th className="th">Status</th>
                <th className="th">Jatuh Tempo</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
              {(jobOrders ?? []).map((jo) => (
                <tr key={jo.id}>
                  <td className="td font-medium">
                    <Link to={`/job-orders/${jo.id}`} style={{ color: "var(--accent)" }}>
                      {jo.title}
                    </Link>
                  </td>
                  <td className="td">{jo.headcount}</td>
                  <td className="td">{jo.status}</td>
                  <td className="td">{jo.due_date ?? "-"}</td>
                </tr>
              ))}
              {jobOrders?.length === 0 && (
                <tr>
                  <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                    Belum ada job order untuk klien ini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "karyawan" && (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
              <tr>
                <th className="th">Nama</th>
                <th className="th">No. Induk</th>
                <th className="th">Status</th>
                <th className="th">Tanggal Masuk</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
              {(employees ?? []).map((e) => (
                <tr key={e.id}>
                  <td className="td font-medium">
                    <Link to={`/employees/${e.id}`} style={{ color: "var(--accent)" }}>
                      {e.full_name}
                    </Link>
                  </td>
                  <td className="td font-mono text-xs">{e.employee_no}</td>
                  <td className="td">{e.status}</td>
                  <td className="td">{e.join_date ?? "-"}</td>
                </tr>
              ))}
              {employees?.length === 0 && (
                <tr>
                  <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                    Belum ada karyawan yang ditempatkan di klien ini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "dokumen" && (
        <div className="card">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Dokumen Legalitas</h2>
          <form
            className="mt-3 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!fileRef.current?.files?.[0]) return;
              const fd = new FormData();
              fd.append("file", fileRef.current.files[0]);
              fd.append("document_type", docTypeRef.current?.value ?? "lainnya");
              uploadDoc.mutate(fd);
            }}
          >
            <select ref={docTypeRef} className="input w-auto">
              {DOC_TYPES.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABELS[t]}
                </option>
              ))}
            </select>
            <input ref={fileRef} type="file" required className="input w-auto" />
            <button className="btn-secondary">Upload</button>
          </form>
          <ul className="mt-3 space-y-2">
            {(documents ?? []).map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between rounded-lg p-3 text-sm"
                style={{ backgroundColor: "var(--hover)" }}
              >
                <div>
                  <p className="font-medium" style={{ color: "var(--text)" }}>
                    {TYPE_LABELS[d.document_type]} — v{d.version}
                  </p>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {d.file_name} · {(d.file_size / 1024).toFixed(0)} KB
                  </p>
                </div>
                <a
                  href="#"
                  onClick={async (e) => {
                    e.preventDefault();
                    const { url } = await api.get<{ url: string }>(
                      `/clients/documents/${d.id}/download-url`
                    );
                    window.open(url, "_blank");
                  }}
                  className="text-sm font-medium hover:opacity-80"
                  style={{ color: "var(--accent)" }}
                >
                  Unduh
                </a>
              </li>
            ))}
            {documents?.length === 0 && (
              <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada dokumen.</li>
            )}
          </ul>
        </div>
      )}

      {tab === "portal-lokasi" && (
        <div className="space-y-4">
          <div className="card space-y-2">
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Portal Klien</h2>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Link tanpa akun untuk klien memantau kehadiran &amp; lembur karyawan yang
              ditempatkan di perusahaan mereka (read-only).
            </p>
            {portalAccess ? (
              <div className="space-y-2">
                <p className="text-sm" style={{ color: "var(--text)" }}>
                  Dibuat {new Date(portalAccess.created_at).toLocaleString("id-ID")}
                  {portalAccess.last_accessed_at
                    ? ` · terakhir diakses ${new Date(portalAccess.last_accessed_at).toLocaleString("id-ID")}`
                    : " · belum pernah diakses"}
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    className="btn-secondary"
                    disabled={generatePortalAccess.isPending}
                    onClick={() => generatePortalAccess.mutate()}
                  >
                    Buat Ulang Link
                  </button>
                  <button
                    className="btn-secondary text-rose-600"
                    disabled={revokePortalAccess.isPending}
                    onClick={() => revokePortalAccess.mutate()}
                  >
                    Cabut Akses
                  </button>
                </div>
              </div>
            ) : (
              <button
                className="btn-secondary"
                disabled={generatePortalAccess.isPending}
                onClick={() => generatePortalAccess.mutate()}
              >
                Buat Link Portal
              </button>
            )}
            {portalUrl && (
              <div
                className="rounded-lg p-3 text-sm"
                style={{ backgroundColor: "var(--accent-tint)", border: "1px solid var(--border)" }}
              >
                <p style={{ color: "var(--text)" }}>
                  Bagikan link ini ke PIC klien (mis. lewat WhatsApp/email):
                </p>
                <code className="mt-1 block break-all text-xs">{portalUrl}</code>
                <button
                  className="btn-secondary mt-2"
                  onClick={() => navigator.clipboard.writeText(portalUrl)}
                >
                  Salin Link
                </button>
              </div>
            )}
          </div>

          <div className="card space-y-3">
            <div>
              <h2 className="font-semibold" style={{ color: "var(--text)" }}>Lokasi Kantor</h2>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Klien dengan banyak cabang bisa punya beberapa lokasi. Karyawan yang ditautkan ke
                salah satu lokasi ini (di halaman Karyawan) wajib absen dalam radiusnya; tanpa
                lokasi, absen tetap bebas seperti biasa.
              </p>
            </div>

            <ul className="space-y-2">
              {(sites ?? []).map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between rounded-lg p-3 text-sm"
                  style={{ backgroundColor: "var(--hover)" }}
                >
                  <div>
                    <p className="font-medium" style={{ color: "var(--text)" }}>{s.name}</p>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {s.address ? `${s.address} · ` : ""}
                      {s.latitude}, {s.longitude} · radius {s.radius_meters}m
                    </p>
                  </div>
                  <button
                    className="btn-secondary text-rose-600"
                    disabled={deleteSite.isPending}
                    onClick={() => deleteSite.mutate(s.id)}
                  >
                    Hapus
                  </button>
                </li>
              ))}
              {sites?.length === 0 && (
                <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada lokasi.</li>
              )}
            </ul>

            <form
              ref={siteFormRef}
              onSubmit={handleCreateSite}
              className="flex flex-wrap items-end gap-2 border-t pt-3"
              style={{ borderColor: "var(--border)" }}
            >
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--text-muted)" }}>Nama</label>
                <input name="name" required placeholder="Kantor Pusat" className="input w-40" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--text-muted)" }}>Alamat</label>
                <input name="address" placeholder="Opsional" className="input w-48" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--text-muted)" }}>Latitude</label>
                <input
                  key={`lat-${gpsCoord?.lat ?? ""}`}
                  name="latitude"
                  required
                  defaultValue={gpsCoord?.lat ?? ""}
                  placeholder="-6.200000"
                  className="input w-28"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--text-muted)" }}>Longitude</label>
                <input
                  key={`lng-${gpsCoord?.lng ?? ""}`}
                  name="longitude"
                  required
                  defaultValue={gpsCoord?.lng ?? ""}
                  placeholder="106.816666"
                  className="input w-28"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: "var(--text-muted)" }}>Radius (m)</label>
                <input
                  name="radius_meters"
                  type="number"
                  min={1}
                  required
                  defaultValue={100}
                  className="input w-24"
                />
              </div>
              <button type="button" className="btn-secondary" onClick={handleUseCurrentLocation}>
                Pakai Lokasi Saat Ini
              </button>
              <button type="submit" className="btn" disabled={createSite.isPending}>
                Tambah Lokasi
              </button>
            </form>
            {gpsError && <p className="text-xs text-rose-600">{gpsError}</p>}
          </div>
        </div>
      )}

      {tab === "riwayat" && isManagement && (
        <div className="card overflow-x-auto p-0">
          <table className="w-full">
            <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
              <tr>
                <th className="th">Aksi</th>
                <th className="th">Oleh</th>
                <th className="th">Waktu</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
              {(auditLogs?.items ?? []).map((l) => (
                <tr key={l.id}>
                  <td className="td font-medium">{l.action}</td>
                  <td className="td font-mono text-xs">{l.user_id ? `${l.user_id.slice(0, 8)}…` : "-"}</td>
                  <td className="td">{new Date(l.created_at).toLocaleString("id-ID")}</td>
                </tr>
              ))}
              {(auditLogs?.items ?? []).length === 0 && (
                <tr>
                  <td colSpan={3} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                    Belum ada riwayat aktivitas untuk klien ini.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
