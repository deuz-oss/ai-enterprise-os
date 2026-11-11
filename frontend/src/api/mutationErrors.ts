import { toast } from "sonner";
import { ApiError } from "./client";

// Meta mutasi yang dikenali handler global di bawah.
declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: {
      /** Mutasi ini sudah menampilkan error-nya sendiri (teks inline, atau
       * `onError` di pemanggil `mutate(...)`) -- jangan ditambah toast. */
      errorHandled?: boolean;
    };
  }
}

/**
 * Jaring pengaman: mutasi yang gagal SELALU memberi tahu user.
 *
 * Audit 2026-11-11 (Top-20 #2): 108 dari 223 mutasi tidak punya jalur error
 * sama sekali -- Run Payroll (409), Generate Invoice (422), buat pengguna
 * dengan email duplikat (409) gagal tanpa pesan apa pun. Handler ini menoast
 * pesan backend untuk setiap mutasi yang tidak menanganinya sendiri:
 * - punya `onError` di definisi `useMutation` -> dilewati otomatis;
 * - menampilkan error dengan cara lain -> tandai `meta: { errorHandled: true }`.
 * Mutasi BARU cukup tidak berbuat apa-apa untuk mendapat toast ini.
 */
export function reportMutationError(
  error: unknown,
  mutation: { options: { onError?: unknown; meta?: { errorHandled?: boolean } } }
) {
  if (mutation.options.onError || mutation.options.meta?.errorHandled) return;
  if (error instanceof ApiError) {
    // 401: api/client sudah mengalihkan ke /login. Langganan menunggak:
    // sudah dialihkan ke /billing.
    if (error.status === 401 || error.code === "subscription_past_due") return;
    if (error.status === 403 && !error.code) {
      toast.error("Role Anda tidak punya akses untuk aksi ini.");
      return;
    }
  }
  const message =
    error instanceof TypeError
      ? "Tidak bisa terhubung ke server. Periksa koneksi lalu coba lagi."
      : error instanceof Error && error.message
        ? error.message
        : "Terjadi kesalahan. Coba lagi.";
  toast.error(message);
}
