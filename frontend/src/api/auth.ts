import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

/** Nilai `UserRole` backend (`backend/app/modules/auth/models.py`). Union, bukan
 * string bebas, supaya salah ketik role di perbandingan langsung ditolak tsc. */
export type UserRole =
  | "admin"
  | "business_dev"
  | "recruiter"
  | "hr"
  | "operations"
  | "finance"
  | "management"
  | "platform_admin"
  | "karyawan";

/** Respons `GET /auth/me` (`UserOut`). */
export interface Me {
  id: string;
  tenant_id: string | null;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  tenant_name: string | null;
}

/**
 * User yang sedang login. Dulu query ini ditulis ulang di 12 tempat dengan
 * 6 bentuk tipe berbeda (`{ role }`, `{ full_name }`, ...) untuk endpoint yang
 * sama (audit 2026-10-08 §4 C2). Satu queryKey `["me"]` = satu cache.
 */
export function useMe(options: { enabled?: boolean; retry?: boolean } = {}) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<Me>("/auth/me"),
    // Identitas & role jarang berubah dalam satu sesi.
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}
