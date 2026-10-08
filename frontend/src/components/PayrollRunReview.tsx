import { Sparkles } from "lucide-react";
import { formatRupiah } from "../api/client";

/** Respons `GET /payroll/runs/{id}/review` (backend payroll/review.py). */
export interface RunReview {
  run_id: string;
  period: string;
  compared_to: { run_id: string; period: string } | null;
  totals: Record<"gross" | "net" | "pph21" | "slips", { current: number; previous: number | null }>;
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

const SEVERITY: Record<RunReview["findings"][number]["severity"], { label: string; cls: string }> = {
  high: { label: "Kritis", cls: "pill p-red" },
  medium: { label: "Cek", cls: "pill p-orange" },
  info: { label: "Info", cls: "pill p-gray" },
};

const TOTAL_ROWS: { key: keyof RunReview["totals"]; label: string; money: boolean }[] = [
  { key: "gross", label: "Bruto", money: true },
  { key: "net", label: "Net (dibayar)", money: true },
  { key: "pph21", label: "PPh21", money: true },
  { key: "slips", label: "Jumlah slip", money: false },
];

const SHOWN = 10;

/**
 * Isi dialog Finalisasi (audit 2026-10-08 Phase 6): apa yang berubah dibanding
 * run final sebelumnya. Angka & temuan dihitung backend secara deterministik;
 * ringkasan AI (bila ada) hanya merangkum temuan yang sama dan diberi label.
 */
export function PayrollRunReview({ review }: { review: RunReview }) {
  const fmt = (v: number | null, money: boolean) =>
    v === null ? "-" : money ? formatRupiah(v) : v.toLocaleString("id-ID");
  return (
    <div className="space-y-3 text-sm" style={{ color: "var(--text)" }}>
      <p className="font-medium">
        Tinjauan {review.period}
        {review.compared_to ? ` dibanding run final ${review.compared_to.period}` : " (belum ada run final sebelumnya)"}
      </p>

      <table className="w-full">
        <thead>
          <tr>
            <th className="th">Total</th>
            <th className="th num">Sekarang</th>
            <th className="th num">Sebelumnya</th>
            <th className="th num">Selisih</th>
          </tr>
        </thead>
        <tbody>
          {TOTAL_ROWS.map(({ key, label, money }) => {
            const t = review.totals[key];
            const delta = t.previous === null ? null : t.current - t.previous;
            return (
              <tr key={key}>
                <td className="td">{label}</td>
                <td className="td num">{fmt(t.current, money)}</td>
                <td className="td num">{fmt(t.previous, money)}</td>
                <td className="td num">{delta === null ? "-" : `${delta > 0 ? "+" : ""}${fmt(delta, money)}`}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {review.summary && (
        <div className="rounded-lg p-3" style={{ backgroundColor: "var(--accent-tint)" }}>
          <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--th-color)" }}>
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Ringkasan AI (dari temuan di bawah)
          </p>
          <p>{review.summary}</p>
        </div>
      )}

      {review.findings_total === 0 ? (
        <p style={{ color: "var(--th-color)" }}>Tidak ada temuan -- tidak ada perubahan besar per karyawan.</p>
      ) : (
        <ul className="space-y-1.5" aria-label="Temuan tinjauan">
          {review.findings.slice(0, SHOWN).map((f, i) => (
            <li key={`${f.kind}-${f.employee_id ?? i}`} className="flex items-start gap-2">
              <span className={`${SEVERITY[f.severity].cls} shrink-0`}>{SEVERITY[f.severity].label}</span>
              <span>
                {f.employee_name && <span className="font-medium">{f.employee_name}: </span>}
                {f.message}
              </span>
            </li>
          ))}
          {review.findings_total > SHOWN && (
            <li style={{ color: "var(--th-color)" }}>dan {review.findings_total - SHOWN} temuan lain.</li>
          )}
        </ul>
      )}
    </div>
  );
}
