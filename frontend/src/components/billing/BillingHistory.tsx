import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { api, downloadFile, formatDateTime, formatRupiah } from "../../api/client";
import { transactionTypeLabel, type Receipt, type Transaction } from "../../lib/billing";
import { Button, DataTable, type Column } from "../ui";

/** Unduh PDF kwitansi sebagai blob (header Authorization lewat downloadFile). */
function useReceiptDownload() {
  const [busyId, setBusyId] = useState<string | null>(null);
  async function download(id: string, fallbackName: string) {
    setBusyId(id);
    try {
      await downloadFile(`/billing/receipts/${id}/pdf`, fallbackName);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Gagal mengunduh kwitansi");
    } finally {
      setBusyId(null);
    }
  }
  return { busyId, download };
}

export function TransactionsTable() {
  const { busyId, download } = useReceiptDownload();
  const transactions = useQuery({
    queryKey: ["billing-transactions"],
    queryFn: () => api.get<Transaction[]>("/billing/transactions?limit=200"),
  });

  // Tanpa sort: "Sisa Setelah" adalah saldo berjalan, bermakna dalam urutan waktu.
  const columns: Column<Transaction>[] = [
    { key: "time", header: "Waktu", className: "whitespace-nowrap", cell: (t) => formatDateTime(t.created_at) },
    { key: "type", header: "Jenis", cell: (t) => transactionTypeLabel(t.type) },
    {
      key: "event",
      header: "Keterangan",
      cell: (t) => (
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {t.ref_event}
        </span>
      ),
    },
    {
      key: "amount",
      header: "Jumlah",
      numeric: true,
      cell: (t) => (
        <span className={t.amount < 0 ? "" : "text-emerald-700 dark:text-emerald-400"}>
          {t.amount >= 0 ? "+" : ""}
          {formatRupiah(t.amount)}
        </span>
      ),
    },
    { key: "after", header: "Sisa Setelah", numeric: true, cell: (t) => formatRupiah(t.balance_after) },
    {
      key: "receipt",
      header: <span className="sr-only">Kwitansi</span>,
      cell: (t) =>
        t.receipt_id ? (
          <Button
            size="sm"
            variant="ghost"
            icon={<Download className="h-3.5 w-3.5" aria-hidden="true" />}
            loading={busyId === t.receipt_id}
            onClick={() => download(t.receipt_id as string, "kwitansi.pdf")}
          >
            Kwitansi
          </Button>
        ) : null,
    },
  ];

  return (
    <DataTable
      label="Riwayat transaksi saldo"
      rows={transactions.data}
      columns={columns}
      rowKey={(t) => t.id}
      query={transactions}
      pageSize={50}
      emptyTitle="Belum ada transaksi."
    />
  );
}

export function ReceiptsTable() {
  const { busyId, download } = useReceiptDownload();
  const receipts = useQuery({
    queryKey: ["billing-receipts"],
    queryFn: () => api.get<Receipt[]>("/billing/receipts?limit=200"),
  });

  const columns: Column<Receipt>[] = [
    {
      key: "number",
      header: "No. Kwitansi",
      className: "whitespace-nowrap font-mono text-xs",
      cell: (r) => r.receipt_number,
      sortValue: (r) => r.receipt_number,
    },
    {
      key: "issued",
      header: "Tanggal",
      className: "whitespace-nowrap",
      cell: (r) => formatDateTime(r.issued_at),
      sortValue: (r) => r.issued_at,
    },
    { key: "desc", header: "Keterangan", cell: (r) => r.description },
    { key: "method", header: "Dibayar dengan", cell: (r) => r.payment_method_label ?? "-" },
    { key: "total", header: "Total", numeric: true, cell: (r) => formatRupiah(r.total), sortValue: (r) => r.total },
    {
      key: "download",
      header: <span className="sr-only">Unduh</span>,
      cell: (r) => (
        <Button
          size="sm"
          variant="secondary"
          aria-label={`Unduh kwitansi ${r.receipt_number}`}
          icon={<Download className="h-3.5 w-3.5" aria-hidden="true" />}
          loading={busyId === r.id}
          onClick={() => download(r.id, `${r.receipt_number}.pdf`)}
        >
          PDF
        </Button>
      ),
    },
  ];

  return (
    <DataTable
      label="Daftar kwitansi"
      rows={receipts.data}
      columns={columns}
      rowKey={(r) => r.id}
      query={receipts}
      pageSize={50}
      emptyTitle="Belum ada kwitansi."
      emptyDescription="Kwitansi terbit otomatis setiap pembayaran langganan, top up, atau auto-reload berhasil."
    />
  );
}
