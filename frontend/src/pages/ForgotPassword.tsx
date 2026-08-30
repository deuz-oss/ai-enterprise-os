import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Info, Mail, Send } from "lucide-react";
import { api, ApiError } from "../api/client";

/** Lupa kata sandi ala mockup forgot-password.html. Tab NIK/WA di mockup
 * dijatuhkan (tidak ada lookup non-email di backend) — hanya jalur email
 * yang didukung `POST /auth/forgot-password`.
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
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-6 antialiased">
      <div
        className="fixed inset-x-0 top-0 h-1"
        style={{ background: "linear-gradient(90deg,#0f172a 0%,#1e3a5f 40%,#a16207 100%)" }}
      />
      <div className="mb-6 flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900 text-sm font-bold text-white">
          AE
        </div>
        <div>
          <div className="text-sm font-semibold leading-none text-slate-900">
            AI Enterprise OS
          </div>
          <div className="text-xs text-slate-500">Pulihkan akses workspace</div>
        </div>
      </div>

      <div className="w-full max-w-[420px] rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7">
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Masuk
        </Link>
        <h1 className="mt-3 text-xl font-semibold tracking-tight text-slate-900">
          Lupa kata sandi?
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Masukkan email kantor Anda — kami kirim link untuk atur ulang kata sandi.
        </p>

        {sent ? (
          <div className="mt-5 flex gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
            <div className="text-xs leading-relaxed">
              <div className="font-semibold text-emerald-900">Cek inbox Anda</div>
              <div className="text-emerald-800">
                Jika email terdaftar, link reset sudah dikirim. Link berlaku 30 menit dan hanya
                bisa dipakai sekali.
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            {error && (
              <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </p>
            )}
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                Email kantor
              </label>
              <div className="relative mt-1.5">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="email"
                  required
                  autoFocus
                  placeholder="nama@perusahaan.co.id"
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <p className="mt-1.5 text-xs text-slate-500">Link reset berlaku 30 menit, 1x pakai.</p>
            </div>

            <div className="flex gap-2.5 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
              <div className="text-xs leading-relaxed text-slate-600">
                Tenant terdeteksi otomatis dari email Anda. Jika tidak menerima link, hubungi{" "}
                <span className="font-medium text-slate-800">HR / admin tenant</span> Anda.
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-slate-900 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Mengirim..." : "Kirim link reset"}
              {!loading && <Send className="h-4 w-4" />}
            </button>
          </form>
        )}

        <div className="mt-5 text-center text-xs text-slate-500">
          Ingat kata sandi?{" "}
          <Link
            to="/login"
            className="font-medium text-slate-700 underline decoration-slate-300 underline-offset-4 hover:text-slate-900"
          >
            Masuk sekarang
          </Link>
        </div>
      </div>

      <div className="mt-4 text-center text-xs text-slate-400">© 2026 AI Enterprise OS</div>
    </div>
  );
}
