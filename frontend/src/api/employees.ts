import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

/** Batas maksimum `limit` di `GET /employees` (backend `hrd/router.py`, `le=1000`). */
export const EMPLOYEE_LOOKUP_LIMIT = 1000;

/**
 * Daftar karyawan untuk lookup nama / dropdown / hitungan lintas halaman.
 *
 * Dulu tiap halaman memanggil `/employees` sendiri; yang lupa memberi `limit`
 * diam-diam kena default backend 200 -- Payroll & Absensi lalu menghitung
 * "karyawan aktif" dan preflight anomali dari daftar terpotong tanpa tanda apa
 * pun (audit 2026-10-08 §8 D1). Hook ini selalu minta batas maksimum dan
 * mengembalikan `truncated` kalau total di server (`X-Total-Count`) masih lebih
 * besar, supaya halaman wajib memberi tahu user.
 *
 * `T` cukup subset field yang dipakai halaman; respons aslinya `EmployeeOut` penuh.
 */
export function useEmployeeLookup<T>() {
  const query = useQuery({
    queryKey: ["employees-lookup"],
    queryFn: () => api.getPaged<T>(`/employees?limit=${EMPLOYEE_LOOKUP_LIMIT}`),
  });
  const rows = query.data?.data;
  const total = query.data?.total ?? 0;
  return {
    ...query,
    data: rows,
    total,
    truncated: rows !== undefined && total > rows.length,
  };
}
