import { FormEvent, useMemo, useRef, useState } from "react";
import { Building2, CalendarClock, UserX } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { KpiCard, PillTabs, type PillTab } from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export interface ClientRow {
  id: string;
  name: string;
  npwp: string | null;
  pic_name: string | null;
  pic_phone: string | null;
  status: string;
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

export default function Clients() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusTab, setStatusTab] = useState("semua");
  const fileRef = useRef<HTMLInputElement>(null);
  const docTypeRef = useRef<HTMLSelectElement>(null);

  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });

  const filteredClients = useMemo(
    () => (clients ?? []).filter((c) => statusTab === "semua" || c.status === statusTab),
    [clients, statusTab]
  );
  const statusTabs: PillTab[] = useMemo(() => {
    const all = clients ?? [];
    return [
      { key: "semua", label: "Semua", count: all.length },
      { key: "aktif", label: "Aktif", count: all.filter((c) => c.status === "aktif").length },
      { key: "berhenti", label: "Berhenti", count: all.filter((c) => c.status === "berhenti").length },
    ];
  }, [clients]);

  // KPI row (§1.3) -- semua dihitung dari `clients` yang sudah di-fetch.
  const activeClients = (clients ?? []).filter((c) => c.status === "aktif");
  const churnedCount = (clients ?? []).filter((c) => c.status === "berhenti").length;
  const expiringSoon = useMemo(() => {
    const now = Date.now();
    const in30d = now + 30 * 24 * 60 * 60 * 1000;
    return activeClients.filter((c) => {
      if (!c.contract_end) return false;
      const t = new Date(c.contract_end).getTime();
      return t >= now && t <= in30d;
    });
  }, [activeClients]);
  const { data: documents } = useQuery({
    queryKey: ["client-docs", selectedId],
    queryFn: () => api.get<LegalDoc[]>(`/clients/${selectedId}/documents`),
    enabled: Boolean(selectedId),
  });
  const { data: portalAccess } = useQuery({
    queryKey: ["client-portal-access", selectedId],
    queryFn: () => api.get<PortalAccessStatus | null>(`/clients/${selectedId}/portal-access`),
    enabled: Boolean(selectedId),
  });
  const [portalUrl, setPortalUrl] = useState<string | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [gpsCoord, setGpsCoord] = useState<{ lat: string; lng: string } | null>(null);
  const siteFormRef = useRef<HTMLFormElement>(null);

  const { data: sites } = useQuery({
    queryKey: ["client-sites", selectedId],
    queryFn: () => api.get<ClientSite[]>(`/clients/${selectedId}/sites`),
    enabled: Boolean(selectedId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["clients"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const createClient = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/clients", body),
    onSuccess: () => {
      setShowForm(false);
      invalidate();
    },
  });

  const uploadDoc = useMutation({
    mutationFn: ({ id, formData }: { id: string; formData: FormData }) =>
      api.upload(`/clients/${id}/documents`, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-docs", selectedId] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const generatePortalAccess = useMutation({
    mutationFn: (id: string) =>
      api.post<{ access: PortalAccessStatus; url: string }>(`/clients/${id}/portal-access`, {}),
    onSuccess: (data) => {
      setPortalUrl(`${window.location.origin}${data.url}`);
      qc.invalidateQueries({ queryKey: ["client-portal-access", selectedId] });
    },
  });
  const revokePortalAccess = useMutation({
    mutationFn: (id: string) => api.delete(`/clients/${id}/portal-access`),
    onSuccess: () => {
      setPortalUrl(null);
      qc.invalidateQueries({ queryKey: ["client-portal-access", selectedId] });
    },
  });

  const createSite = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(`/clients/${selectedId}/sites`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-sites", selectedId] });
      setGpsCoord(null);
      siteFormRef.current?.reset();
    },
  });
  const deleteSite = useMutation({
    mutationFn: (siteId: string) => api.delete(`/clients/sites/${siteId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["client-sites", selectedId] }),
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
    if (!selectedId) return;
    const form = new FormData(e.currentTarget);
    createSite.mutate({
      name: form.get("name"),
      address: form.get("address") || null,
      latitude: form.get("latitude"),
      longitude: form.get("longitude"),
      radius_meters: Number(form.get("radius_meters")),
    });
  }

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createClient.mutate({
      name: form.get("name"),
      npwp: form.get("npwp") || null,
      pic_name: form.get("pic_name") || null,
      pic_phone: form.get("pic_phone") || null,
      contract_end: form.get("contract_end") || null,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader icon={Building2} title="Klien" />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Klien Baru"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
          <input name="name" required placeholder="Nama perusahaan klien *" className="input" />
          <input name="npwp" placeholder="NPWP" className="input" />
          <input name="pic_name" placeholder="Nama PIC" className="input" />
          <input name="pic_phone" placeholder="Telepon PIC" className="input" />
          <input name="contract_end" type="date" placeholder="Akhir kontrak" className="input" />
          <button type="submit" disabled={createClient.isPending} className="btn sm:col-span-3">
            Simpan Klien
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Klien" value={(clients ?? []).length} icon={Building2} iconTone="info" />
        <KpiCard
          label="Klien Aktif"
          value={activeClients.length}
          icon={Building2}
          iconTone="success"
          context={`dari ${(clients ?? []).length} klien terdaftar`}
        />
        <KpiCard
          label="Kontrak Akan Berakhir"
          value={expiringSoon.length}
          icon={CalendarClock}
          iconTone="warning"
          context="Dalam 30 hari ke depan"
          badge={expiringSoon.length > 0 ? { label: "Perlu Tindak Lanjut", tone: "warning" } : undefined}
        />
        <KpiCard label="Klien Berhenti" value={churnedCount} icon={UserX} iconTone="neutral" />
      </div>

      <PillTabs tabs={statusTabs} value={statusTab} onChange={setStatusTab} />

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
            <tr>
              <th className="th">Perusahaan</th>
              <th className="th">NPWP</th>
              <th className="th">PIC</th>
              <th className="th">Akhir Kontrak</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {filteredClients.map((c) => (
              <tr
                key={c.id}
                onClick={() => setSelectedId(c.id === selectedId ? null : c.id)}
                className="cursor-pointer transition-colors hover:bg-[var(--hover)]"
                style={{ backgroundColor: selectedId === c.id ? "var(--accent-tint)" : undefined }}
              >
                <td className="td font-medium">{c.name}</td>
                <td className="td">{c.npwp ?? "-"}</td>
                <td className="td">{c.pic_name ?? "-"}</td>
                <td className="td">{c.contract_end ?? "-"}</td>
                <td className="td">
                  <span
                    className={`pill ${
                      c.status === "aktif"
                        ? "p-green"
                        : "p-gray"
                    }`}
                  >
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
            {filteredClients.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  {clients?.length === 0 ? "Belum ada klien." : "Tidak ada klien untuk status ini."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId && (
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
              uploadDoc.mutate({ id: selectedId, formData: fd });
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

      {selectedId && (
        <div className="card space-y-2">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Portal Klien</h2>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Link tanpa akun untuk klien memantau kehadiran &amp; lembur karyawan yang ditempatkan
            di perusahaan mereka (read-only).
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
                  onClick={() => generatePortalAccess.mutate(selectedId)}
                >
                  Buat Ulang Link
                </button>
                <button
                  className="btn-secondary text-rose-600"
                  disabled={revokePortalAccess.isPending}
                  onClick={() => revokePortalAccess.mutate(selectedId)}
                >
                  Cabut Akses
                </button>
              </div>
            </div>
          ) : (
            <button
              className="btn-secondary"
              disabled={generatePortalAccess.isPending}
              onClick={() => generatePortalAccess.mutate(selectedId)}
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
      )}

      {selectedId && (
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
      )}
    </div>
  );
}
