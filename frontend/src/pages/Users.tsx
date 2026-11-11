import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserCheck, UserCog, UserX } from "lucide-react";
import { PageHeader } from "../components/workspace";
import {
  type Column,
  confirmDialog,
  DataTable,
  KpiCard,
  FormField,
  type PillTab,
  PillTabs,
  TableStateRow,
} from "../components/ui";
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
  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserRow[]>("/auth/users"),
  });
  const users = usersQuery.data;
  const [statusTab, setStatusTab] = useState("");
  const activeCount = (users ?? []).filter((u) => u.is_active).length;
  const inactiveCount = (users ?? []).filter((u) => !u.is_active).length;
  const filteredUsers = (users ?? []).filter(
    (u) => !statusTab || (statusTab === "aktif" ? u.is_active : !u.is_active)
  );
  const statusTabs: PillTab[] = [
    { key: "", label: "Semua", count: (users ?? []).length },
    { key: "aktif", label: "Aktif", count: activeCount },
    { key: "nonaktif", label: "Nonaktif", count: inactiveCount },
  ];

  const updateUser = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/auth/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const createUser = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/auth/register", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const userColumns: Column<UserRow>[] = [
    { key: "name", header: "Nama", className: "font-medium", cell: (u) => u.full_name, sortValue: (u) => u.full_name },
    { key: "email", header: "Email", cell: (u) => u.email, sortValue: (u) => u.email },
    {
      key: "role",
      header: "Role",
      sortValue: (u) => u.role,
      cell: (u) => (
        <select
          value={u.role}
          onChange={(e) => updateUser.mutate({ id: u.id, body: { role: e.target.value } })}
          className="pill p-gray cursor-pointer border-0"
          aria-label={`Ubah role ${u.full_name}`}
        >
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (u) => (u.is_active ? 0 : 1),
      cell: (u) => (
        <button
          onClick={() =>
            u.is_active
              ? // Menonaktifkan = user tidak bisa login lagi; dulu sekali klik.
                confirmDialog({
                  title: `Nonaktifkan ${u.full_name}?`,
                  message: `${u.email} tidak bisa login sampai diaktifkan kembali. Data tidak dihapus.`,
                  confirmLabel: "Nonaktifkan",
                  onConfirm: () => updateUser.mutate({ id: u.id, body: { is_active: false } }),
                })
              : updateUser.mutate({ id: u.id, body: { is_active: true } })
          }
          className={u.is_active ? "pill p-green" : "pill p-red"}
          title={u.is_active ? "Klik untuk menonaktifkan" : "Klik untuk mengaktifkan"}
        >
          {u.is_active ? "aktif" : "nonaktif"}
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <PageHeader icon={UserCog} title="Pengguna" />
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          Kelola akun tim. Isi form di bawah lalu tekan "Buat Akun" untuk menambah pengguna.
        </p>
      </div>

      <form
        className="card grid grid-cols-1 items-start gap-3 sm:grid-cols-2 lg:grid-cols-4"
        aria-label="Buat pengguna baru"
        onSubmit={(e) => {
          e.preventDefault();
          const formEl = e.currentTarget;
          const form = new FormData(formEl);
          // Reset HANYA saat berhasil: dulu form dikosongkan saat submit, jadi
          // email duplikat (409) menghapus isian dan tampak seperti sukses.
          createUser.mutate(
            {
              email: form.get("email"),
              full_name: form.get("full_name"),
              password: form.get("password"),
              role: form.get("role"),
            },
            {
              onSuccess: () => {
                formEl.reset();
                toast.success(`Akun ${String(form.get("email"))} dibuat`);
              },
            }
          );
        }}
      >
        <FormField label="Email" required>
          {(field) => <input {...field} name="email" type="email" autoComplete="off" className="input" />}
        </FormField>
        <FormField label="Nama lengkap" required>
          {(field) => <input {...field} name="full_name" autoComplete="off" className="input" />}
        </FormField>
        {/* type="password" + new-password: dulu type="text" -- password akun baru
            tampil polos di layar dan bisa tersimpan di riwayat isian browser. */}
        <FormField label="Password awal" required hint="Minimal 8 karakter.">
          {(field) => (
            <input
              {...field}
              name="password"
              type="password"
              minLength={8}
              autoComplete="new-password"
              className="input"
            />
          )}
        </FormField>
        <FormField label="Role">
          {(field) => (
            <div className="flex gap-2">
              <select {...field} name="role" className="input" defaultValue="recruiter">
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <button className="btn shrink-0" disabled={createUser.isPending}>
                Buat Akun
              </button>
            </div>
          )}
        </FormField>
      </form>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard label="Total Pengguna" value={(users ?? []).length} icon={UserCog} iconTone="info" />
        <KpiCard label="Aktif" value={activeCount} icon={UserCheck} iconTone="success" />
        <KpiCard label="Nonaktif" value={inactiveCount} icon={UserX} iconTone="neutral" />
      </div>

      <PillTabs tabs={statusTabs} value={statusTab} onChange={setStatusTab} />

      <DataTable
        label="Daftar pengguna"
        rows={filteredUsers}
        columns={userColumns}
        rowKey={(u) => u.id}
        query={usersQuery}
        defaultSort={{ key: "name", dir: "asc" }}
        pageSize={50}
        emptyTitle="Tidak ada pengguna untuk status ini."
      />
    </div>
  );
}
