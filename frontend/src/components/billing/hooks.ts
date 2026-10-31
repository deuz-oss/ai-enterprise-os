import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../api/client";
import { renewalOutcome, type BillingStatus, type RetryRenewalResult } from "../../lib/billing";

/** Semua query billing yang dipengaruhi pembayaran -- dipakai setelah aksi bayar. */
export const BILLING_QUERY_KEYS = [
  ["billing-status"],
  ["billing-balance"],
  ["billing-transactions"],
  ["billing-auto-reload"],
  ["billing-payment-methods"],
  ["billing-receipts"],
] as const;

export function useInvalidateBilling() {
  const qc = useQueryClient();
  return () => {
    for (const key of BILLING_QUERY_KEYS) void qc.invalidateQueries({ queryKey: key });
  };
}

export function useBillingStatus() {
  return useQuery({
    queryKey: ["billing-status"],
    queryFn: () => api.get<BillingStatus>("/billing/status"),
  });
}

/** "Bayar sekarang" untuk tunggakan/perpanjangan: charge metode bayar default
 * (atau yang dipilih), atau buat invoice lalu redirect ke checkout. */
export function useRetryRenewal() {
  const invalidate = useInvalidateBilling();
  return useMutation({
    mutationFn: (paymentMethodId?: string) =>
      api.post<RetryRenewalResult>(
        "/billing/subscription/retry-renewal",
        paymentMethodId ? { payment_method_id: paymentMethodId } : {}
      ),
    onSuccess: (res) => {
      const outcome = renewalOutcome(res);
      if (outcome.kind === "redirect") {
        window.location.href = outcome.url;
        return;
      }
      if (outcome.kind === "success") toast.success(outcome.message);
      else if (outcome.kind === "pending") toast.info(outcome.message);
      else toast.error(outcome.message);
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Gagal memproses pembayaran"),
  });
}
