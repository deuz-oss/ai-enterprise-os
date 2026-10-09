import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Sparkles } from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { QueryState } from "./ui";

/** Respons `GET /finance/invoices/{id}/reconciliation` (backend finance/reconciliation.py). */
export interface InvoiceReconciliation {
  invoice_id: string;
  invoice_no: string;
  period: string;
  run_id: string | null;
  run_status: string | null;
  totals: {
    headcount_billed: number;
    headcount_approved: number;
    overtime_billed: number;
    overtime_approved: number;
    payroll_billed: number;
    payroll_current: number | null;
  };
  findings: {
    severity: "high" | "medium" | "info";
    kind: string;
    employee_id: string | null;
    employee_name: string | null;
    message: string;
  }[];
  findings_total: number;
  summary: string | null;
  summary_source: "ai" | "none";
}

const SEVERITY: Record<InvoiceReconciliation["findings"][number]["severity"], { label: string; cls: string }> = {
  high: { label: "Kritis", cls: "pill p-red" },
  medium: { label: "Cek", cls: "pill p-orange" },
  info: { label: "Info", cls: "pill p-gray" },
};

const SHOWN = 10;

/**
 * Panel rekonsiliasi invoice ↔ absensi disetujui klien, tampil sebagai baris
 * ekspansi di tabel invoice. Angka & temuan dihitung backend secara
 * deterministik; ringkasan AI (bila ada) hanya merangkum temuan yang sama dan
 * diberi label. Tidak ada yang diubah otomatis.
 */
export function InvoiceReconciliationPanel({ invoiceId, onClose }: { invoiceId: string; onClose: () => void }) {
  const query = useQuery({
    queryKey: ["invoice-reconciliation", invoiceId],
    queryFn: () => api.get<InvoiceReconciliation>(`/finance/invoices/${invoiceId}/reconciliation`),
  });
  const rec = query.data;

  return (
    <section className="space-y-3 text-sm" aria-label="Rekonsiliasi invoice dengan absensi" style={{ color: "var(--text)" }}>
      <div className="flex items-center justify-between gap-2">
        <p className="font-medium">Cek tagihan vs absensi disetujui</p>
        <button type="button" className="btn-secondary px-2 py-0.5 text-xs" onClick={onClose}>
          Tutup
        </button>
      </div>
      <QueryState query={query} compact>
        {rec && (
          <>
            <table className="w-full max-w-xl">
              <thead>
                <tr>
                  <th className="th">Periode {rec.period}</th>
                  <th className="th num">Ditagih</th>
                  <th className="th num">Absensi disetujui / slip kini</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="td">Headcount</td>
                  <td className="td num">{rec.totals.headcount_billed}</td>
                  <td className="td num">{rec.totals.headcount_approved}</td>
                </tr>
                <tr>
                  <td className="td">Jam lembur</td>
                  <td className="td num">{rec.totals.overtime_billed}</td>
                  <td className="td num">{rec.totals.overtime_approved}</td>
                </tr>
                <tr>
                  <td className="td">Payroll</td>
                  <td className="td num">{formatRupiah(rec.totals.payroll_billed)}</td>
                  <td className="td num">
                    {rec.totals.payroll_current === null ? "-" : formatRupiah(rec.totals.payroll_current)}
                  </td>
                </tr>
              </tbody>
            </table>

            {rec.summary && (
              <div className="rounded-lg p-3" style={{ backgroundColor: "var(--accent-tint)" }}>
                <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--th-color)" }}>
                  <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Ringkasan AI (dari temuan di bawah)
                </p>
                <p>{rec.summary}</p>
              </div>
            )}

            {rec.findings_total === 0 ? (
              <p className="flex items-center gap-1.5" style={{ color: "var(--th-color)" }}>
                <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                Cocok -- headcount, lembur, dan total payroll sesuai absensi yang disetujui.
              </p>
            ) : (
              <ul className="space-y-1.5" aria-label="Temuan rekonsiliasi">
                {rec.findings.slice(0, SHOWN).map((f, i) => (
                  <li key={`${f.kind}-${f.employee_id ?? i}`} className="flex items-start gap-2">
                    <span className={`${SEVERITY[f.severity].cls} shrink-0`}>{SEVERITY[f.severity].label}</span>
                    <span>
                      {f.employee_name && <span className="font-medium">{f.employee_name}: </span>}
                      {f.message}
                    </span>
                  </li>
                ))}
                {rec.findings_total > SHOWN && (
                  <li style={{ color: "var(--th-color)" }}>dan {rec.findings_total - SHOWN} temuan lain.</li>
                )}
              </ul>
            )}
          </>
        )}
      </QueryState>
    </section>
  );
}
