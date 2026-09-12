import { Badge } from "./Badge";

/**
 * StatusPill — konsolidasi pemetaan status->warna yang sebelumnya tersebar
 * ad-hoc per halaman (docs/design/design.md §"Component Spec — Dashboard
 * Pattern"). Beda dari `Badge` (primitif tone generik): StatusPill tahu
 * ARTI status per domain, jadi pemanggil cukup kirim string status mentah
 * dari backend, bukan menghafal warnanya sendiri di tiap file.
 *
 * SENGAJA TIDAK dipaksakan ke status pipeline `PlacementStatus` (9+ tahap,
 * masing-masing warna dot sendiri di `lib/pipelineStages.ts`) atau ke
 * `business_status` job order di JobOrders.tsx (itu SELECT interaktif buat
 * ganti status, bukan badge baca-saja -- memaksanya jadi StatusPill akan
 * menghapus kemampuan edit inline). Dua sistem itu sudah benar sebagaimana
 * adanya; StatusPill untuk status BACA-SAJA yang genuinely 3-5 state datar,
 * bukan pengganti universal semua badge di app.
 */

type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

interface StatusMeta {
  label: string;
  tone: StatusTone;
}

type StatusDomain = "payment_request" | "invoice" | "margin" | "employee";

const DOMAIN_STATUS_MAP: Record<StatusDomain, Record<string, StatusMeta>> = {
  // PaymentRequests.tsx — dulu `STATUS_BADGE` lokal di file itu.
  payment_request: {
    diajukan: { label: "Diajukan", tone: "neutral" },
    menunggu_atasan: { label: "Menunggu Atasan", tone: "warning" },
    disetujui_atasan: { label: "Disetujui Atasan", tone: "success" },
    dieksekusi: { label: "Dieksekusi", tone: "info" },
    ditolak: { label: "Ditolak", tone: "danger" },
  },
  // Dashboard.tsx / Finance.tsx — dulu `INVOICE_STATUS_PILL` lokal.
  invoice: {
    draft: { label: "Draft", tone: "neutral" },
    terkirim: { label: "Terkirim", tone: "warning" },
    dibayar: { label: "Dibayar", tone: "success" },
  },
  // Dashboard.tsx margin per klien — dulu threshold inline (>=15/>=0/<0).
  margin: {
    baik: { label: "margin", tone: "success" },
    tipis: { label: "margin", tone: "warning" },
    rugi: { label: "margin", tone: "danger" },
  },
  // Employees.tsx — enum status karyawan cuma 2 nilai valid (lihat validasi
  // backend PATCH /employees/{id}): 'aktif' atau 'resign'.
  employee: {
    aktif: { label: "Aktif", tone: "success" },
    resign: { label: "Resign", tone: "neutral" },
  },
};

interface StatusPillProps {
  domain: StatusDomain;
  status: string;
  /** Override label hasil lookup (mis. margin butuh angka persen dinamis di depan label tetap). */
  label?: string;
}

export function StatusPill({ domain, status, label }: StatusPillProps) {
  const meta = DOMAIN_STATUS_MAP[domain][status];
  if (!meta) return <Badge tone="neutral">{label ?? status}</Badge>;
  return <Badge tone={meta.tone}>{label ?? meta.label}</Badge>;
}
