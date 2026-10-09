import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { api, formatRupiah } from "../api/client";

/** Respons `/quotations/pricing-check` (backend presales/pricing.py). */
export interface PricingCheck {
  applicable: boolean;
  roles: Record<string, string>;
  per_head: {
    base_salary: number;
    allowance: number;
    bpjs_employer: number;
    cost: number;
    fee: number | null;
    price: number;
    margin: number;
    margin_pct: number | null;
  } | null;
  monthly: { headcount: number; price: number; cost: number; margin: number } | null;
  history: { count: number; last_fee_pct: number; median_fee_pct: number } | null;
  min_margin_pct: number;
  findings: { severity: "high" | "medium" | "info"; kind: string; message: string }[];
}

const SEVERITY: Record<PricingCheck["findings"][number]["severity"], { label: string; cls: string }> = {
  high: { label: "Rugi", cls: "pill p-red" },
  medium: { label: "Cek", cls: "pill p-orange" },
  info: { label: "Info", cls: "pill p-gray" },
};

const pct = (v: number) => `${(v * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;

/** Nilai yang baru stabil setelah `ms` tanpa perubahan (hindari request per ketukan). */
function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

/**
 * Pengaman margin quotation (AI opportunity #7). Biaya = gaji + tunjangan +
 * BPJS perusahaan (tarif Rates), dihitung deterministik di backend; hanya
 * peringatan, tidak memblokir simpan/approve. Tidak tampil bila template
 * belum menandai peran field harga.
 */
export function PricingCheckPanel({ check }: { check: PricingCheck }) {
  if (!check.applicable) return null;
  const ph = check.per_head;
  return (
    <section
      className="space-y-2 rounded-lg p-3 text-sm"
      style={{ backgroundColor: "var(--hover)", color: "var(--text)" }}
      aria-label="Cek margin quotation"
    >
      <p className="font-medium">Cek margin</p>
      {!ph ? (
        <p style={{ color: "var(--th-color)" }}>Isi gaji pokok dan fee/harga untuk melihat margin.</p>
      ) : (
        <table className="w-full max-w-md">
          <tbody>
            <tr>
              <td className="py-0.5">Gaji pokok + tunjangan</td>
              <td className="num py-0.5">{formatRupiah(ph.base_salary + ph.allowance)}</td>
            </tr>
            <tr>
              <td className="py-0.5">BPJS perusahaan (tarif Rates)</td>
              <td className="num py-0.5">{formatRupiah(ph.bpjs_employer)}</td>
            </tr>
            <tr className="font-medium">
              <td className="py-0.5">Biaya per orang</td>
              <td className="num py-0.5">{formatRupiah(ph.cost)}</td>
            </tr>
            <tr>
              <td className="py-0.5">Harga tagih per orang</td>
              <td className="num py-0.5">{formatRupiah(ph.price)}</td>
            </tr>
            <tr className="font-semibold">
              <td className="py-0.5">Margin per orang</td>
              <td className={`num py-0.5 ${ph.margin < 0 ? "text-rose-700 dark:text-rose-400" : ""}`}>
                {formatRupiah(ph.margin)}
                {ph.margin_pct !== null && ` (${pct(ph.margin_pct)})`}
              </td>
            </tr>
            {check.monthly && (
              <tr>
                <td className="py-0.5">Margin per bulan ({check.monthly.headcount} orang)</td>
                <td className="num py-0.5">{formatRupiah(check.monthly.margin)}</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
      {check.history && (
        <p className="text-xs" style={{ color: "var(--th-color)" }}>
          Quotation sebelumnya ke lead ini: {check.history.count}× · fee terakhir {check.history.last_fee_pct}% · median{" "}
          {check.history.median_fee_pct}%
        </p>
      )}
      {check.findings.length > 0 ? (
        <ul className="space-y-1" aria-label="Peringatan margin">
          {check.findings.map((f) => (
            <li key={f.kind} className="flex items-start gap-2">
              <span className={`${SEVERITY[f.severity].cls} shrink-0`}>{SEVERITY[f.severity].label}</span>
              <span>{f.message}</span>
            </li>
          ))}
        </ul>
      ) : (
        ph && (
          <p className="flex items-center gap-1.5" style={{ color: "var(--th-color)" }}>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            Margin di atas batas {pct(check.min_margin_pct)}.
          </p>
        )
      )}
      <p className="text-xs" style={{ color: "var(--th-color)" }}>
        Fee % dihitung dari total biaya (gaji + tunjangan + BPJS perusahaan); PPN/PPh 23 tidak termasuk margin. Hanya
        peringatan -- tidak memblokir simpan atau approval.
      </p>
    </section>
  );
}

/** Cek langsung isian form (belum disimpan). */
export function LivePricingCheck({
  templateId,
  leadId,
  values,
}: {
  templateId: string;
  leadId: string;
  values: Record<string, string>;
}) {
  const debounced = useDebounced(values, 400);
  const query = useQuery({
    queryKey: ["pricing-check", templateId, leadId, debounced],
    queryFn: () =>
      api.post<PricingCheck>("/quotations/pricing-check", {
        template_id: templateId,
        field_values: debounced,
        ...(leadId ? { lead_id: leadId } : {}),
      }),
    enabled: Boolean(templateId),
    placeholderData: (prev) => prev,
  });
  return query.data ? <PricingCheckPanel check={query.data} /> : null;
}

/** Cek quotation tersimpan (untuk approver). */
export function StoredPricingCheck({ quotationId }: { quotationId: string }) {
  const query = useQuery({
    queryKey: ["pricing-check", quotationId],
    queryFn: () => api.get<PricingCheck>(`/quotations/${quotationId}/pricing-check`),
  });
  return query.data ? <PricingCheckPanel check={query.data} /> : null;
}
