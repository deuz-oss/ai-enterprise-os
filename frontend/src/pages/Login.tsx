import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api/client";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="card w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--n-text)" }}>AI Enterprise OS</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--n-text-muted)" }}>Masuk ke akun tim Anda</p>
        </div>
        {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</p>}
        <input
          type="email"
          required
          placeholder="Email"
          className="input"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          required
          placeholder="Password"
          className="input"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit" disabled={loading} className="btn w-full">
          {loading ? "Memproses..." : "Masuk"}
        </button>
      </form>
    </div>
  );
}
