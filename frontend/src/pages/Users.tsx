import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserCog } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { api } from "../api/client";

interface UserRow {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

const ROLES = [
  { value: "admin", label: "Admin" },
  { value: "business_dev", label: "Business Dev" },
  { value: "recruiter", label: "Recruiter" },
  { value: "hr", label: "HR" },
  { value: "operations", label: "Operations" },
  { value: "finance", label: "Finance" },
  { value: "management", label: "Management" },
  { value: "karyawan", label: "Karyawan (Portal Saya)" },
];

export default function Users() {
  const qc = useQueryClient();
  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserRow[]>("/auth/users"),
  });

  const updateUser = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/auth/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const createUser = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/auth/register", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <div className="space-y-4">
      <div>
        <PageHeader icon={UserCog} title="Pengguna" />
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          Kelola akun tim. Akun baru dibuat lewat tombol "+ Pengguna Baru".
        </p>
      </div>

      <form
        className="card grid grid-cols-1 gap-3 sm:grid-cols-4"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          createUser.mutate({
            email: form.get("email"),
            full_name: form.get("full_name"),
            password: form.get("password"),
            role: form.get("role"),
          });
          e.currentTarget.reset();
        }}
      >
        <input name="email" type="email" required placeholder="Email *" className="input" />
        <input name="full_name" required placeholder="Nama lengkap *" className="input" />
        <input name="password" required minLength={8} placeholder="Password min. 8 karakter *" className="input" />
        <div className="flex gap-2">
          <select name="role" className="input" defaultValue="recruiter">
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <button className="btn shrink-0" disabled={createUser.isPending}>
            + Buat
          </button>
        </div>
      </form>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
            <tr>
              <th className="th">Nama</th>
              <th className="th">Email</th>
              <th className="th">Role</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(users ?? []).map((u) => (
              <tr key={u.id} className="hover:bg-[var(--hover)]">
                <td className="td font-medium">{u.full_name}</td>
                <td className="td">{u.email}</td>
                <td className="td">
                  <select
                    value={u.role}
                    onChange={(e) => updateUser.mutate({ id: u.id, body: { role: e.target.value } })}
                    className="pill p-gray cursor-pointer border-0"
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="td">
                  <button
                    onClick={() =>
                      updateUser.mutate({ id: u.id, body: { is_active: !u.is_active } })
                    }
                    className={`${u.is_active ? "pill p-green" : "pill p-red"}`}
                  >
                    {u.is_active ? "aktif" : "nonaktif"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
