import { type Column, DataTable, PeriodPicker } from "../components/ui";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";

/** Halaman publik monitoring kehadiran & lembur untuk klien -- TANPA
 * Layout/sidebar, tanpa login, diakses via link ber-token yang dibagikan
 * dari Clients.tsx ("Portal Klien"). Read-only murni (keputusan scope) --
 * approval kehadiran/lembur tetap jalur internal HR/Ops seperti sebelumnya,
 * portal ini cuma jendela monitoring. */

interface AttendanceRow {
  employee_name: string;
  employee_no: string;
  present_days: number;
  overtime_hours: number;
  client_approved: boolean;
}

interface ClientPortalData {
  client_name: string;
  year: number;
  month: number;
  rows: AttendanceRow[];
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-10">
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Portal Klien</h1>
        {children}
      </div>
    </main>
  );
}

export default function ClientPortal() {
  const { token } = useParams<{ token: string }>();
  const today = new Date();
  const [period, setPeriod] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });

  const view = useQuery({
    queryKey: ["client-portal-view", token, period],
    queryFn: () =>
      api.get<ClientPortalData>(
        `/clients/portal/${token}?year=${period.year}&month=${period.month}`
      ),
    retry: false,
  });

  if (view.isLoading) {
    return (
      <Shell>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>
      </Shell>
    );
  }

  if (view.error) {
    const status = view.error instanceof ApiError ? view.error.status : 0;
    const msg =
      status === 429
        ? "Terlalu banyak percobaan dari lokasi ini. Coba lagi nanti."
        : status === 404
          ? "Link portal tidak valid."
          : (view.error as Error).message;
    return (
      <Shell>
        <div className="card">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>{msg}</p>
        </div>
      </Shell>
    );
  }

  const data = view.data!;

  const attendanceColumns: Column<AttendanceRow>[] = [
    { key: "no", header: "Nomor Induk", className: "font-mono text-xs", cell: (r) => r.employee_no, sortValue: (r) => r.employee_no },
    { key: "name", header: "Karyawan", className: "font-medium", cell: (r) => r.employee_name, sortValue: (r) => r.employee_name },
    { key: "present", header: "Hari Hadir", numeric: true, cell: (r) => r.present_days, sortValue: (r) => r.present_days },
    { key: "overtime", header: "Jam Lembur", numeric: true, cell: (r) => `${r.overtime_hours} jam`, sortValue: (r) => r.overtime_hours },
    {
      key: "status",
      header: "Status",
      sortValue: (r) => (r.client_approved ? 1 : 0),
      cell: (r) => (
        <span className={`badge pill ${r.client_approved ? "p-green" : "p-yellow"}`}>
          {r.client_approved ? "disetujui" : "menunggu"}
        </span>
      ),
    },
  ];

  return (
    <Shell>
      <div className="card flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {data.client_name} &middot; Rekap kehadiran &amp; lembur karyawan
        </p>
        <div className="flex items-center gap-2">
          <PeriodPicker value={period} onChange={setPeriod} label="periode laporan" />
        </div>
      </div>

      <DataTable
        label="Rekap kehadiran karyawan"
        rows={data.rows}
        columns={attendanceColumns}
        rowKey={(r) => r.employee_no}
        defaultSort={{ key: "name", dir: "asc" }}
        emptyTitle="Belum ada rekap kehadiran untuk periode ini."
      />
    </Shell>
  );
}
