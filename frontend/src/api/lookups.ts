import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

/**
 * Lookup baca-saja untuk dropdown lintas modul (audit 2026-11-11 Top-20 #1).
 *
 * Dulu halaman Finance, Job Orders, Payroll, dll. memanggil `GET /clients`
 * (khusus role CRM) hanya untuk mengisi dropdown -- role finance/recruiter/HR
 * mendapat 403 sehingga dropdown kosong tanpa pesan dan alur utamanya macet.
 * Endpoint `/options` hanya mengembalikan id + nama dan dibuka untuk role yang
 * alurnya memang butuh memilih (lihat `backend/app/core/permissions.py`).
 */

export interface ClientOption {
  id: string;
  name: string;
}

export const CLIENT_OPTIONS_KEY = ["client-options"] as const;

export function useClientOptions(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: CLIENT_OPTIONS_KEY,
    queryFn: () => api.get<ClientOption[]>("/clients/options"),
    enabled: options?.enabled ?? true,
  });
}

export interface ClientSiteOption {
  id: string;
  client_name: string;
  name: string;
  radius_meters: number;
}

export function useClientSiteOptions(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["client-site-options"],
    queryFn: () => api.get<ClientSiteOption[]>("/clients/site-options"),
    enabled: options?.enabled ?? true,
  });
}

export interface UserOption {
  id: string;
  full_name: string;
}

/** Anggota tim aktif (pemilik lead, pewawancara) -- nama saja, bukan daftar akun. */
export function useUserOptions(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["user-options"],
    queryFn: () => api.get<UserOption[]>("/auth/users/options"),
    enabled: options?.enabled ?? true,
  });
}
