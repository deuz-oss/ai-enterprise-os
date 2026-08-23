import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
        <h1 className="text-2xl font-bold text-slate-800">Pengguna</h1>
        <p className="mt-1 text-sm text-slate-500">
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
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Nama</th>
              <th className="th">Email</th>
              <th className="th">Role</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(users ?? []).map((u) => (
              <tr key={u.id} className="hover:bg-slate-50">
                <td className="td font-medium">{u.full_name}</td>
                <td className="td">{u.email}</td>
                <td className="td">
                  <select
                    value={u.role}
                    onChange={(e) => updateUser.mutate({ id: u.id, body: { role: e.target.value } })}
                    className="badge cursor-pointer border-0 bg-slate-100 text-slate-700"
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
                    className={`badge ${
                      u.is_active
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-red-100 text-red-600"
                    }`}
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
