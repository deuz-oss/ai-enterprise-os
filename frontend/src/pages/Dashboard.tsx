import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  Briefcase,
  DollarSign,
  FileText,
  Hourglass,
  IdCard,
  Info,
  type LucideIcon,
  Magnet,
  Palmtree,
  Pin,
  PenLine,
  Receipt,
  Users,
  Wallet,
} from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { CalloutBlock } from "../components/workspace";
import { KpiCard, StatusPill, HeaderCanvas } from "../components/ui";
import { api, formatRupiah } from "../api/client";

interface Overview {
  leads: {
    total: number;
    won: number;
    lost: number;
    by_stage: Record<string, number>;
    funnel: { stage: string; count: number }[];
    pipeline_value_idr: number;
  };
  clients: number;
  documents: number;
  job_orders: { open: number; filled: number };
  candidates: { total: number; by_status: Record<string, number> };
  people: {
    total_employees: number;
    active_employees: number;
    expiring_contracts_14d: number;
    bpjs_complete: number;
    insurance_complete: number;
    resigned_this_month: number;
  };
  payroll: Record<string, number>;
  finance: {
    revenue_mtd: number;
    outstanding: number;
    overdue: number;
    invoices_total: number;
    faktur_belum: number;
    revenue_by_month: { month: string; revenue: number }[];
  };
  accounting: { period_closed: number; memorial_unposted: number };
  recruitment_talent: {
    job_orders_by_stage: Record<string, number>;
    interviews_this_week: number;
  };
  operations: {
    active_placements_by_client: { client: string; active_placements: number }[];
    profit_by_client: { client: string; revenue: number; expense: number; margin: number }[];
  };
  ai_insight: { hint: string };
}

interface DigestItem {
  type: string;
  detail: string;
  refs: string[];
}

interface Digest {
  date: string;
  items: DigestItem[];
}

interface ClientRow {
  id: string;
  name: string;
}

interface InvoiceRow {
  id: string;
  invoice_no: string;
  client_id: string;
  total_due: number;
  status: string;
  tax_invoice_status: string | null;
  no_seri_faktur: string | null;
}

interface AgingRow {
  invoice_id: string;
  invoice_no: string;
  client_name: string;
  total_due: number;
  due_date: string;
  days_overdue: number;
  bucket: string;
}

// Kategori navigasi Opsi G (Fase 28) -- SAMA persis dengan `CATEGORY_META`
// di `components/Layout.tsx` (label + aksen), supaya section Overview dan
// grup sidebar terbaca sebagai satu taksonomi, bukan dua pengelompokan
// berbeda. Kalau salah satu berubah, ubah keduanya.
const CATEGORY: Record<string, { label: string; accent: string; to: string; icon: LucideIcon }> = {
  crm: { label: "CRM", accent: "var(--cat-crm)", to: "/leads", icon: Briefcase },
  recruitment: { label: "Recruitment", accent: "var(--cat-recruitment)", to: "/job-orders", icon: Magnet },
  workforce: { label: "Workforce", accent: "var(--cat-workforce)", to: "/employees", icon: IdCard },
  finance_accounting: { label: "Finance & Accounting", accent: "var(--cat-finance)", to: "/finance", icon: Receipt },
};

// Tahapan lead -- urutan & nilai mengikuti `LeadStage` backend
// (presales/models.py), sama dengan konstanta `STAGES` di Leads.tsx.
const LEAD_STAGE_ORDER = [
  "lead",
  "kontak",
  "presentasi",
  "penawaran",
  "negosiasi",
  "deal",
  "gagal",
];
const LEAD_STAGE_LABELS: Record<string, string> = {
  lead: "Lead",
  kontak: "Kontak",
  presentasi: "Presentasi",
  penawaran: "Penawaran",
  negosiasi: "Negosiasi",
  deal: "Deal",
  gagal: "Gagal",
};

const JO_STAGE_LABELS: Record<string, string> = {
  open: "Open",
  screening: "Screening",
  interview_klien: "Interview",
  offering: "Offering",
  filled: "Filled",
  closed: "Closed",
};
const JO_STAGE_ORDER = ["open", "screening", "interview_klien", "offering", "filled", "closed"];
const JO_STAGE_COLORS: Record<string, string> = {
  open: "#7c3aed",
  screening: "#8b5cf6",
  interview_klien: "#d97706",
  offering: "#059669",
  filled: "#0f172a",
  closed: "#94a3b8",
};

const FAKTUR_STATUS_LABEL: Record<string, string> = {
  belum_buat: "Faktur belum dibuat",
  draft: "Faktur draft",
  approved: "Faktur approved",
  ditolak: "Faktur ditolak DJP",
  dibatalkan: "Faktur dibatalkan",
  pengganti: "Faktur pengganti",
};

const DIGEST_ICON: Record<string, LucideIcon> = {
  approval_menunggu: PenLine,
  payroll_klien: Wallet,
  sla_job_order: Hourglass,
  kontrak_berakhir: FileText,
  invoice_overdue: Receipt,
  cuti_menunggu: Palmtree,
  pengingat: Pin,
  ringkasan: BarChart3,
};

// Urgent Action Banner (§1.9) -- cuma untuk jenis digest yang genuinely
// "butuh tindakan" (bukan `ringkasan`/`pengingat` yang selalu muncul apa
// pun kondisinya). Domain & link tujuan di-map dari `type` yang sudah
// tetap/dikenal backend (core/ai/collab.py::daily_digest), bukan data baru.
const URGENT_DIGEST_DOMAIN: Record<string, string> = {
  approval_menunggu: "Finance & Accounting",
  payroll_klien: "Workforce",
  sla_job_order: "Recruitment",
  kontrak_berakhir: "Workforce",
  invoice_overdue: "Finance & Accounting",
  cuti_menunggu: "Workforce",
};
const URGENT_DIGEST_LINK: Record<string, string> = {
  approval_menunggu: "/payment-requests",
  payroll_klien: "/payroll",
  sla_job_order: "/job-orders",
  kontrak_berakhir: "/employees",
  invoice_overdue: "/finance",
  cuti_menunggu: "/portal-saya",
};

function pct(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

/** Kartu section ber-kategori: badge ikon + label kategori di kepala kartu,
 * warnanya mengikuti grup sidebar yang sama supaya mudah dilacak balik.
 * Round 3 (2026-09-15, respons ke feedback "masih terasa generik"): badge
 * ikon ditambah (dulu cuma teks label polos) + elevasi lembut supaya
 * seluruh halaman terasa "terangkat", bukan cuma hero card sendirian
 * yang diberi perlakuan khusus di tengah kartu-kartu flat lain -- shadow
 * di sini SENGAJA lebih tipis dari hero (`boxShadow` lebih pendek/pudar)
 * supaya hero tetap terasa paling menonjol, bukan menyamakan semuanya. */
function SectionCard({
  category,
  title,
  subtitle,
  children,
}: {
  category: keyof typeof CATEGORY;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const meta = CATEGORY[category];
  const Icon = meta.icon;
  return (
    <div
      className="rounded-xl p-4"
      style={{
        border: "1px solid var(--border)",
        backgroundColor: "var(--bg-elevated)",
        boxShadow: "0 1px 2px rgba(15,23,42,0.03), 0 8px 20px -18px rgba(15,23,42,0.35)",
      }}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2.5">
          <span
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: "var(--hover)" }}
          >
            <Icon className="h-4 w-4" style={{ color: meta.accent }} />
          </span>
          <div className="min-w-0">
            <span
              className="text-[10px] font-bold uppercase tracking-wide"
              style={{ color: meta.accent }}
            >
              {meta.label}
            </span>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
              {title}
            </h2>
            {subtitle && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {subtitle}
              </p>
            )}
          </div>
        </div>
        <Link
          to={meta.to}
          className="shrink-0 text-xs font-medium hover:underline"
          style={{ color: meta.accent }}
        >
          Buka →
        </Link>
      </div>
      {children}
    </div>
  );
}

/** Baris statistik ringkas (label kiri, angka kanan) untuk blok tanpa grafik. */
function StatRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span className="font-mono font-medium" style={{ color: "var(--text)" }}>
        {value}
      </span>
    </div>
  );
}

/** Sub-bagian di dalam satu panel konsolidasi (dipakai panel "Karyawan &
 * Operasional") -- label kecil + garis pemisah tipis, MENGGANTIKAN 3 kartu
 * `.card` terpisah yang isinya semua berkategori "workforce" (redesign
 * dashboard 2026-09-15). Pola divider ini sama persis dengan yang sudah
 * dipakai di dalam kartu "Uang" (bukan pola baru). */
function SubSection({
  title,
  action,
  first,
  children,
}: {
  title: string;
  action?: ReactNode;
  first?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={first ? "" : "mt-4 border-t pt-3"} style={first ? undefined : { borderColor: "var(--border)" }}>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-medium" style={{ color: "var(--text)" }}>
          {title}
        </p>
        {action}
      </div>
      {children}
    </div>
  );
}

const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
function monthShortLabel(ym: string): string {
  const m = Number(ym.split("-")[1]);
  return MONTH_SHORT[m - 1] ?? ym;
}

/** Tren revenue 6 bulan terakhir (permintaan user 2026-09-15: "kenapa
 * bukan menampilkan grafik revenue per month?") -- backend `/overview`
 * sebelumnya cuma punya `revenue_mtd` (1 angka bulan berjalan), tidak
 * cukup utk grafik. Ditambah query baru `finance.revenue_by_month` di
 * `dashboard/router.py` (6 bucket, dihitung di Python bukan SQL
 * date-trunc supaya portable SQLite/Postgres) -- data ASLI, bukan
 * interpolasi/fabrikasi dari revenue_mtd. */
function RevenueTrendChart({ data }: { data: { month: string; revenue: number }[] }) {
  const hasData = data.some((d) => d.revenue > 0);
  if (!hasData) {
    return (
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        Belum ada revenue tercatat dalam 6 bulan terakhir.
      </p>
    );
  }
  return (
    <div style={{ width: "100%", height: 130 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
          <XAxis
            dataKey="month"
            tickFormatter={monthShortLabel}
            tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "var(--hover)" }}
            contentStyle={{
              backgroundColor: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--text)", fontWeight: 600, marginBottom: 2 }}
            labelFormatter={(label) => monthShortLabel(String(label ?? ""))}
            formatter={(value) => [formatRupiah(Number(value) || 0), "Revenue"]}
          />
          <Bar dataKey="revenue" radius={[4, 4, 0, 0]} fill="var(--accent)" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/// Overview — ringkasan operasional lintas modul.
///
/// REDESAIN 2026-09-15 (brief "AEOS Visual Reimagination", eksekusi Concept
/// A "Executive Command Center"). Masalah struktural di versi sebelumnya
/// (bukan kosmetik): (1) 4 KPI card berbobot visual identik -- tidak ada yang
/// "paling penting"; (2) sinyal "digest" dirender DUA kali dalam dua bahasa
/// visual berbeda (banner urgent penuh-lebar DAN kartu AI Executive Digest
/// gelap) karena urgentItems adalah subset dari digest.items -- pengulangan
/// informasi, bukan dua informasi berbeda; (3) 3 kartu "workforce" terpisah
/// (Karyawan & Kepatuhan / Payroll Run / Penempatan Aktif) berdampingan
/// tanpa alasan kuat untuk jadi kartu sendiri-sendiri -- semuanya "apakah
/// operasional SDM sehat", cukup 1 panel dengan sub-bagian; (4) "Margin per
/// Klien" -- data paling actionable di halaman ini (siapa klien paling/
/// kurang menguntungkan) -- dikubur sebagai daftar datar di bagian bawah
/// kartu invoice, bukan direpresentasikan sebagai ranking.
///
/// Section dalam satu panel tetap dikelompokkan mengikuti 5 kategori
/// navigasi Opsi G (Fase 28) yang dipakai sidebar -- itu BUKAN akar masalah
/// (operator ops memang berpikir per fungsi: pipeline, rekrutmen, SDM,
/// uang), jadi taksonomi itu dipertahankan. Yang diubah adalah BOBOT VISUAL
/// (hero vs sekunder), DUPLIKASI (digest vs urgent), KEPADATAN KARTU
/// (3 kartu workforce -> 1 panel), dan REPRESENTASI DATA (list datar ->
/// ranking utk margin). Data 100% tetap dari /overview + /chat/digest +
/// /finance/invoices yang sudah ada -- tidak ada angka yang dikarang.
export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["overview"],
    queryFn: () => api.get<Overview>("/overview"),
  });
  const { data: digest } = useQuery({
    queryKey: ["chat-digest"],
    queryFn: () => api.get<Digest>("/chat/digest"),
  });
  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<ClientRow[]>("/clients"),
  });
  const { data: invoices } = useQuery({
    queryKey: ["invoices"],
    queryFn: () => api.get<InvoiceRow[]>("/finance/invoices"),
  });
  // Endpoint yang sama persis dgn yang sudah dipakai Finance.tsx -- sinyal
  // bisnis baru di Dashboard (audit desain 2026-09-15): "Outstanding &
  // Faktur" sebelumnya cuma 1 angka datar + jumlah overdue, tidak
  // membedakan tagihan telat 5 hari dari yang telat 90 hari (risiko kas
  // yang jauh beda). Reuse endpoint existing, TIDAK ada query backend baru.
  const { data: agingRows } = useQuery({
    queryKey: ["invoices-aging"],
    queryFn: () => api.get<AgingRow[]>("/finance/invoices/aging"),
  });
  // Query key "me" sama dengan Layout.tsx -- react-query dedupe otomatis,
  // tidak ada request tambahan, cuma baca cache yang sama untuk sapaan nama.
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<{ full_name: string }>("/auth/me"),
  });

  if (isLoading || !data)
    return <p className="text-sm" style={{ color: "var(--text-muted)" }}>Memuat...</p>;

  const clientName = (id: string) => clients?.find((c) => c.id === id)?.name ?? "—";
  const recentInvoices = [...(invoices ?? [])].reverse().slice(0, 5);
  const urgentItems = (digest?.items ?? []).filter((i) => i.type in URGENT_DIGEST_DOMAIN);

  const revenueShare = pct(data.finance.revenue_mtd, data.finance.revenue_mtd + data.finance.outstanding);
  const leadsActive = data.leads.total - (data.leads.by_stage.deal ?? 0) - (data.leads.by_stage.gagal ?? 0);
  const leadFunnelMax = Math.max(...LEAD_STAGE_ORDER.map((s) => data.leads.by_stage[s] ?? 0), 1);
  // Job Order sekarang funnel per-tahap (pola sama Lead Pipeline di atasnya)
  // -- sebelumnya stacked-bar+legend, representasi PROPORSI bukan funnel
  // sungguhan, tidak konsisten dgn Lead Pipeline yang sudah benar (feedback
  // user 2026-09-15: "kenapa tahap job order tidak dibuat grafik funnel?").
  const joStageMax = Math.max(
    ...JO_STAGE_ORDER.map((s) => data.recruitment_talent.job_orders_by_stage[s] ?? 0),
    1
  );

  const firstName = me?.full_name?.split(" ")[0];

  // Ranking margin per klien -- representasi diganti dari daftar datar jadi
  // bar terurut (§7/§9 brief: "ranking" & "visual storytelling" utk data
  // paling actionable di halaman ini). Diurutkan margin% tertinggi dulu;
  // lebar bar relatif terhadap |margin%| terbesar yang tampil supaya klien
  // rugi (margin negatif) tetap kebaca sebagai bar, bukan hilang di 0.
  const marginRanked = [...data.operations.profit_by_client]
    .map((row) => ({
      ...row,
      marginPct: row.revenue > 0 ? Math.round((row.margin / row.revenue) * 100) : 0,
    }))
    .sort((a, b) => b.marginPct - a.marginPct)
    .slice(0, 6);
  const marginBarMax = Math.max(...marginRanked.map((r) => Math.abs(r.marginPct)), 1);
  const bestMarginClient = marginRanked[0];

  // Win rate -- sinyal bisnis baru (audit desain 2026-09-15): data
  // (`leads.won`/`leads.lost`) sudah ada di /overview, cuma belum pernah
  // dihitung jadi persentase di Dashboard (Leads.tsx sudah menghitung ini
  // sendiri dgn definisi yang sama -- won/(won+lost) -- disamakan di sini,
  // bukan definisi baru).
  const winRateDenom = data.leads.won + data.leads.lost;
  const winRate = winRateDenom > 0 ? Math.round((data.leads.won / winRateDenom) * 100) : null;

  // Ringkasan AR aging per bucket -- dari endpoint yang sama dgn
  // Finance.tsx, dikelompokkan ulang di sini (bukan backend baru).
  const AGING_BUCKET_ORDER = ["1-30", "31-60", ">60"];
  const agingByBucket: Record<string, number> = { "1-30": 0, "31-60": 0, ">60": 0 };
  for (const row of agingRows ?? []) {
    agingByBucket[row.bucket] = (agingByBucket[row.bucket] ?? 0) + row.total_due;
  }
  const agingTotal = Object.values(agingByBucket).reduce((s, v) => s + v, 0);

  return (
    <div className="space-y-5">
      <HeaderCanvas
        name={firstName}
        headline="Berikut ringkasan operasional lintas modul hari ini."
        subtext={`${data.clients} klien aktif · ${data.job_orders.open} job order terbuka · ${data.people.active_employees} karyawan aktif`}
      />

      {/* Palet dipatok persis (bukan var(--...)), sama seperti PreflightAlert
          (components/ui/PreflightAlert.tsx) -- SENGAJA sama di light & dark
          mode karena ini alert urgensi tinggi, bukan elemen tema biasa. */}
      {urgentItems.length > 0 && (
        <div className="rounded-xl border p-4" style={{ backgroundColor: "#FFFBEB", borderColor: "#FDE68A" }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-semibold" style={{ color: "#92400E" }}>
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {urgentItems.length} Tindakan Mendesak Membutuhkan Perhatian
            </p>
            <span
              className="shrink-0 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white"
              style={{ backgroundColor: "#92400E" }}
            >
              Urgent Priority
            </span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {urgentItems.map((item, idx) => {
              const ItemIcon = DIGEST_ICON[item.type] ?? Info;
              return (
                <div
                  key={idx}
                  className="rounded-lg border bg-white p-3"
                  style={{ borderColor: "#FDE68A", boxShadow: "0 1px 2px rgba(146,64,14,0.06)" }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
                      style={{ backgroundColor: "#FEF3C7" }}
                    >
                      <ItemIcon className="h-3.5 w-3.5" style={{ color: "#92400E" }} />
                    </span>
                    <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "#92400E" }}>
                      {URGENT_DIGEST_DOMAIN[item.type] ?? "Umum"}
                    </p>
                  </div>
                  <p className="mt-2 text-xs" style={{ color: "#78350F" }}>
                    {item.detail}
                  </p>
                  <Link
                    to={URGENT_DIGEST_LINK[item.type] ?? "#"}
                    className="mt-2 inline-block text-xs font-medium hover:underline"
                    style={{ color: "#92400E" }}
                  >
                    Lihat detail →
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ===== Business Pulse: hero + KPI sekunder =====
          Bobot visual asimetris (§10 brief: PRIMARY/SECONDARY/TERTIARY,
          "do not make every element equally prominent") -- dulu 4 KpiCard
          berukuran identik berdampingan, sekarang headcount+revenue jadi
          hero (2 metrik besar dlm 1 kartu + 1 kalimat insight sintesis dari
          data ASLI, bukan karangan), job order & outstanding jadi kartu
          sekunder yang lebih kecil di sampingnya. Tidak ada `delta` (persen
          vs periode lalu) di mana pun -- /overview backend belum
          menyediakan angka perbandingan periode sungguhan, dan §0 melarang
          mengarang delta cuma supaya kartu "terlihat lengkap". */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Hero diberi elevasi nyata (bukan cuma `.card` flat yang sama
            dengan semua kartu lain) -- garis aksen di atas, latar gradasi
            tint aksen (pakai token --accent-tint yang sudah theme-aware,
            bukan hex baru), dan shadow lembut. Ini pengecualian YANG
            DISENGAJA & TERBATAS pada 1 kartu ini dari konvensi "border
            tipis, bukan shadow" di design.md §2 -- justru karena hero
            HARUS terasa beda dari kartu lain, itulah maksudnya jadi hero.
            Feedback user 2026-09-15 setelah draft pertama: struktur oke
            tapi eksekusi visualnya masih terasa "SaaS admin generik". */}
        <div
          className="relative overflow-hidden rounded-xl p-6 lg:col-span-2"
          style={{
            border: "1px solid var(--border)",
            background: "linear-gradient(165deg, var(--bg-elevated) 0%, var(--accent-tint) 260%)",
            boxShadow: "0 1px 2px rgba(15,23,42,0.04), 0 20px 44px -28px rgba(15,110,86,0.45)",
          }}
        >
          <div
            className="absolute inset-x-0 top-0 h-[3px]"
            style={{ background: "linear-gradient(90deg, var(--accent) 0%, var(--accent-tint) 100%)" }}
          />
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <div className="flex items-center gap-2.5">
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full p-green"
                  style={{ boxShadow: "0 2px 6px rgba(0,0,0,0.1)" }}
                >
                  <Users className="h-5 w-5" />
                </span>
                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  Headcount Aktif
                </p>
              </div>
              <p className="mt-3 text-4xl font-bold tracking-tight tabular-nums" style={{ color: "var(--text)" }}>
                {data.people.active_employees}
              </p>
              <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                dari {data.people.total_employees} karyawan terdaftar
              </p>
              <div className="mt-3 h-2 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--hover)" }}>
                <div
                  className="h-full rounded-full transition-[width] duration-500 ease-out"
                  style={{
                    width: `${pct(data.people.active_employees, data.people.total_employees)}%`,
                    background: "linear-gradient(90deg, var(--accent) 0%, var(--accent-tint) 180%)",
                  }}
                />
              </div>
            </div>
            <div className="border-t pt-6 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0" style={{ borderColor: "var(--border)" }}>
              <div className="flex items-center gap-2.5">
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full p-yellow"
                  style={{ boxShadow: "0 2px 6px rgba(0,0,0,0.1)" }}
                >
                  <DollarSign className="h-5 w-5" />
                </span>
                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  Revenue MTD
                </p>
              </div>
              <p className="mt-3 text-4xl font-bold tracking-tight tabular-nums" style={{ color: "var(--text)" }}>
                {formatRupiah(data.finance.revenue_mtd)}
              </p>
              <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                {data.finance.invoices_total === 0 ? (
                  <span title="Belum ada invoice — buat dari Quotation yang sudah Deal">
                    Belum ada invoice — buat dari Quotation
                  </span>
                ) : (
                  `${data.finance.invoices_total} invoice tercatat`
                )}
              </p>
              <div className="mt-3 h-2 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--hover)" }}>
                <div
                  className="h-full rounded-full transition-[width] duration-500 ease-out"
                  style={{ width: `${revenueShare}%`, background: "linear-gradient(90deg, var(--accent) 0%, var(--accent-tint) 180%)" }}
                />
              </div>
            </div>
          </div>
          {/* Kalimat sintesis -- menggabungkan 2 angka di atas + (kalau ada
              datanya) klien margin terbaik, jadi satu cerita singkat,
              bukan cuma 2 angka berdampingan (§9 brief "visual storytelling").
              Seluruhnya dari field yang sudah di-fetch, tidak ada fabrikasi.
              Dikemas dalam strip tint aksen supaya tetap terasa bagian dari
              hero, bukan footnote pudar. */}
          <p
            className="relative mt-5 rounded-lg px-3.5 py-2.5 text-xs"
            style={{ backgroundColor: "var(--accent-tint)", color: "var(--text-muted)" }}
          >
            <span className="font-medium" style={{ color: "var(--text)" }}>{data.people.active_employees} karyawan aktif</span> menghasilkan{" "}
            <span className="font-medium" style={{ color: "var(--text)" }}>{formatRupiah(data.finance.revenue_mtd)}</span> revenue bulan ini
            {bestMarginClient && bestMarginClient.revenue > 0 && (
              <>
                {" "}
                · margin terbaik saat ini:{" "}
                <span style={{ color: "var(--text)" }}>
                  {bestMarginClient.client} ({bestMarginClient.marginPct}%)
                </span>
              </>
            )}
          </p>
        </div>

        <div className="space-y-4">
          <KpiCard
            label="Job Order Aktif"
            value={data.job_orders.open}
            icon={Briefcase}
            iconTone="info"
            context={`${data.job_orders.filled} filled · ${data.candidates.total} kandidat`}
            progressPct={pct(data.job_orders.filled, data.job_orders.open + data.job_orders.filled)}
          />
          <KpiCard
            label="Outstanding & Faktur"
            value={formatRupiah(data.finance.outstanding)}
            icon={AlertTriangle}
            iconTone="danger"
            context={`${data.finance.overdue} overdue · ${data.finance.faktur_belum} faktur belum dibuat`}
            progressPct={pct(data.finance.overdue, Math.max(data.finance.invoices_total, 1))}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Kolom kiri */}
        <div className="space-y-5 lg:col-span-2">
          <SectionCard
            category="crm"
            title="Pipeline Calon Klien"
            subtitle={`${leadsActive} lead aktif · ${data.leads.won} deal menang · ${data.clients} klien · ${data.documents} dokumen legal`}
          >
            {/* Nilai Pipeline & Win Rate -- sinyal bisnis baru (audit desain
                2026-09-15, permintaan user): dulu funnel cuma tampil sbg
                JUMLAH lead per tahap, tidak pernah "seberapa besar" (Rp)
                atau "seberapa efektif kita menang" (%). */}
            <div className="mb-3 flex flex-wrap gap-5 border-b pb-3" style={{ borderColor: "var(--border)" }}>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  Nilai Pipeline
                </p>
                <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--text)" }}>
                  {formatRupiah(data.leads.pipeline_value_idr)}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  Win Rate
                </p>
                <p className="text-lg font-semibold tabular-nums" style={{ color: "var(--text)" }}>
                  {winRate !== null ? `${winRate}%` : "—"}
                </p>
                {winRateDenom > 0 && (
                  <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {data.leads.won} menang dari {winRateDenom}
                  </p>
                )}
              </div>
            </div>
            {data.leads.total > 0 ? (
              <div className="space-y-1.5">
                {LEAD_STAGE_ORDER.map((stage) => {
                  const count = data.leads.by_stage[stage] ?? 0;
                  return (
                    <div key={stage} className="flex items-center gap-2">
                      <span className="w-20 shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>
                        {LEAD_STAGE_LABELS[stage] ?? stage}
                      </span>
                      <div className="h-2 flex-1 rounded-full" style={{ backgroundColor: "var(--hover)" }}>
                        <div
                          className="h-full rounded-full transition-[width] duration-500 ease-out"
                          style={{
                            width: `${pct(count, leadFunnelMax)}%`,
                            backgroundColor:
                              stage === "gagal"
                                ? "#dc2626"
                                : stage === "deal"
                                  ? "#059669"
                                  : CATEGORY.crm.accent,
                          }}
                        />
                      </div>
                      <span
                        className="w-6 shrink-0 text-right font-mono text-xs font-medium"
                        style={{ color: "var(--text)" }}
                      >
                        {count}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Belum ada lead tercatat.
              </p>
            )}
          </SectionCard>

          <SectionCard
            category="recruitment"
            title="Job Order"
            subtitle={`${data.candidates.total} kandidat di pipeline · ${data.recruitment_talent.interviews_this_week} interview minggu ini`}
          >
            {data.job_orders.open + data.job_orders.filled > 0 || Object.values(data.recruitment_talent.job_orders_by_stage).some((c) => c > 0) ? (
              <div className="space-y-1.5">
                {JO_STAGE_ORDER.map((stage) => {
                  const count = data.recruitment_talent.job_orders_by_stage[stage] ?? 0;
                  return (
                    <div key={stage} className="flex items-center gap-2">
                      <span className="w-24 shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>
                        {JO_STAGE_LABELS[stage] ?? stage}
                      </span>
                      <div className="h-2 flex-1 rounded-full" style={{ backgroundColor: "var(--hover)" }}>
                        <div
                          className="h-full rounded-full transition-[width] duration-500 ease-out"
                          style={{
                            width: `${pct(count, joStageMax)}%`,
                            backgroundColor: JO_STAGE_COLORS[stage],
                          }}
                        />
                      </div>
                      <span
                        className="w-6 shrink-0 text-right font-mono text-xs font-medium"
                        style={{ color: "var(--text)" }}
                      >
                        {count}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Belum ada job order tercatat.
              </p>
            )}
          </SectionCard>

          <SectionCard
            category="finance_accounting"
            title="Keuangan"
            subtitle="Tren revenue, invoice terbaru, margin per klien & kesehatan pembukuan"
          >
            {/* Tren revenue jadi konten UTAMA panel ini (dipindah ke atas
                tabel invoice) -- permintaan user 2026-09-15: tabel invoice
                mentah (daftar dokumen) bukan cara terbaik bercerita ke
                eksekutif, grafik tren jauh lebih bercerita. */}
            <p className="mb-2 text-xs font-medium" style={{ color: "var(--text)" }}>
              Tren Revenue (6 bulan terakhir)
            </p>
            <RevenueTrendChart data={data.finance.revenue_by_month} />

            <div className="mt-4 border-t pt-3" style={{ borderColor: "var(--border)" }}>
              <p className="mb-2 text-xs font-medium" style={{ color: "var(--text)" }}>
                Invoice Terbaru
              </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="th">Invoice</th>
                    <th className="th">Klien</th>
                    <th className="th text-right">Jumlah</th>
                    <th className="th">Status</th>
                    <th className="th">Faktur</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {recentInvoices.map((inv) => (
                    <tr key={inv.id}>
                      <td className="td font-mono text-xs">{inv.invoice_no}</td>
                      <td className="td">{clientName(inv.client_id)}</td>
                      <td className="td text-right tabular-nums">{formatRupiah(inv.total_due)}</td>
                      <td className="td">
                        <StatusPill domain="invoice" status={inv.status} />
                      </td>
                      <td className="td text-xs" style={{ color: "var(--text-muted)" }}>
                        {FAKTUR_STATUS_LABEL[inv.tax_invoice_status ?? "belum_buat"] ?? "—"}
                      </td>
                    </tr>
                  ))}
                  {recentInvoices.length === 0 && (
                    <tr>
                      <td colSpan={5} className="td text-center" style={{ color: "var(--text-muted)" }}>
                        Belum ada invoice.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            </div>

            {/* Margin per klien: diganti dari daftar datar jadi ranking bar
                terurut (§7/§9 brief) -- ini angka paling actionable di kartu
                ini (siapa yang menguntungkan, siapa yang tidak), jadi layak
                representasi visual, bukan dikubur sbg baris teks terakhir. */}
            <div className="mt-4 grid grid-cols-1 gap-4 border-t pt-3 sm:grid-cols-8" style={{ borderColor: "var(--border)" }}>
              <div className="sm:col-span-3">
                <p className="mb-2 text-xs font-medium" style={{ color: "var(--text)" }}>
                  Margin per Klien (bulan berjalan)
                </p>
                {marginRanked.length > 0 ? (
                  <div className="space-y-2">
                    {marginRanked.map((row, idx) => (
                      <div key={row.client}>
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <span className="min-w-0 truncate font-medium" style={{ color: "var(--text)" }}>
                            {row.client}
                            {idx === 0 && row.marginPct > 0 && (
                              <span className="pill p-green ml-1.5 text-[9px]">Terbaik</span>
                            )}
                          </span>
                          <span
                            className="shrink-0 font-mono font-medium"
                            style={{ color: row.marginPct >= 15 ? "#047857" : row.marginPct >= 0 ? "#b45309" : "#b91c1c" }}
                          >
                            {row.marginPct}%
                          </span>
                        </div>
                        <div className="mt-1 h-2 rounded-full" style={{ backgroundColor: "var(--hover)" }}>
                          <div
                            className="h-full rounded-full transition-[width] duration-500 ease-out"
                            style={{
                              width: `${Math.max(4, pct(Math.abs(row.marginPct), marginBarMax))}%`,
                              background:
                                row.marginPct >= 15
                                  ? "linear-gradient(90deg, #059669 0%, #34d399 100%)"
                                  : row.marginPct >= 0
                                    ? "linear-gradient(90deg, #b45309 0%, #fbbf24 100%)"
                                    : "linear-gradient(90deg, #b91c1c 0%, #f87171 100%)",
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Belum ada data margin per klien.
                  </p>
                )}
              </div>
              <div className="sm:col-span-3">
                {/* Aging AR -- sinyal bisnis baru (audit desain 2026-09-15):
                    "Outstanding & Faktur" di hero cuma 1 angka datar +
                    jumlah overdue, tidak bedakan telat 5 hari dari 90 hari
                    -- risiko kas yang beda jauh. Endpoint sama persis dgn
                    Finance.tsx, dikelompokkan ulang di sini saja. */}
                <p className="mb-2 text-xs font-medium" style={{ color: "var(--text)" }}>
                  Aging Tagihan Terlambat
                </p>
                {agingTotal > 0 ? (
                  <div className="space-y-1.5">
                    {AGING_BUCKET_ORDER.map((bucket) => (
                      <div key={bucket} className="flex items-center justify-between text-xs">
                        <span style={{ color: "var(--text-muted)" }}>{bucket} hari</span>
                        <span
                          className="font-mono font-medium"
                          style={{ color: bucket === ">60" ? "#b91c1c" : "var(--text)" }}
                        >
                          {formatRupiah(agingByBucket[bucket] ?? 0)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Tidak ada tagihan lewat jatuh tempo.
                  </p>
                )}
              </div>
              <div className="sm:col-span-2">
                <p className="mb-2 text-xs font-medium" style={{ color: "var(--text)" }}>
                  Kesehatan Pembukuan
                </p>
                <div className="space-y-1.5">
                  <StatRow label="Periode akuntansi tercatat" value={data.accounting.period_closed} />
                  <StatRow label="Jurnal memorial belum diposting" value={data.accounting.memorial_unposted} />
                </div>
              </div>
            </div>
          </SectionCard>
        </div>

        {/* Kolom kanan */}
        <div className="space-y-5">
          {/* Kartu "AI Executive Digest" dibuang sementara (permintaan user
              2026-09-16): isinya (`/chat/digest`) murni threshold check
              deterministik, tidak ada panggilan LLM sama sekali -- label
              "AI" menyesatkan. Narasi AI SUNGGUHAN sudah ada di backend
              (`GET /accounting/ai/executive-summary`, pakai `chat_completion`
              beneran) tapi belum disambungkan ke sini. Panggil lagi kalau
              endpoint itu sudah dipakai. */}

          {/* Konsolidasi "Karyawan & Kepatuhan" + "Payroll Run" + "Penempatan
              Aktif" (dulu 3 kartu .card terpisah) jadi 1 panel dengan 3
              sub-bagian -- semuanya sama-sama menjawab "apakah operasional
              SDM sehat", tidak ada alasan kuat jadi 3 kartu sendiri-sendiri
              (redesign dashboard 2026-09-15). */}
          <SectionCard category="workforce" title="Karyawan & Operasional">
            <SubSection title="Kepatuhan" first>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs">
                    <span style={{ color: "var(--text)" }}>BPJS Lengkap</span>
                    <span className="font-mono font-medium" style={{ color: "var(--text)" }}>
                      {data.people.bpjs_complete}/{data.people.total_employees} ·{" "}
                      {pct(data.people.bpjs_complete, data.people.total_employees)}%
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full" style={{ backgroundColor: "var(--hover)" }}>
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-[width] duration-500 ease-out"
                      style={{ width: `${pct(data.people.bpjs_complete, data.people.total_employees)}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs">
                    <span style={{ color: "var(--text)" }}>Asuransi Lengkap</span>
                    <span className="font-mono font-medium" style={{ color: "var(--text)" }}>
                      {data.people.insurance_complete}/{data.people.total_employees} ·{" "}
                      {pct(data.people.insurance_complete, data.people.total_employees)}%
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full" style={{ backgroundColor: "var(--hover)" }}>
                    <div
                      className="h-full rounded-full bg-amber-500 transition-[width] duration-500 ease-out"
                      style={{ width: `${pct(data.people.insurance_complete, data.people.total_employees)}%` }}
                    />
                  </div>
                </div>
                {/* Turnover bulan berjalan -- sinyal bisnis baru (audit
                    desain 2026-09-15): dulu "karyawan aktif" cuma angka
                    statis, tidak pernah kelihatan APAKAH sedang banyak yg
                    keluar bulan ini (resigned_at baru ditambah, lihat
                    hrd/models.py). */}
                <div className="flex items-center justify-between text-xs">
                  <span style={{ color: "var(--text)" }}>Resign bulan ini</span>
                  <span
                    className="font-mono font-medium"
                    style={{ color: data.people.resigned_this_month > 0 ? "#b45309" : "var(--text)" }}
                  >
                    {data.people.resigned_this_month}
                  </span>
                </div>
              </div>
              {data.people.expiring_contracts_14d > 0 && (
                <div className="mt-3">
                  <CalloutBlock tone="warning">
                    <span className="font-semibold">Expiry ≤14 hari:</span>{" "}
                    {data.people.expiring_contracts_14d} kontrak perlu tindak lanjut.
                  </CalloutBlock>
                </div>
              )}
            </SubSection>

            {/* Payroll Run dibuang dari sini (redesign, permintaan user
                2026-09-15) -- itu status proses internal, bukan sinyal
                bisnis, dan Payroll.tsx sendiri sudah menampilkannya jauh
                lebih detail + actionable (preflight alert). Dashboard
                eksekutif fokus ke sinyal yang butuh keputusan, bukan
                breakdown status antrian.

                "Penempatan Aktif" juga dibuang dari sini (2026-09-16) --
                digabung ke "Margin & Penempatan per Klien" di panel
                Keuangan, karena keduanya sama-sama breakdown PER KLIEN dan
                sebelumnya terpecah jadi 2 panel berbeda tanpa alasan kuat. */}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
