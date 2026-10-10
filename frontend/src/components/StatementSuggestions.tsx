import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatRupiah } from "../api/client";
import { confirmDialog, QueryState } from "./ui";

/** Respons `GET /accounting/cashbank/statement/{id}/suggestions` (bank_statement.py). */
interface Suggestions {
  line_id: string;
  direction: "masuk" | "keluar";
  amount: number;
  actions: {
    kind: "settle_invoice" | "pay_bill" | "create_transaction";
    label: string;
    reason: string;
    invoice_id?: string;
    bill_id?: string;
    counter_account_id?: string;
  }[];
  bank_accounts: { id: string; code: string; name: string }[];
}

const CONFIRM_TEXT: Record<Suggestions["actions"][number]["kind"], string> = {
  settle_invoice: "Invoice ditandai lunas dengan tanggal mutasi dan jurnal pelunasan diposting.",
  pay_bill: "Bill dibayar dari rekening yang dipilih dan jurnal pembayaran diposting.",
  create_transaction: "Transaksi kas-bank baru dibuat dan jurnalnya diposting.",
};

/**
 * Saran untuk baris rekening koran tanpa pasangan (AI opportunity #6).
 * Deterministik; tidak ada yang diposting sampai user memilih satu aksi dan
 * mengonfirmasinya. Setelah aksi berjalan, baris langsung dicocokkan ke
 * jurnal/transaksi hasilnya.
 */
export function StatementSuggestions({ lineId, onClose }: { lineId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["statement-suggestions", lineId],
    queryFn: () => api.get<Suggestions>(`/accounting/cashbank/statement/${lineId}/suggestions`),
  });
  const data = query.data;
  const [bankId, setBankId] = useState("");
  const bankAccount = bankId || data?.bank_accounts.find((a) => a.code === "1-1100")?.id || data?.bank_accounts[0]?.id || "";

  const apply = useMutation({
    mutationFn: (action: Suggestions["actions"][number]) =>
      api.post<{ status: string; warning?: string }>(`/accounting/cashbank/statement/${lineId}/apply`, {
        ...action,
        bank_account_id: bankAccount,
      }),
    onSuccess: () => {
      for (const key of ["bank-statement", "invoices", "invoices-aging", "aging", "purchase-bills", "bank-transactions", "journal"]) {
        void qc.invalidateQueries({ queryKey: [key] });
      }
    },
  });

  const needsBank = (data?.actions ?? []).some((a) => a.kind !== "settle_invoice");

  return (
    <section className="space-y-2 text-sm" aria-label="Saran untuk mutasi tanpa pasangan" style={{ color: "var(--text)" }}>
      <div className="flex items-center justify-between gap-2">
        <p className="font-medium">
          Saran untuk mutasi {data ? `${data.direction} ${formatRupiah(data.amount)}` : ""}
        </p>
        <button type="button" className="btn-secondary px-2 py-0.5 text-xs" onClick={onClose}>
          Tutup
        </button>
      </div>
      <QueryState query={query} compact>
        {data &&
          (data.actions.length === 0 ? (
            <p style={{ color: "var(--th-color)" }}>
              Tidak ada invoice, bill, atau mutasi serupa yang cocok. Catat manual lewat Kas &amp; Bank, atau abaikan.
            </p>
          ) : (
            <>
              {needsBank && (
                <label className="flex items-center gap-2 text-xs">
                  <span style={{ color: "var(--th-color)" }}>Rekening</span>
                  <select className="input w-auto py-1 text-xs" value={bankAccount} onChange={(e) => setBankId(e.target.value)}>
                    {data.bank_accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code} {a.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <ul className="space-y-1.5">
                {data.actions.map((action) => (
                  <li key={`${action.kind}-${action.invoice_id ?? action.bill_id ?? action.counter_account_id}`} className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="btn-secondary px-2 py-0.5 text-xs"
                      disabled={apply.isPending}
                      onClick={() =>
                        confirmDialog({
                          title: `${action.label}?`,
                          message: `${CONFIRM_TEXT[action.kind]} Mutasi ini lalu tercocok ke jurnalnya.`,
                          confirmLabel: "Terapkan",
                          tone: "primary",
                          onConfirm: () => apply.mutate(action),
                        })
                      }
                    >
                      {action.label}
                    </button>
                    <span className="text-xs" style={{ color: "var(--th-color)" }}>
                      {action.reason}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ))}
      </QueryState>
      {apply.data?.warning === "jurnal_gagal" && (
        <p role="alert" className="text-xs text-amber-700 dark:text-amber-400">
          Aksi berhasil, tetapi jurnalnya tidak terbentuk (aturan jurnal nonaktif?) sehingga mutasi belum tercocok.
        </p>
      )}
      {apply.error && (
        <p role="alert" className="text-xs text-rose-700 dark:text-rose-400">
          {(apply.error as Error).message}
        </p>
      )}
    </section>
  );
}
