import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, KeyRound, XCircle } from "lucide-react";
import { api, ApiError } from "../api/client";

/** Halaman tujuan link reset dari email — melengkapi alur forgot-password.html
 * (mockup berhenti di "link terkirim"; ini landing page saat link diklik). */
export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Konfirmasi kata sandi tidak sama");
      return;
    }
    if (newPassword.length < 8) {
      setError("Kata sandi minimal 8 karakter");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.post("/auth/reset-password", { token, new_password: newPassword });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal mengatur ulang kata sandi");
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
          <div className="text-xs text-slate-500">Atur ulang kata sandi</div>
        </div>
      </div>

      <div className="w-full max-w-[420px] rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-7">
        {!token ? (
          <div className="flex gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-700" />
            <div className="text-xs leading-relaxed">
              <div className="font-semibold text-red-900">Link tidak valid</div>
              <div className="text-red-800">
                Link ini tidak menyertakan token reset. Minta link baru lewat halaman{" "}
                <Link to="/forgot-password" className="underline underline-offset-2">
                  Lupa kata sandi
                </Link>
                .
              </div>
            </div>
          </div>
        ) : done ? (
          <div className="flex gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
            <div className="text-xs leading-relaxed">
              <div className="font-semibold text-emerald-900">Kata sandi berhasil diganti</div>
              <div className="text-emerald-800">
                Silakan masuk kembali dengan kata sandi baru Anda.
              </div>
            </div>
          </div>
        ) : (
          <>
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Masuk
            </Link>
            <h1 className="mt-3 text-xl font-semibold tracking-tight text-slate-900">
              Atur kata sandi baru
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Link ini hanya berlaku sekali pakai dan akan kedaluwarsa otomatis.
            </p>

            <form onSubmit={handleSubmit} className="mt-4 space-y-4">
              {error && (
                <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {error}
                </p>
              )}
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Kata sandi baru
                </label>
                <div className="relative mt-1.5">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type="password"
                    required
                    minLength={8}
                    autoFocus
                    placeholder="Minimal 8 karakter"
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Konfirmasi kata sandi
                </label>
                <div className="relative mt-1.5">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="Ulangi kata sandi baru"
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-slate-900 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Memproses..." : "Ganti kata sandi"}
              </button>
            </form>
          </>
        )}

        <div className="mt-5 text-center text-xs text-slate-500">
          <Link
            to="/login"
            className="font-medium text-slate-700 underline decoration-slate-300 underline-offset-4 hover:text-slate-900"
          >
            Kembali ke halaman masuk
          </Link>
        </div>
      </div>

      <div className="mt-4 text-center text-xs text-slate-400">© 2026 AI Enterprise OS</div>
    </div>
  );
}
