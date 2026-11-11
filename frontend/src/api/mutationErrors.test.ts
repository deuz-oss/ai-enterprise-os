import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { reportMutationError } from "./mutationErrors";

const toastError = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast: { error: toastError } }));

const plain = { options: {} };

describe("reportMutationError", () => {
  beforeEach(() => toastError.mockClear());

  it("mutasi tanpa penanganan sendiri -> toast pesan backend", () => {
    reportMutationError(new ApiError(409, "Payrol internal periode 2026-10 sudah ada"), plain);
    expect(toastError).toHaveBeenCalledWith("Payrol internal periode 2026-10 sudah ada");
  });

  it("dilewati bila mutasi punya onError atau ditandai errorHandled", () => {
    reportMutationError(new ApiError(409, "x"), { options: { onError: () => undefined } });
    reportMutationError(new ApiError(409, "x"), { options: { meta: { errorHandled: true } } });
    expect(toastError).not.toHaveBeenCalled();
  });

  it("401 & langganan menunggak sudah dialihkan -> tanpa toast", () => {
    reportMutationError(new ApiError(401, "Not authenticated"), plain);
    reportMutationError(new ApiError(403, "Menunggak", "subscription_past_due"), plain);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("403 role -> pesan akses; 402 metered -> pesan backend apa adanya", () => {
    reportMutationError(new ApiError(403, "Role Anda tidak memiliki akses ke fitur ini"), plain);
    expect(toastError).toHaveBeenLastCalledWith("Role Anda tidak punya akses untuk aksi ini.");
    reportMutationError(new ApiError(402, "Saldo tidak cukup", "metered_blocked"), plain);
    expect(toastError).toHaveBeenLastCalledWith("Saldo tidak cukup");
  });

  it("gagal jaringan -> pesan koneksi", () => {
    reportMutationError(new TypeError("Failed to fetch"), plain);
    expect(toastError).toHaveBeenCalledWith(
      "Tidak bisa terhubung ke server. Periksa koneksi lalu coba lagi."
    );
  });
});
