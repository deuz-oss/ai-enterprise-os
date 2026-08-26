import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile, formatRupiah } from "../api/client";

interface OcrDraft {
  draft: {
    vendor_name: string;
    bill_number: string | null;
    amount: number;
    ppn_rate: number;
    entry_date: string | null;
    due_date: string | null;
    description: string | null;
  };
  category_suggestions: { account_code: string; account_name: string; matched_keyword: string }[];
}

interface StatementLine {
  id: string;
  tx_date: string;
  description: string | null;
  amount_in: number;
  amount_out: number;
  status: string;
  match_score: number;
  match_reason: string | null;
  suggested_tx_id: string | null;
  suggested_tx_description: string | null;
  matched_tx_id: string | null;
}

interface PredictionRow {
  client_id: string;
  client_name: string;
  risk_score: number;
  risk_basis: string;
  avg_delay_days: number;
  late_ratio: number;
  open_invoices: number;
  outstanding_total: number;
  overdue_total: number;
  priority_score: number;
}

const STATUS_LABEL: Record<string, string> = {
  belum_cocok: "Belum cocok",
  usulan: "Usulan",
  tercocok: "Tercocok",
  diabaikan: "Diabaikan",
};

function riskColor(score: number): string {
  if (score >= 70) return "text-red-600";
  if (score >= 40) return "text-amber-600";
  return "text-emerald-600";
}

function ScanFakturCard() {
  const [result, setResult] = useState<OcrDraft | null>(null);
  const scan = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.upload<OcrDraft>("/accounting/ai/ocr-bill", fd);
    },
    onSuccess: setResult,
  });

  return (
    <div className="card space-y-3 p-4">
      <div>
        <h3 className="text-sm font-semibold">📷 Scan Faktur (OCR + Auto-kategori)</h3>
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          Foto faktur/nota → draft pembelian + saran COA. Butuh AI dikonfigurasi
          (AI_BASE_URL). Buat bill dari draft lewat tab Pembelian.
        </p>
      </div>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="input text-xs"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) scan.mutate(f);
        }}
      />
      {scan.isPending && <p className="text-xs">Membaca faktur…</p>}
      {scan.error && (
        <p className="text-xs text-red-600">{(scan.error as Error).message}</p>
      )}
      {result && (
        <div className="rounded p-3 text-xs" style={{ backgroundColor: "var(--n-hover)" }}>
          <p className="font-semibold">{result.draft.vendor_name}</p>
          <p>
            DPP Rp{result.draft.amount.toLocaleString("id-ID")} · PPN{" "}
            {(result.draft.ppn_rate * 100).toFixed(0)}%
            {result.draft.bill_number ? ` · No. ${result.draft.bill_number}` : ""}
          </p>
          {result.draft.entry_date && <p>Tanggal: {result.draft.entry_date}</p>}
          {result.category_suggestions.length > 0 && (
            <p className="mt-1">
              Saran COA:{" "}
              {result.category_suggestions
                .map((s) => `${s.account_code} — ${s.account_name}`)
                .join(" · ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function RekonsiliasiCard() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const lines = useQuery({
    queryKey: ["bank-statement"],
    queryFn: () =>
      api.get<StatementLine[]>(
        "/accounting/cashbank/statement"
      ),
  });
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["bank-statement"] });

  const importCsv = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.upload<{ inserted: number; failed: unknown[]; duplicates: unknown[] }>(
        "/accounting/cashbank/statement/import",
        fd,
      );
    },
    onSuccess: invalidate,
  });

  const confirm = useMutation({
    mutationFn: (p: { lineId: string; txId: string }) =>
      api.post(`/accounting/cashbank/statement/${p.lineId}/match`, {
        bank_transaction_id: p.txId,
      }),
    onSuccess: invalidate,
  });
  const ignore = useMutation({
    mutationFn: (lineId: string) =>
      api.post(`/accounting/cashbank/statement/${lineId}/ignore`, {}),
    onSuccess: invalidate,
  });

  return (
    <div className="card space-y-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">🧾 Rekonsiliasi Bank Cerdas</h3>
          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
            Impor mutasi rekening koran; sistem mengusulkan pasangan transaksi
            secara deterministik dan menjelaskan yang tidak cocok.
          </p>
        </div>
        <button
          onClick={() => void downloadFile("/accounting/cashbank/statement/template")}
          className="whitespace-nowrap text-xs font-medium text-blue-600 hover:text-blue-800"
        >
          Template CSV
        </button>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".csv,text/csv"
        className="input text-xs"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) importCsv.mutate(f);
        }}
      />
      {importCsv.isPending && <p className="text-xs">Mengimpor…</p>}
      {importCsv.error && (
        <p className="text-xs text-red-600">{(importCsv.error as Error).message}</p>
      )}
      {importCsv.data && (
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          {importCsv.data.inserted} baris diimpor
          {importCsv.data.duplicates.length > 0 &&
            ` · ${importCsv.data.duplicates.length} duplikat dilewati`}
          {importCsv.data.failed.length > 0 && ` · ${importCsv.data.failed.length} gagal`}
        </p>
      )}

      <table className="w-full text-xs">
        <thead style={{ backgroundColor: "var(--n-hover)" }}>
          <tr>
            <th className="th">Tanggal</th>
            <th className="th">Keterangan</th>
            <th className="th">Masuk</th>
            <th className="th">Keluar</th>
            <th className="th">Status</th>
            <th className="th">Aksi</th>
          </tr>
        </thead>
        <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
          {(lines.data ?? []).map((ln) => (
            <tr key={ln.id}>
              <td className="td whitespace-nowrap">{ln.tx_date}</td>
              <td className="td max-w-[180px] truncate">{ln.description ?? "-"}</td>
              <td className="td text-emerald-700">
                {ln.amount_in ? formatRupiah(ln.amount_in) : "—"}
              </td>
              <td className="td text-rose-600">
                {ln.amount_out ? formatRupiah(ln.amount_out) : "—"}
              </td>
              <td className="td">
                <span className={`badge ${ln.status === "usulan" ? "bg-amber-100 text-amber-700" : ln.status === "tercocok" ? "bg-emerald-100 text-emerald-700" : ""}`}>
                  {STATUS_LABEL[ln.status] ?? ln.status}
                  {ln.status === "usulan" && ` ${Math.round(ln.match_score * 100)}%`}
                </span>
                {ln.match_reason && (
                  <p className="mt-0.5 max-w-[220px]" style={{ color: "var(--n-text-muted)" }}>
                    {ln.match_reason}
                  </p>
                )}
              </td>
              <td className="td whitespace-nowrap">
                {ln.status === "usulan" && ln.suggested_tx_id && (
                  <button
                    onClick={() =>
                      confirm.mutate({ lineId: ln.id, txId: ln.suggested_tx_id! })
                    }
                    disabled={confirm.isPending}
                    className="font-medium text-emerald-600 hover:text-emerald-800"
                  >
                    Cocokkan
                  </button>
                )}
                {ln.status !== "matched" && ln.status !== "diabaikan" && ln.status !== "tercocok" && (
                  <>
                    {ln.status === "usulan" && " · "}
                    <button
                      onClick={() => ignore.mutate(ln.id)}
                      disabled={ignore.isPending}
                      className="font-medium text-slate-500 hover:text-slate-800"
                    >
                      Abaikan
                    </button>
                  </>
                )}
                {ln.status === "tercocok" && <span>✓</span>}
              </td>
            </tr>
          ))}
          {lines.data?.length === 0 && (
            <tr>
              <td colSpan={6} className="td py-6 text-center" style={{ color: "var(--n-text-muted)" }}>
                Belum ada rekening koran diimpor.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function PrediksiKlienCard() {
  const prediksi = useQuery({
    queryKey: ["payment-prediction"],
    queryFn: () =>
      api.get<{ clients_ranked: PredictionRow[]; summary: { total_outstanding: number; total_overdue: number } }>(
        "/accounting/ai/payment-prediction",
      ),
  });

  return (
    <div className="card space-y-3 p-4">
      <div>
        <h3 className="text-sm font-semibold">🔮 Prediksi Pembayaran Klien</h3>
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          Skor risiko telat bayar dari histori invoice → prioritas collection.
        </p>
      </div>
      <table className="w-full text-xs">
        <thead style={{ backgroundColor: "var(--n-hover)" }}>
          <tr>
            <th className="th">Klien</th>
            <th className="th">Risiko</th>
            <th className="th">Dasar Skor</th>
            <th className="th">Outstanding</th>
            <th className="th">Overdue</th>
            <th className="th">Prioritas</th>
          </tr>
        </thead>
        <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
          {(prediksi.data?.clients_ranked ?? []).map((r) => (
            <tr key={r.client_id}>
              <td className="td font-medium">{r.client_name}</td>
              <td className={`td font-semibold ${riskColor(r.risk_score)}`}>
                {r.risk_score}/100
              </td>
              <td className="td" style={{ color: "var(--n-text-muted)" }}>
                {r.risk_basis}
              </td>
              <td className="td">{formatRupiah(r.outstanding_total)}</td>
              <td className={`td ${r.overdue_total > 0 ? "font-semibold text-red-600" : ""}`}>
                {formatRupiah(r.overdue_total)}
              </td>
              <td className="td">{formatRupiah(r.priority_score)}</td>
            </tr>
          ))}
          {prediksi.data?.clients_ranked.length === 0 && (
            <tr>
              <td colSpan={6} className="td py-6 text-center" style={{ color: "var(--n-text-muted)" }}>
                Tidak ada invoice berjalan.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {prediksi.data && (
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          Total outstanding {formatRupiah(prediksi.data.summary.total_outstanding)} · overdue{" "}
          {formatRupiah(prediksi.data.summary.total_overdue)}
        </p>
      )}
    </div>
  );
}

export default function AccountingAi() {
  return (
    <div className="space-y-4">
      <ScanFakturCard />
      <RekonsiliasiCard />
      <PrediksiKlienCard />
    </div>
  );
}
