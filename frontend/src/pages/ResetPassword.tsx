import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, KeyRound, XCircle } from "lucide-react";
import { api, ApiError } from "../api/client";
import { Button, Card } from "../components/ui";

/** Halaman tujuan link reset dari email — melengkapi alur forgot-password.html
 * (mockup berhenti di "link terkirim"; ini landing page saat link diklik).
 *
 * Dimigrasi 2026-09-03 ke token var(--...) + component library (Button,
 * Card) — halaman ketiga (dari 3) yang sebelumnya 100% hardcode slate-*
 * dan tidak ikut dark mode (temuan audit design-system). Login.tsx dan
 * ForgotPassword.tsx sudah dimigrasi lebih dulu dengan pola yang sama.
 */
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
            Atur ulang kata sandi
          </div>
        </div>
      </div>

      <Card className="w-full max-w-[420px] sm:p-7">
        {!token ? (
          <div className="flex gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3 dark:border-red-900/40 dark:bg-red-900/20">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-700 dark:text-red-400" />
            <div className="text-xs leading-relaxed">
              <div className="font-semibold text-red-900 dark:text-red-300">Link tidak valid</div>
              <div className="text-red-800 dark:text-red-400">
                Link ini tidak menyertakan token reset. Minta link baru lewat halaman{" "}
                <Link to="/forgot-password" className="underline underline-offset-2">
                  Lupa kata sandi
                </Link>
                .
              </div>
            </div>
          </div>
        ) : done ? (
          <div className="flex gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900/40 dark:bg-emerald-900/20">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-400" />
            <div className="text-xs leading-relaxed">
              <div className="font-semibold text-emerald-900 dark:text-emerald-300">
                Kata sandi berhasil diganti
              </div>
              <div className="text-emerald-800 dark:text-emerald-400">
                Silakan masuk kembali dengan kata sandi baru Anda.
              </div>
            </div>
          </div>
        ) : (
          <>
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 text-xs font-medium hover:opacity-80"
              style={{ color: "var(--text-muted)" }}
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Kembali ke Masuk
            </Link>
            <h1 className="mt-3 text-xl font-semibold tracking-tight" style={{ color: "var(--text)" }}>
              Atur kata sandi baru
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
              Link ini hanya berlaku sekali pakai dan akan kedaluwarsa otomatis.
            </p>

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
                  Kata sandi baru
                </label>
                <div className="relative mt-1.5">
                  <KeyRound
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
                    style={{ color: "var(--text-muted)" }}
                  />
                  <input
                    type="password"
                    required
                    minLength={8}
                    autoFocus
                    placeholder="Minimal 8 karakter"
                    className="input h-10 pl-9"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label
                  className="text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--text-muted)" }}
                >
                  Konfirmasi kata sandi
                </label>
                <div className="relative mt-1.5">
                  <KeyRound
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
                    style={{ color: "var(--text-muted)" }}
                  />
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="Ulangi kata sandi baru"
                    className="input h-10 pl-9"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </div>
              </div>

              <Button type="submit" loading={loading} className="w-full">
                {loading ? "Memproses..." : "Ganti kata sandi"}
              </Button>
            </form>
          </>
        )}

        <div className="mt-5 text-center text-xs" style={{ color: "var(--text-muted)" }}>
          <Link to="/login" className="font-medium underline underline-offset-4" style={{ color: "var(--text)" }}>
            Kembali ke halaman masuk
          </Link>
        </div>
      </Card>

      <div className="mt-4 text-center text-xs" style={{ color: "var(--text-muted)" }}>
        © 2026 AI Enterprise OS
      </div>
    </div>
  );
}
