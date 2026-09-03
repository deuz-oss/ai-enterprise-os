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
                      className="font-medium text-[var(--n-text-muted)] hover:text-[var(--n-text)]"
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

interface ChecklistFinding {
  code: string;
  severity: string;
  detail: string;
  items: string[];
}

function CloseChecklistCard() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const checklist = useQuery({
    queryKey: ["close-checklist", year, month],
    queryFn: () =>
      api.get<{
        period: string;
        ready_to_close: boolean;
        errors: number;
        warnings: number;
        findings: ChecklistFinding[];
      }>(`/accounting/ai/close-checklist?year=${year}&month=${month}`),
  });

  return (
    <div className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">✅ Checklist Tutup Buku</h3>
          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
            Deteksi deterministik (tanpa LLM) sebelum periode ditutup.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-20 text-xs" />
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="input w-auto text-xs">
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>
      {checklist.data && (
        <>
          <span className={`badge ${checklist.data.ready_to_close ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
            {checklist.data.ready_to_close ? "Siap ditutup" : `${checklist.data.errors} error, ${checklist.data.warnings} warning`}
          </span>
          <ul className="space-y-1.5 text-xs">
            {checklist.data.findings.map((f, i) => (
              <li key={i} className={f.severity === "error" ? "text-red-600" : "text-amber-600"}>
                <span className="font-medium">[{f.severity}]</span> {f.detail}
              </li>
            ))}
            {checklist.data.findings.length === 0 && (
              <li style={{ color: "var(--n-text-muted)" }}>Tidak ada temuan.</li>
            )}
          </ul>
        </>
      )}
    </div>
  );
}

interface Anomaly {
  type: string;
  severity: string;
  detail: string;
  vendor?: string;
  amount?: number;
}

function AnomaliesCard() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const anomalies = useQuery({
    queryKey: ["ai-anomalies", year, month],
    queryFn: () =>
      api.get<{ period: string; total_anomalies: number; high_severity: number; anomalies: Anomaly[] }>(
        `/accounting/ai/anomalies?year=${year}&month=${month}`
      ),
  });

  return (
    <div className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">🚨 Deteksi Anomali</h3>
          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
            Duplikasi bill, transaksi besar tak wajar, ketidaksesuaian PPN.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-20 text-xs" />
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="input w-auto text-xs">
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>
      <ul className="space-y-1.5 text-xs">
        {(anomalies.data?.anomalies ?? []).map((a, i) => (
          <li key={i} className={a.severity === "high" ? "font-medium text-red-600" : "text-amber-600"}>
            [{a.severity}] {a.detail}
          </li>
        ))}
        {anomalies.data?.anomalies.length === 0 && (
          <li style={{ color: "var(--n-text-muted)" }}>Tidak ada anomali terdeteksi.</li>
        )}
      </ul>
    </div>
  );
}

function ExecutiveSummaryCard() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState<number | "">(now.getMonth() + 1);
  const summary = useQuery({
    queryKey: ["exec-summary", year, month],
    queryFn: () =>
      api.get<{
        period: string;
        metrics: { total_revenue: number; total_expense: number; net_income: number; active_clients: number };
        narrative: string;
      }>(`/accounting/ai/executive-summary?year=${year}${month ? `&month=${month}` : ""}`),
    enabled: false,
  });

  return (
    <div className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">📋 Ringkasan Eksekutif</h3>
          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
            Narasi otomatis dari data terverifikasi (LLM opsional).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-20 text-xs" />
          <select
            value={month}
            onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : "")}
            className="input w-auto text-xs"
          >
            <option value="">Setahun</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <button className="btn-secondary py-1 text-xs" disabled={summary.isFetching} onClick={() => summary.refetch()}>
            {summary.isFetching ? "Memuat..." : "Buat Ringkasan"}
          </button>
        </div>
      </div>
      {summary.data && (
        <>
          <p className="whitespace-pre-line text-xs" style={{ color: "var(--n-text)" }}>{summary.data.narrative}</p>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div>
              <p style={{ color: "var(--n-text-muted)" }}>Pendapatan</p>
              <p className="font-semibold">{formatRupiah(summary.data.metrics.total_revenue)}</p>
            </div>
            <div>
              <p style={{ color: "var(--n-text-muted)" }}>Beban</p>
              <p className="font-semibold">{formatRupiah(summary.data.metrics.total_expense)}</p>
            </div>
            <div>
              <p style={{ color: "var(--n-text-muted)" }}>Laba Bersih</p>
              <p className="font-semibold">{formatRupiah(summary.data.metrics.net_income)}</p>
            </div>
            <div>
              <p style={{ color: "var(--n-text-muted)" }}>Klien Aktif</p>
              <p className="font-semibold">{summary.data.metrics.active_clients}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function AskReportCard() {
  const [question, setQuestion] = useState("");
  const ask = useMutation({
    mutationFn: () =>
      api.post<{ question: string; answer: string; context: string[] }>("/accounting/ai/ask", {
        question,
        year: new Date().getFullYear(),
      }),
  });

  return (
    <div className="card space-y-3 p-4">
      <div>
        <h3 className="text-sm font-semibold">💬 Tanya Laporan</h3>
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          Tanya soal laba rugi, neraca, margin klien, atau saldo -- kata kunci: "laba rugi",
          "neraca", "klien", "saldo".
        </p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) ask.mutate();
        }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Contoh: bagaimana laba rugi tahun ini?"
          className="input flex-1 text-xs"
        />
        <button type="submit" disabled={ask.isPending || !question.trim()} className="btn-secondary text-xs">
          Tanya
        </button>
      </form>
      {ask.error && <p className="text-xs text-red-600">{(ask.error as Error).message}</p>}
      {ask.data && (
        <p className="whitespace-pre-line rounded p-2 text-xs" style={{ backgroundColor: "var(--n-hover)" }}>
          {ask.data.answer}
        </p>
      )}
    </div>
  );
}

interface LedgerLine {
  entry_id: string;
  entry_date: string;
  description: string;
  reference: string | null;
  debit: number;
  credit: number;
  balance: number;
}

function LedgerCard() {
  const [accountCode, setAccountCode] = useState("");
  const [activeCode, setActiveCode] = useState("");
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const ledger = useQuery({
    queryKey: ["ledger", activeCode, year],
    queryFn: () =>
      api.get<{ account: string; account_name: string; year: number; lines: LedgerLine[] }>(
        `/accounting/ledger/${activeCode}?year=${year}`
      ),
    enabled: !!activeCode,
  });

  return (
    <div className="card space-y-3 p-4">
      <div>
        <h3 className="text-sm font-semibold">📖 Buku Besar per Akun</h3>
        <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>
          Mutasi jurnal posted + saldo berjalan untuk satu kode akun.
        </p>
      </div>
      <div className="flex gap-2">
        <input
          value={accountCode}
          onChange={(e) => setAccountCode(e.target.value)}
          placeholder="Kode akun (mis. 1-1100)"
          className="input text-xs"
        />
        <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-20 text-xs" />
        <button
          className="btn-secondary text-xs"
          disabled={!accountCode}
          onClick={() => setActiveCode(accountCode)}
        >
          Tampilkan
        </button>
      </div>
      {ledger.error && <p className="text-xs text-red-600">{(ledger.error as Error).message}</p>}
      {ledger.data && (
        <table className="w-full text-xs">
          <thead style={{ backgroundColor: "var(--n-hover)" }}>
            <tr>
              <th className="th">Tanggal</th>
              <th className="th">Keterangan</th>
              <th className="th">Debit</th>
              <th className="th">Kredit</th>
              <th className="th">Saldo</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {ledger.data.lines.map((l) => (
              <tr key={l.entry_id}>
                <td className="td whitespace-nowrap">{l.entry_date}</td>
                <td className="td max-w-[220px] truncate">{l.description}</td>
                <td className="td">{l.debit > 0 ? formatRupiah(l.debit) : "-"}</td>
                <td className="td">{l.credit > 0 ? formatRupiah(l.credit) : "-"}</td>
                <td className="td font-medium">{formatRupiah(l.balance)}</td>
              </tr>
            ))}
            {ledger.data.lines.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-6 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Tidak ada mutasi tahun ini.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

interface BalanceSheetRow {
  account_code: string;
  account_name: string;
  amount: number;
}

function BalanceSheetCard() {
  const [asOf, setAsOf] = useState(() => new Date().toISOString().slice(0, 10));
  const [activeAsOf, setActiveAsOf] = useState("");
  const bs = useQuery({
    queryKey: ["balance-sheet", activeAsOf],
    queryFn: () =>
      api.get<{
        as_of: string;
        assets: { rows: BalanceSheetRow[]; total: number };
        liabilities: { rows: BalanceSheetRow[]; total: number };
        equity: { rows: BalanceSheetRow[]; total: number };
        net_income: number;
      }>(`/accounting/reports/balance-sheet?as_of=${activeAsOf}`),
    enabled: !!activeAsOf,
  });

  function Section({ title, rows, total }: { title: string; rows: BalanceSheetRow[]; total: number }) {
    return (
      <div>
        <h4 className="text-xs font-semibold" style={{ color: "var(--n-text)" }}>{title}</h4>
        <ul className="mt-1 space-y-0.5 text-xs">
          {rows.map((r) => (
            <li key={r.account_code} className="flex justify-between">
              <span style={{ color: "var(--n-text-muted)" }}>{r.account_name}</span>
              <span>{formatRupiah(r.amount)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-1 flex justify-between border-t pt-1 text-xs font-semibold" style={{ borderColor: "var(--n-border)" }}>
          <span>Total {title}</span>
          <span>{formatRupiah(total)}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">⚖️ Neraca</h3>
          <p className="text-xs" style={{ color: "var(--n-text-muted)" }}>Posisi keuangan per tanggal.</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} className="input text-xs" />
          <button className="btn-secondary text-xs" onClick={() => setActiveAsOf(asOf)}>
            Tampilkan
          </button>
        </div>
      </div>
      {bs.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Section title="Aset" rows={bs.data.assets.rows} total={bs.data.assets.total} />
          <Section title="Liabilitas" rows={bs.data.liabilities.rows} total={bs.data.liabilities.total} />
          <Section title="Ekuitas" rows={bs.data.equity.rows} total={bs.data.equity.total} />
        </div>
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
      <CloseChecklistCard />
      <AnomaliesCard />
      <ExecutiveSummaryCard />
      <AskReportCard />
      <BalanceSheetCard />
      <LedgerCard />
    </div>
  );
}
