import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Info, Lock, Mail, Sparkles, ArrowRight } from "lucide-react";
import { api, setToken } from "../api/client";
import { Button, Card } from "../components/ui";

/** Login dua panel ala mockup login.html — hero brand (desktop) + form.
 * Elemen dekoratif tanpa dukungan backend nyata (SSO Google, Magic Link,
 * slug tenant manual, remember-me, KPI ringkasan palsu) sengaja tidak
 * diikutkan — email sudah unik global sehingga tenant otomatis terdeteksi
 * saat login, tanpa perlu input tambahan.
 *
 * Dimigrasi 2026-09-03 ke token var(--...) + component library (Button,
 * Card) untuk PANEL KANAN (form) dan header mobile — sebelumnya 100%
 * hardcode slate-*, tidak ikut dark mode (temuan audit design-system).
 * PANEL KIRI (hero gradient gelap) SENGAJA TETAP hardcode dark — itu
 * elemen brand tetap yang memang selalu gelap di kedua mode, bukan bug.
 */
export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api.post<{
        access_token: string;
        user: { role: string };
      }>("/auth/login", { email, password });
      setToken(data.access_token);
      const target =
        data.user.role === "platform_admin"
          ? "/platform"
          : data.user.role === "karyawan"
            ? "/portal-saya"
            : "/";
      navigate(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login gagal");
    } finally {
      setLoading(false);
    }
  }

  // ⌘/Ctrl+Enter submit dari mana pun di form, selaras hint mockup.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        formRef.current?.requestSubmit();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="flex min-h-screen antialiased" style={{ backgroundColor: "var(--bg)" }}>
      <div
        className="fixed inset-x-0 top-0 h-1"
        style={{ background: "linear-gradient(90deg,var(--accent) 0%,#1e3a5f 40%,#a16207 100%)" }}
      />

      {/* LEFT: brand hero (desktop only) — sengaja tetap gelap di kedua mode */}
      <div
        className="relative hidden overflow-hidden text-white lg:flex lg:w-[52%]"
        style={{ background: "linear-gradient(135deg,#020617 0%,#0f172a 55%,#1e3a5f 100%)" }}
      >
        <div
          className="absolute inset-0 opacity-[0.08]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 30% 20%,white 1px,transparent 1px),radial-gradient(circle at 70% 80%,white 1px,transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
        <div className="absolute -bottom-24 -right-24 h-[520px] w-[520px] rounded-full border border-white/10" />
        <div className="absolute -bottom-10 -right-10 h-[380px] w-[380px] rounded-full border border-white/10" />
        <div className="relative z-10 flex w-full flex-col p-10 xl:p-12">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-white text-sm font-bold text-slate-900">
              AE
            </div>
            <div>
              <div className="text-sm font-semibold leading-none tracking-tight">
                AI Enterprise OS
              </div>
              <div className="text-xs text-white/60">Outsourcing Operations</div>
            </div>
          </div>

          <div className="mt-16 max-w-[520px] xl:mt-20">
            <h1 className="mt-5 text-[34px] font-semibold leading-[1.05] tracking-tight xl:text-[40px]">
              Operasional enterprise,
              <br />
              <span className="text-white/60">satu pintu.</span>
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-white/65">
              Talent Cloud · Workforce Cloud · Revenue Cloud · Govern Cloud — rekrutmen, HR,
              payroll, tagihan, dan pembukuan dalam satu workspace.
            </p>
            <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white px-3 py-1.5 text-xs font-semibold uppercase tracking-widest text-slate-900">
              <Sparkles className="h-3.5 w-3.5 text-violet-600" /> AI Native
            </div>
          </div>

          <div className="mt-auto flex items-center gap-3 pt-10 text-xs text-white/50">
            <span>© 2026 AI Enterprise OS</span>
          </div>
        </div>
      </div>

      {/* RIGHT: form */}
      <div className="flex min-w-0 flex-1 flex-col" style={{ backgroundColor: "var(--bg)" }}>
        <div
          className="flex items-center gap-3 px-6 py-5 lg:hidden"
          style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
        >
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
              Outsourcing Operations
            </div>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center p-6 lg:p-10">
          <div className="w-full max-w-[420px]">
            <Card className="sm:p-7">
              <h2 className="text-[20px] font-semibold tracking-tight" style={{ color: "var(--text)" }}>
                Masuk ke workspace
              </h2>
              <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
                Gunakan email &amp; kata sandi akun tenant Anda.
              </p>

              {error && (
                <p className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-400">
                  {error}
                </p>
              )}

              <form ref={formRef} onSubmit={handleSubmit} className="mt-5 space-y-4">
                <div>
                  <label
                    className="text-xs font-semibold uppercase tracking-wide"
                    style={{ color: "var(--text-muted)" }}
                  >
                    Email
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
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <label
                      className="text-xs font-semibold uppercase tracking-wide"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Kata sandi
                    </label>
                    <Link
                      to="/forgot-password"
                      className="text-xs font-medium underline underline-offset-4"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Lupa kata sandi?
                    </Link>
                  </div>
                  <div className="relative mt-1.5">
                    <Lock
                      className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
                      style={{ color: "var(--text-muted)" }}
                    />
                    <input
                      type={showPassword ? "text" : "password"}
                      required
                      placeholder="••••••••"
                      className="input h-10 pl-9 pr-9"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer rounded-lg p-1.5 hover:opacity-70"
                      style={{ color: "var(--text-muted)" }}
                      title={showPassword ? "Sembunyikan sandi" : "Tampilkan sandi"}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  loading={loading}
                  className="w-full"
                  icon={<ArrowRight className="h-4 w-4" />}
                >
                  {loading ? "Memproses..." : "Masuk"}
                </Button>
                <p className="hidden text-center text-xs sm:block" style={{ color: "var(--text-muted)" }}>
                  ⌘ + Enter untuk masuk
                </p>
              </form>

              <div className="mt-6 flex gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/40 dark:bg-amber-900/20">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" />
                <div className="text-xs leading-relaxed">
                  <div className="font-semibold text-amber-900 dark:text-amber-300">
                    Akses mengikuti lisensi tenant
                  </div>
                  <div className="text-amber-800 dark:text-amber-400">
                    Jika modul terkunci, minta admin tenant mengaktifkan lewat halaman Aplikasi,
                    atau hubungi platform admin.
                  </div>
                </div>
              </div>
            </Card>

            <div className="mt-4 text-center text-xs" style={{ color: "var(--text-muted)" }}>
              © 2026 AI Enterprise OS
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
