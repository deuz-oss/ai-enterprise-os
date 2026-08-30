import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { UserCircle } from "lucide-react";
import { PageHeader } from "../components/notion";

const MONTHS = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember",
];

interface Profile {
  id: string;
  employee_no: string;
  full_name: string;
  ktp_no: string | null;
  npwp_no: string | null;
  bpjs_kesehatan_no: string | null;
  bpjs_ketenagakerjaan_no: string | null;
  phone: string | null;
  address: string | null;
  bank_name: string | null;
  bank_account: string | null;
  join_date: string | null;
  marital_status: string | null;
  dependents: number;
  status: string;
}

interface ContractRow {
  id: string;
  contract_no: string;
  start_date: string | null;
  end_date: string | null;
  sign_status: string;
  file_name: string | null;
}

interface DocumentRow {
  id: string;
  document_type: string;
  title: string;
  version: number;
  file_name: string;
  uploaded_at: string;
}

interface PayslipRow {
  id: string;
  year: number;
  month: number;
  base_salary: number;
  allowance: number;
  overtime_hours: number;
  overtime_amount: number;
  deductions: number;
  gross: number;
  pph21_method: string;
  tax_pph21: number;
  net_pay: number;
}

interface AttendanceRow {
  id: string;
  year: number;
  month: number;
  present_days: number;
  overtime_hours: number;
  client_approved: boolean;
  notes: string | null;
}

const LEAVE_TYPES = [
  { value: "cuti_tahunan", label: "Cuti Tahunan" },
  { value: "izin", label: "Izin" },
  { value: "sakit", label: "Sakit" },
  { value: "cuti_tak_berbayar", label: "Cuti Tak Berbayar" },
];

const LEAVE_STATUS_BADGES: Record<string, string> = {
  menunggu: "pill p-yellow",
  disetujui: "pill p-green",
  ditolak: "pill p-red",
  dibatalkan: "pill p-gray",
};

interface LeaveRow {
  id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: string;
  decision_note: string | null;
  file_name: string | null;
  file_size: number;
}

interface LeaveBalanceRow {
  year: number;
  total_days: number;
  used_days: number;
  remaining: number;
}

interface AppNotification {
  id: string;
  title: string;
  body: string | null;
  read_at: string | null;
  created_at: string;
}

interface AttendanceCorrectionRow {
  id: string;
  year: number;
  month: number;
  requested_present_days: number;
  requested_overtime_hours: number;
  reason: string | null;
  status: string;
  decision_note: string | null;
}

async function openDownload(path: string) {
  const { url } = await api.get<{ url: string }>(path);
  window.open(url, "_blank");
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide" style={{ color: "var(--n-text-muted)" }}>{label}</dt>
      <dd className="mt-0.5 text-sm" style={{ color: "var(--n-text)" }}>{value}</dd>
    </div>
  );
}

export default function MyPortal() {
  const qc = useQueryClient();
  const today = new Date();
  const [attPeriod, setAttPeriod] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });
  const [passwordMsg, setPasswordMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const { data: profile, error, isLoading } = useQuery({
    queryKey: ["me-profile"],
    queryFn: () => api.get<Profile>("/me/profile"),
    retry: false,
  });
  const { data: contracts } = useQuery({
    queryKey: ["me-contracts"],
    queryFn: () => api.get<ContractRow[]>("/me/contracts"),
  });
  const { data: documents } = useQuery({
    queryKey: ["me-documents"],
    queryFn: () => api.get<DocumentRow[]>("/me/documents"),
  });
  const { data: payslips } = useQuery({
    queryKey: ["me-payslips"],
    queryFn: () => api.get<PayslipRow[]>("/me/payslips"),
  });
  const { data: attendance } = useQuery({
    queryKey: ["me-attendance", attPeriod],
    queryFn: () =>
      api.get<AttendanceRow[]>(`/me/attendance?year=${attPeriod.year}&month=${attPeriod.month}`),
  });
  const { data: leaves } = useQuery({
    queryKey: ["me-leaves"],
    queryFn: () => api.get<LeaveRow[]>("/me/leave-requests"),
  });
  const { data: leaveBalance } = useQuery({
    queryKey: ["me-leave-balance", today.getFullYear()],
    queryFn: () =>
      api.get<LeaveBalanceRow | null>("/me/leave-balance"),
  });
  const { data: notifications } = useQuery({
    queryKey: ["me-notifications"],
    queryFn: () => api.get<AppNotification[]>("/me/notifications"),
  });
  const { data: corrections } = useQuery({
    queryKey: ["me-corrections"],
    queryFn: () => api.get<AttendanceCorrectionRow[]>("/me/attendance-corrections"),
  });

  const invalidateCorrections = () => {
    qc.invalidateQueries({ queryKey: ["me-corrections"] });
    qc.invalidateQueries({ queryKey: ["me-attendance"] });
  };

  const createCorrection = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post("/me/attendance-corrections", body),
    onSuccess: invalidateCorrections,
  });
  const cancelCorrection = useMutation({
    mutationFn: (id: string) => api.post(`/me/attendance-corrections/${id}/cancel`, {}),
    onSuccess: invalidateCorrections,
  });

  const markNotification = useMutation({
    mutationFn: (id: string) => api.post(`/me/notifications/${id}/read`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me-notifications"] }),
  });
  const markAllNotifications = useMutation({
    mutationFn: () => api.post<{ marked: number }>("/me/notifications/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me-notifications"] }),
  });

  const invalidateLeaves = () => {
    qc.invalidateQueries({ queryKey: ["me-leaves"] });
    qc.invalidateQueries({ queryKey: ["me-attendance"] });
  };

  const submitLeave = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/me/leave-requests", body),
    onSuccess: invalidateLeaves,
  });
  const cancelLeave = useMutation({
    mutationFn: (id: string) => api.post(`/me/leave-requests/${id}/cancel`, {}),
    onSuccess: invalidateLeaves,
  });
  const uploadAttachment = useMutation({
    mutationFn: ({ id, formData }: { id: string; formData: FormData }) =>
      api.upload(`/me/leave-requests/${id}/attachment`, formData),
    onSuccess: invalidateLeaves,
  });
  const changePassword = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post("/auth/change-password", body),
    onSuccess: () =>
      setPasswordMsg({ ok: true, text: "Password berhasil diganti." }),
    onError: (err) =>
      setPasswordMsg({ ok: false, text: err instanceof Error ? err.message : "Gagal" }),
  });

  if (isLoading) return <p style={{ color: "var(--n-text-muted)" }}>Memuat portal...</p>;
  if (error || !profile) {
    return (
      <div className="card">
        <h1 className="text-xl font-bold" style={{ color: "var(--n-text)" }}>Portal Saya</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--n-text-muted)" }}>
          Akun ini belum tertaut ke data karyawan. Silakan hubungi HR untuk
          mengaktifkan portal Anda.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader icon={UserCircle} title="Portal Saya" />

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Data Pribadi</h2>
          <span className="badge pill p-green">{profile.status}</span>
        </div>
        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Nomor Induk" value={profile.employee_no} />
          <Field label="Nama Lengkap" value={profile.full_name} />
          <Field
            label="Tanggal Masuk"
            value={profile.join_date ?? "-"}
          />
          <Field label="Telepon" value={profile.phone ?? "-"} />
          <Field label="Alamat" value={profile.address ?? "-"} />
          <Field
            label="Status Perkawinan"
            value={profile.marital_status ? `${profile.marital_status} · ${profile.dependents} tanggungan` : "-"}
          />
          <Field label="No. KTP" value={profile.ktp_no ?? "-"} />
          <Field label="No. NPWP" value={profile.npwp_no ?? "-"} />
          <Field label="Rekening Gaji" value={profile.bank_name ? `${profile.bank_name} · ${profile.bank_account ?? "-"}` : "-"} />
          <Field label="BPJS Kesehatan" value={profile.bpjs_kesehatan_no ?? "-"} />
          <Field label="BPJS Ketenagakerjaan" value={profile.bpjs_ketenagakerjaan_no ?? "-"} />
        </dl>
      </div>

      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--n-border)" }}>
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Kontrak Kerja</h2>
        </div>
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">Nomor Kontrak</th>
              <th className="th">Periode</th>
              <th className="th">Status TTD</th>
              <th className="th">File</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(contracts ?? []).map((c) => (
              <tr key={c.id}>
                <td className="td font-medium">{c.contract_no}</td>
                <td className="td">
                  {c.start_date ?? "-"} s.d. {c.end_date ?? "-"}
                </td>
                <td className="td">{c.sign_status}</td>
                <td className="td">
                  {c.file_name ? (
                    <button
                      onClick={() => openDownload(`/me/contracts/${c.id}/download-url`)}
                      className="text-sm font-medium hover:opacity-80"
                      style={{ color: "var(--accent)" }}
                    >
                      Unduh
                    </button>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}
            {contracts?.length === 0 && (
              <tr>
                <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada kontrak kerja.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--n-border)" }}>
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Dokumen Saya</h2>
        </div>
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">Judul</th>
              <th className="th">Jenis</th>
              <th className="th">Versi</th>
              <th className="th">Diunggah</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(documents ?? []).map((d) => (
              <tr key={d.id}>
                <td className="td font-medium">{d.title}</td>
                <td className="td">{d.document_type}</td>
                <td className="td">v{d.version}</td>
                <td className="td">{new Date(d.uploaded_at).toLocaleDateString("id-ID")}</td>
                <td className="td">
                  <button
                    onClick={() => openDownload(`/me/documents/${d.id}/download-url`)}
                    className="text-sm font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                  >
                    Unduh
                  </button>
                </td>
              </tr>
            ))}
            {documents?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada dokumen.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--n-border)" }}>
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Riwayat Slip Gaji</h2>
        </div>
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)", borderBottom: "1px solid var(--n-border)" }}>
            <tr>
              <th className="th">Periode</th>
              <th className="th">Gaji Pokok</th>
              <th className="th">Tunjangan</th>
              <th className="th">Lembur</th>
              <th className="th">Bruto</th>
              <th className="th">PPh21</th>
              <th className="th">Potongan</th>
              <th className="th">Diterima</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(payslips ?? []).map((s) => (
              <tr key={s.id}>
                <td className="td font-medium">
                  {MONTHS[s.month - 1]} {s.year}
                </td>
                <td className="td">{formatRupiah(Number(s.base_salary))}</td>
                <td className="td">{formatRupiah(Number(s.allowance))}</td>
                <td className="td">
                  {s.overtime_hours > 0
                    ? `${s.overtime_hours} jam · ${formatRupiah(Number(s.overtime_amount))}`
                    : "-"}
                </td>
                <td className="td">{formatRupiah(Number(s.gross))}</td>
                <td className="td text-rose-600">-{formatRupiah(Number(s.tax_pph21))}</td>
                <td className="td text-rose-600">-{formatRupiah(Number(s.deductions))}</td>
                <td className="td font-semibold text-emerald-700">
                  {formatRupiah(Number(s.net_pay))}
                </td>
              </tr>
            ))}
            {payslips?.length === 0 && (
              <tr>
                <td colSpan={8} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada slip gaji yang difinalisasi.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Rekap Kehadiran</h2>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              max={12}
              value={attPeriod.month}
              onChange={(e) =>
                setAttPeriod({ ...attPeriod, month: Number(e.target.value) })
              }
              className="input w-20"
            />
            <input
              type="number"
              value={attPeriod.year}
              onChange={(e) =>
                setAttPeriod({ ...attPeriod, year: Number(e.target.value) })
              }
              className="input w-24"
            />
          </div>
        </div>
        {(attendance ?? []).map((a) => (
          <div key={a.id} className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Field label="Hari Hadir" value={String(a.present_days)} />
            <Field label="Jam Lembur" value={`${a.overtime_hours} jam`} />
            <Field
              label="Approval Klien"
              value={a.client_approved ? "disetujui" : "menunggu"}
            />
            <Field label="Catatan" value={a.notes ?? "-"} />
          </div>
        ))}
        {attendance?.length === 0 && (
          <p className="mt-3 text-sm" style={{ color: "var(--n-text-muted)" }}>
            Belum ada rekap kehadiran untuk periode ini.
          </p>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Koreksi Absensi</h2>
        <form
          className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[auto_auto_auto_1fr_auto]"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            createCorrection.mutate({
              year: Number(form.get("year")),
              month: Number(form.get("month")),
              requested_present_days: Number(form.get("present_days") || 0),
              requested_overtime_hours: Number(form.get("overtime_hours") || 0),
              reason: form.get("reason") || null,
            });
            e.currentTarget.reset();
          }}
        >
          <input
            name="month"
            type="number"
            min={1}
            max={12}
            required
            placeholder="Bulan"
            defaultValue={attPeriod.month}
            className="input w-24"
          />
          <input
            name="year"
            type="number"
            required
            placeholder="Tahun"
            defaultValue={attPeriod.year}
            className="input w-24"
          />
          <div className="flex gap-2">
            <input
              name="present_days"
              type="number"
              min={0}
              placeholder="Hari hadir"
              className="input w-28"
            />
            <input
              name="overtime_hours"
              type="number"
              min={0}
              placeholder="Jam lembur"
              className="input w-28"
            />
          </div>
          <input name="reason" placeholder="Alasan koreksi" className="input" />
          <button disabled={createCorrection.isPending} className="btn">
            Ajukan
          </button>
        </form>
        {createCorrection.error && (
          <p className="mt-2 text-sm text-red-600">
            {(createCorrection.error as Error).message}
          </p>
        )}
        <table className="mt-3 w-full">
          <thead>
            <tr>
              <th className="th">Periode</th>
              <th className="th">Usulan</th>
              <th className="th">Status</th>
              <th className="th">Catatan HR</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(corrections ?? []).map((c) => (
              <tr key={c.id}>
                <td className="td font-medium">
                  {String(c.month).padStart(2, "0")}/{c.year}
                </td>
                <td className="td">
                  {c.requested_present_days} hari hadir · {c.requested_overtime_hours} jam lembur
                  {c.reason ? ` · ${c.reason}` : ""}
                </td>
                <td className="td">
                  <span className={`badge ${LEAVE_STATUS_BADGES[c.status] ?? ""}`}>
                    {c.status}
                  </span>
                </td>
                <td className="td">{c.decision_note ?? "-"}</td>
                <td className="td">
                  {c.status === "menunggu" && (
                    <button
                      onClick={() => cancelCorrection.mutate(c.id)}
                      className="text-sm font-medium text-rose-600 hover:text-rose-800"
                    >
                      Batalkan
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {corrections?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-6 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada pengajuan koreksi absensi.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>
            Sisa Cuti Tahunan {today.getFullYear()}
          </h2>
          {leaveBalance && (
            <span className="badge pill p-indigo">
              sisa {leaveBalance.remaining} hari
            </span>
          )}
        </div>
        {leaveBalance ? (
          <div className="mt-3 grid grid-cols-3 gap-4">
            <Field label="Total Jatah" value={`${leaveBalance.total_days} hari`} />
            <Field label="Terpakai" value={`${leaveBalance.used_days} hari`} />
            <Field label="Sisa" value={`${leaveBalance.remaining} hari`} />
          </div>
        ) : (
          <p className="mt-3 text-sm" style={{ color: "var(--n-text-muted)" }}>
            Jatah cuti belum diatur HR — pengajuan cuti tahunan masih bisa
            diajukan tanpa batas kuota.
          </p>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Ajukan Cuti / Izin</h2>
        <form
          className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[auto_1fr_1fr_1fr_auto]"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            submitLeave.mutate({
              leave_type: form.get("leave_type"),
              start_date: form.get("start_date"),
              end_date: form.get("end_date"),
              reason: form.get("reason") || null,
            });
            e.currentTarget.reset();
          }}
        >
          <select name="leave_type" className="input w-auto" defaultValue="cuti_tahunan">
            {LEAVE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <input name="start_date" type="date" required className="input" />
          <input name="end_date" type="date" required className="input" />
          <input name="reason" placeholder="Alasan (opsional)" className="input" />
          <button disabled={submitLeave.isPending} className="btn">
            Ajukan
          </button>
        </form>
        {submitLeave.error && (
          <p className="mt-2 text-sm text-red-600">{(submitLeave.error as Error).message}</p>
        )}
        <table className="mt-3 w-full">
          <thead>
            <tr>
              <th className="th">Jenis</th>
              <th className="th">Tanggal</th>
              <th className="th">Status</th>
              <th className="th">Catatan HR</th>
              <th className="th">Lampiran</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(leaves ?? []).map((lv) => (
              <tr key={lv.id}>
                <td className="td">
                  {LEAVE_TYPES.find((t) => t.value === lv.leave_type)?.label ?? lv.leave_type}
                </td>
                <td className="td">
                  {lv.start_date} s.d. {lv.end_date}
                  {lv.reason ? ` · ${lv.reason}` : ""}
                </td>
                <td className="td">
                  <span className={`badge ${LEAVE_STATUS_BADGES[lv.status] ?? ""}`}>
                    {lv.status}
                  </span>
                </td>
                <td className="td">{lv.decision_note ?? "-"}</td>
                <td className="td whitespace-nowrap">
                  {lv.file_name ? (
                    <button
                      onClick={() => openDownload(`/me/leave-requests/${lv.id}/attachment/download-url`)}
                      className="text-sm font-medium hover:opacity-80"
                      style={{ color: "var(--accent)" }}
                    >
                      Lampiran ({(lv.file_size / 1024).toFixed(0)} KB)
                    </button>
                  ) : lv.status === "menunggu" ? (
                    <label className="cursor-pointer text-sm font-medium hover:opacity-80" style={{ color: "var(--accent)" }}>
                      + Lampirkan
                      <input
                        type="file"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          const fd = new FormData();
                          fd.append("file", file);
                          uploadAttachment.mutate({ id: lv.id, formData: fd });
                          e.target.value = "";
                        }}
                      />
                    </label>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="td">
                  {lv.status === "menunggu" && (
                    <button
                      onClick={() => cancelLeave.mutate(lv.id)}
                      className="text-sm font-medium text-rose-600 hover:text-rose-800"
                    >
                      Batalkan
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {leaves?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-6 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada pengajuan cuti/izin.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Notifikasi</h2>
          {(notifications ?? []).some((n) => !n.read_at) && (
            <button
              onClick={() => markAllNotifications.mutate()}
              disabled={markAllNotifications.isPending}
              className="btn-secondary text-xs"
            >
              Tandai semua dibaca
            </button>
          )}
        </div>
        <ul className="mt-3 space-y-2">
          {(notifications ?? []).map((n) => (
            <li
              key={n.id}
              className="rounded-lg p-3 text-sm"
              style={{ backgroundColor: n.read_at ? "var(--n-hover)" : "var(--accent-tint)" }}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium" style={{ color: n.read_at ? "var(--n-text-muted)" : "var(--n-text)" }}>
                    {n.title}
                  </p>
                  {n.body && <p className="mt-0.5 text-xs" style={{ color: "var(--n-text-muted)" }}>{n.body}</p>}
                  <p className="mt-1 text-[11px]" style={{ color: "var(--n-text-muted)" }}>
                    {new Date(n.created_at).toLocaleString("id-ID")}
                  </p>
                </div>
                {!n.read_at && (
                  <button
                    onClick={() => markNotification.mutate(n.id)}
                    className="shrink-0 text-xs font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                  >
                    Tandai dibaca
                  </button>
                )}
              </div>
            </li>
          ))}
          {notifications?.length === 0 && (
            <li className="text-sm" style={{ color: "var(--n-text-muted)" }}>Belum ada notifikasi.</li>
          )}
        </ul>
      </div>

      <div className="card max-w-xl">
        <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>Ganti Password</h2>
        <form
          className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            changePassword.mutate({
              old_password: form.get("old_password"),
              new_password: form.get("new_password"),
            });
            e.currentTarget.reset();
          }}
        >
          <input
            name="old_password"
            type="password"
            required
            placeholder="Password lama"
            className="input"
          />
          <input
            name="new_password"
            type="password"
            required
            minLength={8}
            placeholder="Password baru (min. 8 karakter)"
            className="input"
          />
          <button disabled={changePassword.isPending} className="btn sm:col-span-2">
            Simpan Password Baru
          </button>
        </form>
        {passwordMsg && (
          <p
            className={`mt-2 text-sm ${
              passwordMsg.ok ? "text-emerald-600" : "text-red-600"
            }`}
          >
            {passwordMsg.text}
          </p>
        )}
      </div>
    </div>
  );
}
