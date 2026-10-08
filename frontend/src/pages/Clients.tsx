import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, CalendarClock, UserX } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { DataTable, KpiCard, PillTabs, type Column, type PillTab } from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatDate } from "../api/client";

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
  const [search, setSearch] = useState("");

  const clientsQuery = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const clients = clientsQuery.data;

  const filteredClients = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (clients ?? []).filter(
      (c) =>
        (statusTab === "semua" || c.status === statusTab) &&
        (!q || [c.name, c.pic_name, c.npwp].some((v) => v?.toLowerCase().includes(q)))
    );
  }, [clients, statusTab, search]);
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

  const columns: Column<ClientRow>[] = [
    {
      key: "name",
      header: "Perusahaan",
      cell: (c) => <span className="font-medium">{c.name}</span>,
      sortValue: (c) => c.name,
    },
    { key: "npwp", header: "NPWP", cell: (c) => c.npwp ?? "-" },
    { key: "pic", header: "PIC", cell: (c) => c.pic_name ?? "-", sortValue: (c) => c.pic_name },
    { key: "jobs", header: "Jobs", numeric: true, cell: (c) => c.job_count, sortValue: (c) => c.job_count },
    {
      key: "contract_end",
      header: "Akhir Kontrak",
      cell: (c) => <span className="whitespace-nowrap">{formatDate(c.contract_end)}</span>,
      sortValue: (c) => c.contract_end,
    },
    {
      key: "status",
      header: "Status",
      cell: (c) => <span className={`pill ${c.status === "aktif" ? "p-green" : "p-gray"}`}>{c.status}</span>,
      sortValue: (c) => c.status,
    },
  ];

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
        // Label terlihat di atas field (dulu placeholder saja -- hilang saat
        // mengetik, dan placeholder input tanggal tidak pernah tampil).
        <form onSubmit={handleCreate} className="card grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(
            [
              ["name", "Nama perusahaan", "text", true],
              ["npwp", "NPWP", "text", false],
              ["pic_name", "Nama PIC", "text", false],
              ["pic_phone", "Telepon PIC", "tel", false],
              ["contract_end", "Akhir kontrak", "date", false],
            ] as const
          ).map(([name, label, type, required]) => (
            <label key={name} className="space-y-1 text-sm" style={{ color: "var(--text)" }}>
              <span className="font-medium">
                {label}
                {required && <span className="text-red-700 dark:text-red-400"> *</span>}
              </span>
              <input name={name} type={type} required={required} className="input" />
            </label>
          ))}
          {createClient.isError && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-400 sm:col-span-3">
              Gagal menyimpan klien: {(createClient.error as Error).message}
            </p>
          )}
          <button type="submit" disabled={createClient.isPending} className="btn sm:col-span-3">
            {createClient.isPending ? "Menyimpan…" : "Simpan Klien"}
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

      <div className="flex flex-wrap items-center gap-3">
        <PillTabs tabs={statusTabs} value={statusTab} onChange={setStatusTab} />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari perusahaan, PIC, atau NPWP…"
          aria-label="Cari klien"
          className="input w-full sm:ml-auto sm:w-72"
        />
      </div>

      <DataTable
        label="Daftar klien"
        rows={filteredClients}
        columns={columns}
        rowKey={(c) => c.id}
        query={clientsQuery}
        onRowClick={(c) => navigate(`/clients/${c.id}`)}
        defaultSort={{ key: "name", dir: "asc" }}
        pageSize={50}
        emptyTitle={
          clients?.length === 0
            ? "Belum ada klien."
            : search
              ? "Tidak ada klien yang cocok dengan pencarian."
              : "Tidak ada klien untuk status ini."
        }
        emptyDescription={clients?.length === 0 ? "Tambahkan klien pertama lewat tombol + Klien Baru." : undefined}
      />
    </div>
  );
}
