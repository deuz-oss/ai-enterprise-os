import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { api, formatRupiah } from "../api/client";
import { QueryState } from "./ui";

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
        // Pasangan label: nilai, bukan tabel data (tanpa header kolom) -> <dl>.
        // Label sekunder pakai --th-color: panel ini di atas --hover, dan
        // --text-muted gagal kontras AA di permukaan itu.
        <dl className="grid max-w-md grid-cols-[1fr,auto] gap-x-3 gap-y-0.5">
          <dt style={{ color: "var(--th-color)" }}>Gaji pokok + tunjangan</dt>
          <dd className="num">{formatRupiah(ph.base_salary + ph.allowance)}</dd>
          <dt style={{ color: "var(--th-color)" }}>BPJS perusahaan (tarif Rates)</dt>
          <dd className="num">{formatRupiah(ph.bpjs_employer)}</dd>
          <dt className="font-medium">Biaya per orang</dt>
          <dd className="num font-medium">{formatRupiah(ph.cost)}</dd>
          <dt style={{ color: "var(--th-color)" }}>Harga tagih per orang</dt>
          <dd className="num">{formatRupiah(ph.price)}</dd>
          <dt className="font-semibold">Margin per orang</dt>
          <dd className="num font-semibold" style={ph.margin < 0 ? { color: "var(--danger)" } : undefined}>
            {formatRupiah(ph.margin)}
            {ph.margin_pct !== null && ` (${pct(ph.margin_pct)})`}
          </dd>
          {check.monthly && (
            <>
              <dt style={{ color: "var(--th-color)" }}>Margin per bulan ({check.monthly.headcount} orang)</dt>
              <dd className="num">{formatRupiah(check.monthly.margin)}</dd>
            </>
          )}
        </dl>
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
            <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "var(--success)" }} aria-hidden="true" />
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
  // Approver harus tahu kalau cek margin GAGAL dimuat -- dulu diam-diam null,
  // terbaca seolah tidak ada peringatan.
  return (
    <QueryState query={query} compact>
      {query.data && <PricingCheckPanel check={query.data} />}
    </QueryState>
  );
}
