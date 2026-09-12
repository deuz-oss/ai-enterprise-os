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

  return (
    <Shell>
      <div className="card flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {data.client_name} &middot; Rekap kehadiran &amp; lembur karyawan
        </p>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            max={12}
            value={period.month}
            onChange={(e) => setPeriod({ ...period, month: Number(e.target.value) })}
            className="input w-20"
            aria-label="Bulan"
          />
          <input
            type="number"
            value={period.year}
            onChange={(e) => setPeriod({ ...period, year: Number(e.target.value) })}
            className="input w-24"
            aria-label="Tahun"
          />
        </div>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead style={{ backgroundColor: "var(--hover)" }}>
            <tr>
              <th className="th">Nomor Induk</th>
              <th className="th">Karyawan</th>
              <th className="th">Hari Hadir</th>
              <th className="th">Jam Lembur</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {data.rows.map((r) => (
              <tr key={r.employee_no}>
                <td className="td">{r.employee_no}</td>
                <td className="td font-medium">{r.employee_name}</td>
                <td className="td">{r.present_days}</td>
                <td className="td">{r.overtime_hours} jam</td>
                <td className="td">
                  <span className={`badge pill ${r.client_approved ? "p-green" : "p-yellow"}`}>
                    {r.client_approved ? "disetujui" : "menunggu"}
                  </span>
                </td>
              </tr>
            ))}
            {data.rows.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada rekap kehadiran untuk periode ini.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
