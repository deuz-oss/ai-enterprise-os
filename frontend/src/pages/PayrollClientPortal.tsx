import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, formatRupiah, ApiError } from "../api/client";

/** Halaman publik approval payroll klien -- TANPA Layout/sidebar, tanpa
 * login, diakses via link ber-token yang dibagikan dari Payroll.tsx
 * ("submitToClient"). Sebelumnya link ini 404 karena route belum ada
 * sama sekali, walau backend (GET/POST /payroll/client/{token}) sudah jadi. */

interface PayrollLine {
  employee_name: string;
  base_salary: number;
  allowance: number;
  overtime_amount: number;
  deductions: number;
  gross: number;
  tax_pph21: number;
  net_pay: number;
}

interface ClientViewData {
  client: string | null;
  year: number;
  month: number;
  status: string;
  expires_at: string;
  decided: boolean;
  decided_by_name: string | null;
  decision_note: string | null;
  lines: PayrollLine[];
  total_net_pay: number;
  total_gross: number;
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--n-bg)] px-4 py-10">
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-[var(--n-text)]">Persetujuan Payroll</h1>
        {children}
      </div>
    </div>
  );
}

export default function PayrollClientPortal() {
  const { token } = useParams<{ token: string }>();
  const [name, setName] = useState("");
  const [note, setNote] = useState("");

  const view = useQuery({
    queryKey: ["payroll-client-view", token],
    queryFn: () => api.get<ClientViewData>(`/payroll/client/${token}`),
    retry: false,
  });

  // Sengaja TIDAK invalidate/refetch `view` setelah sukses -- backend
  // (`_find_token`) menolak GET dengan 409 begitu token sudah punya
  // keputusan, jadi refetch di sini cuma akan menukar tampilan sukses
  // dengan pesan error. State sukses murni lokal dari respons POST.
  const decide = useMutation({
    mutationFn: (approved: boolean) =>
      api.post<{ status: string; decided_by_name: string; decision_note: string | null }>(
        `/payroll/client/${token}/decision`,
        { approved, name, note: note || undefined }
      ),
  });

  if (view.isLoading) {
    return (
      <Shell>
        <p className="text-sm text-[var(--n-text-muted)]">Memuat...</p>
      </Shell>
    );
  }

  if (view.error) {
    const status = view.error instanceof ApiError ? view.error.status : 0;
    const msg =
      status === 410
        ? "Link approval ini sudah kedaluwarsa."
        : status === 409
          ? "Keputusan untuk payroll ini sudah pernah direkam sebelumnya."
          : status === 404
            ? "Link approval tidak valid."
            : (view.error as Error).message;
    return (
      <Shell>
        <div className="card">
          <p className="text-sm" style={{ color: "var(--n-text-muted)" }}>{msg}</p>
        </div>
      </Shell>
    );
  }

  const data = view.data!;

  return (
    <Shell>
      <div className="card space-y-1">
        <p className="text-sm" style={{ color: "var(--n-text-muted)" }}>
          {data.client ?? "Klien"} &middot; Periode {data.month}/{data.year}
        </p>
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          Berlaku s.d. {new Date(data.expires_at).toLocaleString("id-ID")}
        </p>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead style={{ backgroundColor: "var(--n-hover)" }}>
            <tr>
              <th className="th">Karyawan</th>
              <th className="th">Gaji Pokok</th>
              <th className="th">Tunjangan</th>
              <th className="th">Lembur</th>
              <th className="th">Potongan</th>
              <th className="th">PPh 21</th>
              <th className="th">Netto</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {data.lines.map((l, i) => (
              <tr key={i}>
                <td className="td font-medium">{l.employee_name}</td>
                <td className="td">{formatRupiah(l.base_salary)}</td>
                <td className="td">{formatRupiah(l.allowance)}</td>
                <td className="td">{formatRupiah(l.overtime_amount)}</td>
                <td className="td">{formatRupiah(l.deductions)}</td>
                <td className="td">{formatRupiah(l.tax_pph21)}</td>
                <td className="td font-medium">{formatRupiah(l.net_pay)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ borderTop: "1px solid var(--n-border)" }}>
              <td className="td font-semibold" colSpan={5}>
                Total
              </td>
              <td className="td" />
              <td className="td font-semibold">{formatRupiah(data.total_net_pay)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {decide.isSuccess ? (
        <div className="card border-emerald-600">
          <p className="pill p-green">Keputusan tersimpan</p>
          <p className="mt-2 text-sm" style={{ color: "var(--n-text)" }}>
            {decide.data.status} -- oleh {decide.data.decided_by_name}
            {decide.data.decision_note && ` -- ${decide.data.decision_note}`}
          </p>
        </div>
      ) : data.decided ? (
        <div className="card">
          <p className="pill p-green">Sudah diputuskan</p>
          <p className="mt-2 text-sm" style={{ color: "var(--n-text)" }}>
            Oleh {data.decided_by_name}
            {data.decision_note && ` -- ${data.decision_note}`}
          </p>
        </div>
      ) : (
        <div className="card space-y-3">
          <h3 className="font-semibold" style={{ color: "var(--n-text)" }}>
            Keputusan Anda
          </h3>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nama Anda *"
            className="input w-full"
          />
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Catatan (opsional)"
            className="input w-full"
            rows={2}
          />
          {decide.error && <p className="text-sm text-red-600">{(decide.error as Error).message}</p>}
          <div className="flex gap-2">
            <button
              className="btn flex-1"
              disabled={!name || decide.isPending}
              onClick={() => decide.mutate(true)}
            >
              Setujui
            </button>
            <button
              className="btn-secondary flex-1"
              disabled={!name || decide.isPending}
              onClick={() => decide.mutate(false)}
            >
              Tolak
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
}
