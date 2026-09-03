import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Info, Mail, Send } from "lucide-react";
import { api, ApiError } from "../api/client";
import { Button, Card } from "../components/ui";

/** Lupa kata sandi ala mockup forgot-password.html. Tab NIK/WA di mockup
 * dijatuhkan (tidak ada lookup non-email di backend) — hanya jalur email
 * yang didukung `POST /auth/forgot-password`.
 *
 * Dimigrasi 2026-09-03 ke token var(--...) + component library (Button,
 * Card) — sebelumnya halaman ini 100% hardcode kelas Tailwind slate-*,
 * jadi TIDAK ikut berubah sama sekali kalau user toggle dark mode (temuan
 * audit design-system). Warna status (sukses/error/info) sengaja tetap
 * pakai warna semantik tetap (emerald/red), bukan var(--accent) — sama
 * prinsipnya dengan Badge: warna makna tidak boleh ikut goyah kalau brand
 * accent ganti nanti.
 */
export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // Balasan backend selalu generik (anti user-enumeration) — sukses
      // tidak berarti email pasti terdaftar, cuma bahwa jika terdaftar,
      // link sudah dikirim.
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal mengirim permintaan");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center p-6 antialiased"
      style={{ backgroundColor: "var(--bg)" }}
    >
      <div
        className="fixed inset-x-0 top-0 h-1"
        style={{ background: "linear-gradient(90deg,var(--accent) 0%,#1e3a5f 40%,#a16207 100%)" }}
      />
      <div className="mb-6 flex items-center gap-3">
        <div
          className="grid h-9 w-9 place-items-center rounded-xl text-sm font-bold text-white"
          style={{ backgroundColor: "var(--accent)" }}
        >
          AE
        </div>
        <div>
          <div className="text-sm font-semibold leading-none" style={{ color: "var(--text)" }}>
            AI Enterprise OS
          </div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            Pulihkan akses workspace
          </div>
        </div>
      </div>

      <Card className="w-full max-w-[420px] sm:p-7">
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 text-xs font-medium hover:opacity-80"
          style={{ color: "var(--text-muted)" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Masuk
        </Link>
        <h1 className="mt-3 text-xl font-semibold tracking-tight" style={{ color: "var(--text)" }}>
          Lupa kata sandi?
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          Masukkan email kantor Anda — kami kirim link untuk atur ulang kata sandi.
        </p>

        {sent ? (
          <div className="mt-5 flex gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900/40 dark:bg-emerald-900/20">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-400" />
            <div className="text-xs leading-relaxed">
              <div className="font-semibold text-emerald-900 dark:text-emerald-300">
                Cek inbox Anda
              </div>
              <div className="text-emerald-800 dark:text-emerald-400">
                Jika email terdaftar, link reset sudah dikirim. Link berlaku 30 menit dan hanya
                bisa dipakai sekali.
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            {error && (
              <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-400">
                {error}
              </p>
            )}
            <div>
              <label
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--text-muted)" }}
              >
                Email kantor
              </label>
              <div className="relative mt-1.5">
                <Mail
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
                  style={{ color: "var(--text-muted)" }}
                />
                <input
                  type="email"
                  required
                  autoFocus
                  placeholder="nama@perusahaan.co.id"
                  className="input h-10 pl-9"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
                Link reset berlaku 30 menit, 1x pakai.
              </p>
            </div>

            <div className="flex gap-2.5 rounded-xl p-3" style={{ backgroundColor: "var(--hover)" }}>
              <Info className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
              <div className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
                Tenant terdeteksi otomatis dari email Anda. Jika tidak menerima link, hubungi{" "}
                <span className="font-medium" style={{ color: "var(--text)" }}>
                  HR / admin tenant
                </span>{" "}
                Anda.
              </div>
            </div>

            <Button type="submit" loading={loading} className="w-full" icon={<Send className="h-4 w-4" />}>
              {loading ? "Mengirim..." : "Kirim link reset"}
            </Button>
          </form>
        )}

        <div className="mt-5 text-center text-xs" style={{ color: "var(--text-muted)" }}>
          Ingat kata sandi?{" "}
          <Link to="/login" className="font-medium underline underline-offset-4" style={{ color: "var(--text)" }}>
            Masuk sekarang
          </Link>
        </div>
      </Card>

      <div className="mt-4 text-center text-xs" style={{ color: "var(--text-muted)" }}>
        © 2026 AI Enterprise OS
      </div>
    </div>
  );
}
