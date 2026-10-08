import { type Column, DataTable, PeriodPicker } from "../components/ui";
import { FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatDate, formatDateTime, formatRupiah } from "../api/client";
import {
  ArrowLeft,
  Bell,
  CalendarClock,
  FileSignature,
  FileText,
  IdCard,
  KeyRound,
  type LucideIcon,
  Plane,
  Timer,
  UserCircle,
  Wallet,
} from "lucide-react";
import { PageHeader } from "../components/workspace";

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
  shift_start_time: string | null;
  shift_end_time: string | null;
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

interface TodayAttendance {
  id: string;
  date: string;
  status: string;
  clock_in: string | null;
  clock_out: string | null;
  clock_in_address: string | null;
  clock_out_address: string | null;
  has_clock_in_selfie: boolean;
  has_clock_out_selfie: boolean;
}

interface WeekDay {
  date: string;
  status: string | null;
  clock_in: string | null;
  clock_out: string | null;
}

const WEEKDAY_LABELS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

function weekDayDotColor(status: string | null): string {
  if (status === null) return "var(--border)";
  if (status === "hadir" || status === "terlambat" || status === "dinas_luar") return "#059669";
  if (status === "izin" || status === "sakit" || status === "cuti") return "#2563eb";
  if (status === "alpa") return "#dc2626";
  return "var(--text-muted)"; // libur
}

function mondayOf(d: Date): Date {
  const copy = new Date(d);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function toDateParam(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
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

interface OvertimeRequestRow {
  id: string;
  date: string;
  requested_hours: number;
  reason: string | null;
  status: string;
  decision_note: string | null;
}

async function openDownload(path: string) {
  const { url } = await api.get<{ url: string }>(path);
  window.open(url, "_blank");
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

/** Kamera live in-page untuk selfie absensi -- ganti `<input capture>` yang
 * melempar ke app kamera bawaan HP (izinnya level OS untuk aplikasi
 * browser, bukan per-website, tidak bisa di-"ask" dari kode web).
 * `getUserMedia` di sini adalah izin PER-WEBSITE sungguhan, diminta lebih
 * dulu saat halaman dibuka (lihat efek priming di komponen utama) supaya
 * modal ini biasanya langsung dapat stream tanpa prompt lagi. */
function SelfieCameraModal({
  onCapture,
  onCancel,
}: {
  onCapture: (blob: Blob) => void;
  onCancel: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user" } })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch(() => {
        setError("Tidak bisa mengakses kamera -- pastikan izin kamera untuk situs ini diaktifkan.");
      });
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function handleShutter() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    // Sampling data mentah video (bukan elemen DOM ter-mirror) -- hasil
    // jepretan TIDAK terbalik walau preview-nya di-mirror buat kesan natural.
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob((blob) => blob && onCapture(blob), "image/jpeg", 0.85);
  }

  return (
    <div className="fixed inset-0 z-40 flex flex-col items-center justify-center gap-4 bg-black/80 p-4">
      {error ? (
        <>
          <p className="max-w-xs text-center text-sm text-white">{error}</p>
          <button onClick={onCancel} className="btn-secondary">Tutup</button>
        </>
      ) : (
        <>
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="max-h-[70vh] w-full max-w-md rounded-lg"
            style={{ transform: "scaleX(-1)" }}
          />
          <div className="flex gap-3">
            <button onClick={onCancel} className="btn-secondary">Batal</button>
            <button onClick={handleShutter} className="btn">Jepret</button>
          </div>
        </>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{label}</dt>
      <dd className="mt-0.5 text-sm" style={{ color: "var(--text)" }}>{value}</dd>
    </div>
  );
}

function BackLink({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="mb-3 inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium"
      style={{ color: "var(--text-muted)" }}
    >
      <ArrowLeft className="h-3.5 w-3.5" /> Kembali
    </button>
  );
}

function IconTile({
  icon: Icon,
  label,
  badge,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  badge?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex cursor-pointer flex-col items-center gap-2 rounded-xl p-3 text-center transition-colors hover:bg-[var(--hover)]"
    >
      <span className="relative flex h-12 w-12 items-center justify-center rounded-full" style={{ backgroundColor: "var(--accent-tint)" }}>
        <Icon className="h-5 w-5" style={{ color: "var(--accent)" }} />
        {badge && (
          <span
            className="absolute -right-1 -top-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none text-white"
            style={{ backgroundColor: "#dc2626" }}
          >
            {badge}
          </span>
        )}
      </span>
      <span className="text-xs font-medium" style={{ color: "var(--text)" }}>{label}</span>
    </button>
  );
}

function IconCategory({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p
        className="px-1 pb-2 text-[11px] font-semibold uppercase tracking-widest"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </p>
      <div className="grid grid-cols-3 gap-1 sm:grid-cols-4">{children}</div>
    </div>
  );
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const h = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
  const m = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
  const s = String(totalSeconds % 60).padStart(2, "0");
  return `${h}.${m}.${s}`;
}

/** Halaman Absensi tersendiri (Fase 36) -- dibuka dari widget ringkas di
 * home Portal Saya, bukan lagi kartu inline dengan tombol clock langsung.
 * Strip kalender mingguan + shift + tombol bulat Clock In/Out dengan
 * timer berjalan + alamat hasil reverse geocoding. */
function AbsensiPage({
  onBack,
  profile,
  attendanceToday,
  clockDirection,
  clockError,
  clockMutationError,
  startClock,
  showCamera,
  onCapture,
  onCameraCancel,
}: {
  onBack: () => void;
  profile: Profile;
  attendanceToday: TodayAttendance | null;
  clockDirection: "in" | "out" | null;
  clockError: string | null;
  clockMutationError: Error | null;
  startClock: (direction: "in" | "out") => void;
  showCamera: boolean;
  onCapture: (blob: Blob) => void;
  onCameraCancel: () => void;
}) {
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [elapsed, setElapsed] = useState(0);

  const { data: week } = useQuery({
    queryKey: ["me-attendance-week", toDateParam(weekStart)],
    queryFn: () =>
      api.get<WeekDay[]>(`/me/attendance/week?start_date=${toDateParam(weekStart)}`),
  });

  useEffect(() => {
    if (!attendanceToday?.clock_in || attendanceToday.clock_out) return;
    const clockInMs = new Date(attendanceToday.clock_in).getTime();
    const tick = () => setElapsed(Date.now() - clockInMs);
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [attendanceToday?.clock_in, attendanceToday?.clock_out]);

  const isClockedIn = Boolean(attendanceToday?.clock_in) && !attendanceToday?.clock_out;
  const isDone = Boolean(attendanceToday?.clock_out);

  return (
    <div className="space-y-4">
      <BackLink onClick={onBack} />
      {showCamera && <SelfieCameraModal onCapture={onCapture} onCancel={onCameraCancel} />}

      <div className="card">
        <div className="flex items-center justify-between gap-2">
          <button
            className="cursor-pointer rounded-lg p-1.5 hover:bg-[var(--hover)]"
            onClick={() => setWeekStart((d) => new Date(d.getTime() - 7 * 86400000))}
          >
            <ArrowLeft className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
          </button>
          <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            {weekStart.toLocaleDateString("id-ID", { month: "long", year: "numeric" })}
          </p>
          <button
            className="cursor-pointer rounded-lg p-1.5 hover:bg-[var(--hover)]"
            onClick={() => setWeekStart((d) => new Date(d.getTime() + 7 * 86400000))}
          >
            <ArrowLeft className="h-4 w-4 rotate-180" style={{ color: "var(--text-muted)" }} />
          </button>
        </div>
        <div className="mt-3 grid grid-cols-7 gap-1 text-center">
          {(week ?? []).map((d, i) => {
            const isToday = d.date === toDateParam(new Date());
            return (
              <div
                key={d.date}
                className="rounded-lg py-2"
                style={{ backgroundColor: isToday ? "var(--accent-tint)" : undefined }}
              >
                <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                  {WEEKDAY_LABELS[i]}
                </p>
                <p className="mt-0.5 text-sm font-medium" style={{ color: "var(--text)" }}>
                  {new Date(d.date).getDate()}
                </p>
                <span
                  className="mx-auto mt-1 block h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: weekDayDotColor(d.status) }}
                />
              </div>
            );
          })}
        </div>
      </div>

      <div className="card flex flex-col items-center gap-4 py-8 text-center">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {profile.shift_start_time && profile.shift_end_time
            ? `Shift: ${profile.shift_start_time.slice(0, 5)} - ${profile.shift_end_time.slice(0, 5)}`
            : "Shift belum diatur HR"}
        </p>

        <div
          className="flex h-48 w-48 flex-col items-center justify-center gap-3 rounded-full"
          style={{ border: "3px solid var(--border)" }}
        >
          <p className="text-2xl font-semibold tabular-nums" style={{ color: "var(--text)" }}>
            {formatElapsed(elapsed)}
          </p>
          {!isDone && (
            <button
              onClick={() => startClock(isClockedIn ? "out" : "in")}
              disabled={clockDirection !== null}
              className="btn"
            >
              {clockDirection !== null
                ? "Memproses..."
                : isClockedIn
                  ? "Absen Keluar"
                  : "Absen Masuk"}
            </button>
          )}
          {isDone && <span className="badge pill p-green">Selesai hari ini</span>}
        </div>

        {clockError && <p className="text-sm text-red-600 dark:text-red-400">{clockError}</p>}
        {clockMutationError && (
          <p className="text-sm text-red-600 dark:text-red-400">{clockMutationError.message}</p>
        )}

        {attendanceToday?.clock_in && (
          <div className="w-full space-y-1 text-left text-sm" style={{ color: "var(--text)" }}>
            <p>
              Titik Lokasi <span className="text-emerald-700 dark:text-emerald-400">✓</span>
            </p>
            <p style={{ color: "var(--text-muted)" }}>
              {(isDone ? attendanceToday.clock_out_address : attendanceToday.clock_in_address) ??
                "Alamat tidak tersedia"}
            </p>
          </div>
        )}

        <div className="flex flex-wrap justify-center gap-3">
          {attendanceToday?.has_clock_in_selfie && (
            <button
              onClick={() =>
                openDownload(`/me/attendance/${attendanceToday.id}/selfie/in/download-url`)
              }
              className="text-sm font-medium hover:opacity-80"
              style={{ color: "var(--accent)" }}
            >
              Lihat Selfie Masuk
            </button>
          )}
          {attendanceToday?.has_clock_out_selfie && (
            <button
              onClick={() =>
                openDownload(`/me/attendance/${attendanceToday.id}/selfie/out/download-url`)
              }
              className="text-sm font-medium hover:opacity-80"
              style={{ color: "var(--accent)" }}
            >
              Lihat Selfie Keluar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function MyPortal() {
  const qc = useQueryClient();
  const today = new Date();
  const [attPeriod, setAttPeriod] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });
  const [passwordMsg, setPasswordMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  // Priming izin: minta lokasi+kamera begitu halaman dibuka (bukan nunggu
  // klik Absen) supaya prompt-nya tidak gampang terlewat di HP. Diam-diam
  // (tidak munculkan error) -- kegagalan sungguhan baru ditampilkan saat
  // user benar-benar klik Absen.
  useEffect(() => {
    getGpsPosition().catch(() => {});
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "user" } })
      .then((stream) => stream.getTracks().forEach((t) => t.stop()))
      .catch(() => {});
  }, []);

  const { data: profile, error, isLoading } = useQuery({
    queryKey: ["me-profile"],
    queryFn: () => api.get<Profile>("/me/profile"),
    retry: false,
  });
  const contractsQuery = useQuery({
    queryKey: ["me-contracts"],
    queryFn: () => api.get<ContractRow[]>("/me/contracts"),
  });
  const contracts = contractsQuery.data;
  const documentsQuery = useQuery({
    queryKey: ["me-documents"],
    queryFn: () => api.get<DocumentRow[]>("/me/documents"),
  });
  const documents = documentsQuery.data;
  const payslipsQuery = useQuery({
    queryKey: ["me-payslips"],
    queryFn: () => api.get<PayslipRow[]>("/me/payslips"),
  });
  const payslips = payslipsQuery.data;
  const { data: attendance } = useQuery({
    queryKey: ["me-attendance", attPeriod],
    queryFn: () =>
      api.get<AttendanceRow[]>(`/me/attendance?year=${attPeriod.year}&month=${attPeriod.month}`),
  });
  const leavesQuery = useQuery({
    queryKey: ["me-leaves"],
    queryFn: () => api.get<LeaveRow[]>("/me/leave-requests"),
  });
  const leaves = leavesQuery.data;
  const { data: leaveBalance } = useQuery({
    queryKey: ["me-leave-balance", today.getFullYear()],
    queryFn: () =>
      api.get<LeaveBalanceRow | null>("/me/leave-balance"),
  });
  const { data: notifications } = useQuery({
    queryKey: ["me-notifications"],
    queryFn: () => api.get<AppNotification[]>("/me/notifications"),
  });
  const correctionsQuery = useQuery({
    queryKey: ["me-corrections"],
    queryFn: () => api.get<AttendanceCorrectionRow[]>("/me/attendance-corrections"),
  });
  const corrections = correctionsQuery.data;
  const overtimeQuery = useQuery({
    queryKey: ["me-overtime"],
    queryFn: () => api.get<OvertimeRequestRow[]>("/me/overtime-requests"),
  });
  const overtimeRequests = overtimeQuery.data;

  const { data: attendanceToday } = useQuery({
    queryKey: ["me-attendance-today"],
    queryFn: () => api.get<TodayAttendance | null>("/me/attendance/today"),
  });
  const [clockDirection, setClockDirection] = useState<"in" | "out" | null>(null);
  const [clockError, setClockError] = useState<string | null>(null);
  const [showCamera, setShowCamera] = useState(false);
  const pendingCoordsRef = useRef<{ lat: number; lng: number } | null>(null);

  const clockMutation = useMutation({
    mutationFn: ({ direction, formData }: { direction: "in" | "out"; formData: FormData }) =>
      api.upload(`/me/attendance/clock-${direction}`, formData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me-attendance-today"] });
      qc.invalidateQueries({ queryKey: ["me-attendance"] });
    },
  });

  function startClock(direction: "in" | "out") {
    setClockError(null);
    setClockDirection(direction);
    getGpsPosition()
      .then((pos) => {
        pendingCoordsRef.current = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setShowCamera(true);
      })
      .catch((err: unknown) => {
        setClockError(err instanceof Error ? err.message : "Gagal mengambil lokasi");
        setClockDirection(null);
      });
  }

  function handleCaptured(blob: Blob) {
    setShowCamera(false);
    const coords = pendingCoordsRef.current;
    const direction = clockDirection;
    if (!coords || !direction) {
      setClockDirection(null);
      return;
    }
    const fd = new FormData();
    fd.append("file", blob, "selfie.jpg");
    fd.append("latitude", String(coords.lat));
    fd.append("longitude", String(coords.lng));
    clockMutation.mutate(
      { direction, formData: fd },
      { onSettled: () => setClockDirection(null) }
    );
  }

  function handleCameraCancel() {
    setShowCamera(false);
    setClockDirection(null);
  }

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

  const submitOvertime = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/me/overtime-requests", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me-overtime"] }),
  });
  const cancelOvertime = useMutation({
    mutationFn: (id: string) => api.post(`/me/overtime-requests/${id}/cancel`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me-overtime"] }),
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

  if (isLoading) return <p style={{ color: "var(--text-muted)" }}>Memuat portal...</p>;
  if (error || !profile) {
    return (
      <div className="card">
        <h1 className="text-2xl font-semibold" style={{ color: "var(--text)" }}>Portal Saya</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--text-muted)" }}>
          Akun ini belum tertaut ke data karyawan. Silakan hubungi HR untuk
          mengaktifkan portal Anda.
        </p>
      </div>
    );
  }

  const hour = today.getHours();
  const greeting = hour < 11 ? "Selamat pagi" : hour < 15 ? "Selamat siang" : hour < 19 ? "Selamat sore" : "Selamat malam";
  const unreadCount = (notifications ?? []).filter((n) => !n.read_at).length;

  // ---------- Kolom tabel (DataTable: tampil sebagai kartu di layar HP) ----------
  const statusColumn = {
    key: "status",
    header: "Status",
    cell: (r: { status: string }) => <span className={`badge ${LEAVE_STATUS_BADGES[r.status] ?? ""}`}>{r.status}</span>,
  };
  const noteColumn = {
    key: "note",
    header: "Catatan HR",
    cell: (r: { decision_note: string | null }) => r.decision_note ?? "-",
  };
  const cancelColumn = (cancel: { mutate: (id: string) => void; isPending: boolean }) => ({
    key: "aksi",
    header: "Aksi",
    cell: (r: { id: string; status: string }) =>
      r.status === "menunggu" ? (
        <button
          onClick={() => cancel.mutate(r.id)}
          disabled={cancel.isPending}
          className="text-sm font-medium text-rose-700 hover:text-rose-800 dark:text-rose-400"
        >
          Batalkan
        </button>
      ) : null,
  });
  const downloadButton = (path: string, label = "Unduh") => (
    <button
      onClick={() => openDownload(path)}
      className="text-sm font-medium hover:opacity-80"
      style={{ color: "var(--accent)" }}
    >
      {label}
    </button>
  );

  const contractColumns: Column<ContractRow>[] = [
    { key: "no", header: "Nomor Kontrak", className: "font-medium", cell: (c) => c.contract_no },
    { key: "period", header: "Periode", cell: (c) => `${formatDate(c.start_date)} s.d. ${formatDate(c.end_date)}` },
    { key: "sign", header: "Status TTD", cell: (c) => c.sign_status },
    {
      key: "file",
      header: "File",
      cell: (c) => (c.file_name ? downloadButton(`/me/contracts/${c.id}/download-url`) : "-"),
    },
  ];
  const documentColumns: Column<DocumentRow>[] = [
    { key: "title", header: "Judul", className: "font-medium", cell: (d) => d.title },
    { key: "type", header: "Jenis", cell: (d) => d.document_type },
    { key: "version", header: "Versi", cell: (d) => `v${d.version}` },
    { key: "uploaded", header: "Diunggah", cell: (d) => formatDate(d.uploaded_at) },
    { key: "aksi", header: "Aksi", cell: (d) => downloadButton(`/me/documents/${d.id}/download-url`) },
  ];
  // "Diterima" sengaja kolom kedua: di HP (kartu) angka yang paling dicari
  // karyawan langsung terlihat di bawah periode.
  const payslipColumns: Column<PayslipRow>[] = [
    {
      key: "period",
      header: "Periode",
      className: "font-medium",
      cell: (p) => `${MONTHS[p.month - 1]} ${p.year}`,
      sortValue: (p) => p.year * 100 + p.month,
    },
    {
      key: "net",
      header: "Diterima",
      numeric: true,
      className: "font-semibold text-emerald-700 dark:text-emerald-400",
      cell: (p) => formatRupiah(Number(p.net_pay)),
    },
    { key: "base", header: "Gaji Pokok", numeric: true, cell: (p) => formatRupiah(Number(p.base_salary)) },
    { key: "allowance", header: "Tunjangan", numeric: true, cell: (p) => formatRupiah(Number(p.allowance)) },
    {
      key: "overtime",
      header: "Lembur",
      numeric: true,
      cell: (p) => (p.overtime_hours > 0 ? `${p.overtime_hours} jam · ${formatRupiah(Number(p.overtime_amount))}` : "-"),
    },
    { key: "gross", header: "Bruto", numeric: true, cell: (p) => formatRupiah(Number(p.gross)) },
    {
      key: "pph21",
      header: "PPh21",
      numeric: true,
      className: "text-rose-700 dark:text-rose-400",
      cell: (p) => `-${formatRupiah(Number(p.tax_pph21))}`,
    },
    {
      key: "deductions",
      header: "Potongan",
      numeric: true,
      className: "text-rose-700 dark:text-rose-400",
      cell: (p) => `-${formatRupiah(Number(p.deductions))}`,
    },
  ];
  const correctionColumns: Column<AttendanceCorrectionRow>[] = [
    {
      key: "period",
      header: "Periode",
      className: "font-medium",
      cell: (c) => `${String(c.month).padStart(2, "0")}/${c.year}`,
    },
    {
      key: "usulan",
      header: "Usulan",
      cell: (c) =>
        `${c.requested_present_days} hari hadir · ${c.requested_overtime_hours} jam lembur${c.reason ? ` · ${c.reason}` : ""}`,
    },
    statusColumn,
    noteColumn,
    cancelColumn(cancelCorrection),
  ];
  const overtimeColumns: Column<OvertimeRequestRow>[] = [
    { key: "date", header: "Tanggal", className: "font-medium", cell: (o) => formatDate(o.date) },
    { key: "hours", header: "Jam Diajukan", cell: (o) => `${o.requested_hours} jam` },
    { key: "reason", header: "Alasan", cell: (o) => o.reason ?? "-" },
    statusColumn,
    noteColumn,
    cancelColumn(cancelOvertime),
  ];
  const leaveColumns: Column<LeaveRow>[] = [
    {
      key: "type",
      header: "Jenis",
      className: "font-medium",
      cell: (lv) => LEAVE_TYPES.find((t) => t.value === lv.leave_type)?.label ?? lv.leave_type,
    },
    {
      key: "date",
      header: "Tanggal",
      cell: (lv) => `${formatDate(lv.start_date)} s.d. ${formatDate(lv.end_date)}${lv.reason ? ` · ${lv.reason}` : ""}`,
    },
    statusColumn,
    noteColumn,
    {
      key: "file",
      header: "Lampiran",
      className: "whitespace-nowrap",
      cell: (lv) =>
        lv.file_name ? (
          downloadButton(
            `/me/leave-requests/${lv.id}/attachment/download-url`,
            `Lampiran (${(lv.file_size / 1024).toFixed(0)} KB)`
          )
        ) : lv.status === "menunggu" ? (
          <label className="cursor-pointer text-sm font-medium hover:opacity-80" style={{ color: "var(--accent)" }}>
            + Lampirkan
            <input
              type="file"
              className="sr-only"
              aria-label="Lampirkan file ke pengajuan cuti"
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
        ),
    },
    cancelColumn(cancelLeave),
  ];

  return (
    <div className="space-y-4">
      <PageHeader icon={UserCircle} title="Portal Saya" subtitle={`${greeting}, ${profile.full_name}`} />

      {activeSection === null && (
        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold" style={{ color: "var(--text)" }}>Absen Masuk/Keluar</h2>
              {attendanceToday?.clock_out ? (
                <span className="badge pill p-green mt-1 inline-block">Selesai hari ini</span>
              ) : attendanceToday?.clock_in ? (
                <span className="badge pill p-yellow mt-1 inline-block">Sudah absen masuk</span>
              ) : (
                <span className="badge pill p-gray mt-1 inline-block">Belum absen masuk</span>
              )}
            </div>
            <button onClick={() => setActiveSection("absen")} className="btn">
              Buka Absensi
            </button>
          </div>
        </div>
      )}

      {activeSection === "absen" && (
        <AbsensiPage
          onBack={() => setActiveSection(null)}
          profile={profile}
          attendanceToday={attendanceToday ?? null}
          clockDirection={clockDirection}
          clockError={clockError}
          clockMutationError={clockMutation.error as Error | null}
          startClock={startClock}
          showCamera={showCamera}
          onCapture={handleCaptured}
          onCameraCancel={handleCameraCancel}
        />
      )}

      {activeSection === null && (
        <div className="card space-y-5">
          <IconCategory label="Kepegawaian">
            <IconTile icon={IdCard} label="Profil Saya" onClick={() => setActiveSection("profil")} />
            <IconTile icon={FileSignature} label="Kontrak Kerja" onClick={() => setActiveSection("kontrak")} />
            <IconTile icon={FileText} label="Dokumen Saya" onClick={() => setActiveSection("dokumen")} />
          </IconCategory>
          <IconCategory label="Kehadiran">
            <IconTile icon={CalendarClock} label="Riwayat Absensi" onClick={() => setActiveSection("absensi")} />
            <IconTile icon={Timer} label="Lembur" onClick={() => setActiveSection("lembur")} />
          </IconCategory>
          <IconCategory label="Cuti">
            <IconTile
              icon={Plane}
              label="Cuti & Izin"
              badge={leaveBalance ? `${leaveBalance.remaining}h` : undefined}
              onClick={() => setActiveSection("cuti")}
            />
          </IconCategory>
          <IconCategory label="Keuangan">
            <IconTile icon={Wallet} label="Slip Gaji" onClick={() => setActiveSection("gaji")} />
          </IconCategory>
          <IconCategory label="Akun">
            <IconTile
              icon={Bell}
              label="Notifikasi"
              badge={unreadCount > 0 ? String(unreadCount) : undefined}
              onClick={() => setActiveSection("notifikasi")}
            />
            <IconTile icon={KeyRound} label="Ganti Password" onClick={() => setActiveSection("password")} />
          </IconCategory>
        </div>
      )}

      {activeSection === "profil" && (
      <div className="card">
        <BackLink onClick={() => setActiveSection(null)} />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Data Pribadi</h2>
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
      )}

      {activeSection === "kontrak" && (
      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
          <BackLink onClick={() => setActiveSection(null)} />
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Kontrak Kerja</h2>
        </div>
        {/* px-4 di HP: kartu induk p-0 (tabel desktop rata tepi). */}
        <div className="px-4 pb-4 sm:p-0">
          <DataTable
            plain
            label="Kontrak kerja saya"
            rows={contracts}
            columns={contractColumns}
            rowKey={(r) => r.id}
            query={contractsQuery}
            emptyTitle="Belum ada kontrak kerja."
          />
        </div>
      </div>
      )}

      {activeSection === "dokumen" && (
      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
          <BackLink onClick={() => setActiveSection(null)} />
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Dokumen Saya</h2>
        </div>
        {/* px-4 di HP: kartu induk p-0 (tabel desktop rata tepi). */}
        <div className="px-4 pb-4 sm:p-0">
          <DataTable
            plain
            label="Dokumen saya"
            rows={documents}
            columns={documentColumns}
            rowKey={(r) => r.id}
            query={documentsQuery}
            emptyTitle="Belum ada dokumen."
          />
        </div>
      </div>
      )}

      {activeSection === "gaji" && (
      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--border)" }}>
          <BackLink onClick={() => setActiveSection(null)} />
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Riwayat Slip Gaji</h2>
        </div>
        {/* px-4 di HP: kartu induk p-0 (tabel desktop rata tepi). */}
        <div className="px-4 pb-4 sm:p-0">
          <DataTable
            plain
            label="Riwayat slip gaji"
            rows={payslips}
            columns={payslipColumns}
            rowKey={(r) => r.id}
            query={payslipsQuery}
            defaultSort={{ key: "period", dir: "desc" }}
            emptyTitle="Belum ada slip gaji yang difinalisasi."
          />
        </div>
      </div>
      )}

      {activeSection === "absensi" && (
      <>
      <BackLink onClick={() => setActiveSection(null)} />
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Rekap Kehadiran</h2>
          <div className="flex items-center gap-2">
            <PeriodPicker value={attPeriod} onChange={setAttPeriod} label="rekap kehadiran" />
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
          <p className="mt-3 text-sm" style={{ color: "var(--text-muted)" }}>
            Belum ada rekap kehadiran untuk periode ini.
          </p>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--text)" }}>Koreksi Absensi</h2>
        <form
          className="mt-3 grid grid-cols-1 items-end gap-2 sm:grid-cols-[auto_auto_auto_1fr_auto]"
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
          {/* Label terlihat: dulu placeholder saja, padahal bulan/tahun berisi
              defaultValue sehingga placeholder-nya tidak pernah tampil. */}
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Bulan</span>
            <select name="month" required defaultValue={attPeriod.month} className="input w-auto">
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Tahun</span>
            <input name="year" type="number" required defaultValue={attPeriod.year} className="input w-24" />
          </label>
          <div className="flex gap-2">
            <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
              <span>Hari hadir</span>
              <input name="present_days" type="number" min={0} className="input w-28" />
            </label>
            <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
              <span>Jam lembur</span>
              <input name="overtime_hours" type="number" min={0} className="input w-28" />
            </label>
          </div>
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Alasan koreksi</span>
            <input name="reason" className="input" />
          </label>
          <button disabled={createCorrection.isPending} className="btn">
            Ajukan
          </button>
        </form>
        {createCorrection.error && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">
            {(createCorrection.error as Error).message}
          </p>
        )}
        <div className="mt-3">
          <DataTable
            plain
            label="Pengajuan koreksi absensi"
            rows={corrections}
            columns={correctionColumns}
            rowKey={(r) => r.id}
            query={correctionsQuery}
            emptyTitle="Belum ada pengajuan koreksi absensi."
          />
        </div>
      </div>
      </>
      )}

      {activeSection === "lembur" && (
      <div className="card">
        <BackLink onClick={() => setActiveSection(null)} />
        <h2 className="font-semibold" style={{ color: "var(--text)" }}>Ajukan Lembur</h2>
        <form
          className="mt-3 grid grid-cols-1 items-end gap-2 sm:grid-cols-[auto_auto_1fr_auto]"
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            submitOvertime.mutate({
              date: form.get("date"),
              requested_hours: Number(form.get("requested_hours") || 0),
              reason: form.get("reason") || null,
            });
            e.currentTarget.reset();
          }}
        >
<label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Tanggal lembur</span>
            <input name="date" type="date" required className="input" />
          </label>
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Jam lembur</span>
            <input name="requested_hours" type="number" min={1} max={24} required className="input w-32" />
          </label>
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Alasan (opsional)</span>
            <input name="reason" className="input" />
          </label>
          <button disabled={submitOvertime.isPending} className="btn">
            Ajukan
          </button>
        </form>
        {submitOvertime.error && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">{(submitOvertime.error as Error).message}</p>
        )}
        <div className="mt-3">
          <DataTable
            plain
            label="Pengajuan lembur"
            rows={overtimeRequests}
            columns={overtimeColumns}
            rowKey={(r) => r.id}
            query={overtimeQuery}
            emptyTitle="Belum ada pengajuan lembur."
          />
        </div>
      </div>
      )}

      {activeSection === "cuti" && (
      <>
      <BackLink onClick={() => setActiveSection(null)} />
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>
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
          <p className="mt-3 text-sm" style={{ color: "var(--text-muted)" }}>
            Jatah cuti belum diatur HR — pengajuan cuti tahunan masih bisa
            diajukan tanpa batas kuota.
          </p>
        )}
      </div>

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--text)" }}>Ajukan Cuti / Izin</h2>
        <form
          className="mt-3 grid grid-cols-1 items-end gap-2 sm:grid-cols-[auto_1fr_1fr_1fr_auto]"
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
<label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Jenis</span>
            <select name="leave_type" className="input w-auto" defaultValue="cuti_tahunan">
              {LEAVE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Mulai</span>
            <input name="start_date" type="date" required className="input" />
          </label>
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Sampai</span>
            <input name="end_date" type="date" required className="input" />
          </label>
          <label className="space-y-1 text-xs font-medium" style={{ color: "var(--th-color)" }}>
            <span>Alasan (opsional)</span>
            <input name="reason" className="input" />
          </label>
          <button disabled={submitLeave.isPending} className="btn">
            Ajukan
          </button>
        </form>
        {submitLeave.error && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">{(submitLeave.error as Error).message}</p>
        )}
        <div className="mt-3">
          <DataTable
            plain
            label="Pengajuan cuti dan izin"
            rows={leaves}
            columns={leaveColumns}
            rowKey={(r) => r.id}
            query={leavesQuery}
            emptyTitle="Belum ada pengajuan cuti/izin."
          />
        </div>
      </div>
      </>
      )}

      {activeSection === "notifikasi" && (
      <div className="card">
        <BackLink onClick={() => setActiveSection(null)} />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold" style={{ color: "var(--text)" }}>Notifikasi</h2>
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
              style={{ backgroundColor: n.read_at ? "var(--hover)" : "var(--accent-tint)" }}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium" style={{ color: n.read_at ? "var(--text-muted)" : "var(--text)" }}>
                    {n.title}
                  </p>
                  {n.body && <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>{n.body}</p>}
                  <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {formatDateTime(n.created_at)}
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
            <li className="text-sm" style={{ color: "var(--text-muted)" }}>Belum ada notifikasi.</li>
          )}
        </ul>
      </div>
      )}

      {activeSection === "password" && (
      <div className="card max-w-xl">
        <BackLink onClick={() => setActiveSection(null)} />
        <h2 className="font-semibold" style={{ color: "var(--text)" }}>Ganti Password</h2>
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
              passwordMsg.ok ? "text-emerald-700 dark:text-emerald-400" : "text-red-600 dark:text-red-400"
            }`}
          >
            {passwordMsg.text}
          </p>
        )}
      </div>
      )}
    </div>
  );
}
