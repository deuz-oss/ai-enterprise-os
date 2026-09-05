import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gift } from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { PageHeader } from "../components/workspace";

/** Program referral karyawan (Fase 27) — jalur sourcing ketiga di samping
 * Job Portal (Fase 16) dan Talent Pool. Halaman baru berdiri sendiri,
 * mengikuti pola Rates.tsx: PageHeader + form pengaturan sederhana + tabel,
 * tanpa tab (cakupannya kecil, cuma satu pengaturan + satu daftar). */

interface ReferralSetting {
  id: string;
  is_enabled: boolean;
  reward_amount: number;
}

interface ReferralReward {
  id: string;
  employee_id: string;
  candidate_id: string;
  placement_id: string | null;
  amount: number;
  eligible_at: string | null;
  status: "pending" | "eligible" | "paid" | "cancelled";
  is_eligible: boolean;
  paid_at: string | null;
  created_at: string;
}

interface EmployeeRow {
  id: string;
  full_name: string;
}

interface CandidateRow {
  id: string;
  full_name: string;
}

const STATUS_BADGE: Record<string, string> = {
  pending: "pill p-gray",
  eligible: "pill p-yellow",
  paid: "pill p-green",
  cancelled: "pill p-red",
};

export default function Referral() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const { data: setting } = useQuery({
    queryKey: ["referral-setting"],
    queryFn: () => api.get<ReferralSetting>("/recruitment/referral-setting"),
  });
  const { data: rewards } = useQuery({
    queryKey: ["referral-rewards"],
    queryFn: () => api.get<ReferralReward[]>("/recruitment/referral-rewards"),
  });
  const { data: employees } = useQuery({
    queryKey: ["employees-lookup"],
    queryFn: () => api.get<EmployeeRow[]>("/employees?limit=1000"),
  });
  const { data: candidates } = useQuery({
    queryKey: ["candidates-lookup"],
    queryFn: () => api.get<CandidateRow[]>("/recruitment/candidates?limit=1000"),
  });

  const saveSetting = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.put("/recruitment/referral-setting", body),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["referral-setting"] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal menyimpan"),
  });

  const markPaid = useMutation({
    mutationFn: (id: string) => api.post(`/recruitment/referral-rewards/${id}/mark-paid`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["referral-rewards"] }),
  });

  function employeeName(id: string) {
    return employees?.find((e) => e.id === id)?.full_name ?? "-";
  }
  function candidateName(id: string) {
    return candidates?.find((c) => c.id === id)?.full_name ?? "-";
  }

  function handleSaveSetting(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    saveSetting.mutate({
      is_enabled: form.get("is_enabled") === "on",
      reward_amount: Number(form.get("reward_amount")) || 0,
    });
  }

  return (
    <div className="space-y-4">
      <PageHeader icon={Gift} title="Program Referral" />

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--text)" }}>Pengaturan Program</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Karyawan yang mereferensikan kandidat dapat kode referral otomatis
          (lihat halaman Karyawan). Reward cair otomatis 3 bulan setelah
          kandidat placement.
        </p>
        <form
          key={setting ? `${setting.is_enabled}-${setting.reward_amount}` : "loading"}
          onSubmit={handleSaveSetting}
          className="mt-3 flex flex-wrap items-center gap-3"
        >
          <label className="input flex items-center gap-2 text-sm w-auto">
            <input
              name="is_enabled"
              type="checkbox"
              defaultChecked={setting?.is_enabled ?? false}
              className="h-4 w-4"
            />
            Aktifkan program referral
          </label>
          <input
            name="reward_amount"
            type="number"
            min={0}
            defaultValue={setting?.reward_amount ?? 0}
            placeholder="Nominal reward (Rp)"
            className="input w-56"
          />
          <button disabled={saveSetting.isPending} className="btn">
            Simpan Pengaturan
          </button>
        </form>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Daftar Reward</h2>
        </div>
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
            <tr>
              <th className="th">Karyawan (referrer)</th>
              <th className="th">Kandidat</th>
              <th className="th">Jumlah</th>
              <th className="th">Eligible Sejak</th>
              <th className="th">Status</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(rewards ?? []).map((r) => (
              <tr key={r.id}>
                <td className="td font-medium">{employeeName(r.employee_id)}</td>
                <td className="td">{candidateName(r.candidate_id)}</td>
                <td className="td">{formatRupiah(r.amount)}</td>
                <td className="td">{r.eligible_at ?? "-"}</td>
                <td className="td">
                  <span className={`badge ${STATUS_BADGE[r.status] ?? "pill p-gray"}`}>
                    {r.status}
                  </span>
                  {r.is_eligible && r.status === "pending" && (
                    <span className="badge pill p-yellow ml-1">siap dibayar</span>
                  )}
                </td>
                <td className="td">
                  {(r.status === "pending" || r.status === "eligible") && (
                    <button
                      onClick={() => markPaid.mutate(r.id)}
                      disabled={markPaid.isPending}
                      className="btn-secondary text-xs"
                    >
                      Tandai Dibayar
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {rewards?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada reward referral.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
