import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
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
  job_count: number;
}

export default function Clients() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [statusTab, setStatusTab] = useState("semua");

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

  const createClient = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/clients", body),
    onSuccess: () => {
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["clients"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });

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
              <th className="th">Jobs</th>
              <th className="th">Akhir Kontrak</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {filteredClients.map((c) => (
              <tr
                key={c.id}
                onClick={() => navigate(`/clients/${c.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    navigate(`/clients/${c.id}`);
                  }
                }}
                role="button"
                tabIndex={0}
                className="cursor-pointer transition-colors hover:bg-[var(--hover)]"
              >
                <td className="td font-medium">{c.name}</td>
                <td className="td">{c.npwp ?? "-"}</td>
                <td className="td">{c.pic_name ?? "-"}</td>
                <td className="td">{c.job_count}</td>
                <td className="td">{c.contract_end ?? "-"}</td>
                <td className="td">
                  <span className={`pill ${c.status === "aktif" ? "p-green" : "p-gray"}`}>
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
            {filteredClients.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  {clients?.length === 0 ? "Belum ada klien." : "Tidak ada klien untuk status ini."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
