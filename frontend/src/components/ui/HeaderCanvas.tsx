import { useState, type ReactNode } from "react";
import { Calendar, ChevronDown } from "lucide-react";

/**
 * Pola "Header Canvas" — docs/design/design.md §"Component Spec — Dashboard
 * Pattern". Greeting kontekstual (jam lokal browser) + headline 1 kalimat +
 * subtext + date-range picker kanan atas.
 *
 * Date-range picker di sini PRESENTASIONAL SAJA (§0 -- jangan fabrikasi
 * fungsi yang belum ada): backend /overview (dan endpoint sejenis di
 * halaman lain yang sudah pakai pola ini) belum menerima parameter rentang
 * tanggal sama sekali, jadi memilih rentang di sini TIDAK memfilter data
 * apa pun -- sama seperti tombol "Periode tampilan (segera dapat
 * difilter)" yang sudah ada duluan di topbar Layout.tsx. `onRangeChange`
 * disediakan supaya pemanggil BISA mewujudkannya nyata begitu endpoint
 * terkait sudah mendukung filter tanggal, tanpa perlu bongkar komponen ini.
 */

const RANGE_OPTIONS = ["Hari ini", "7 hari terakhir", "30 hari terakhir", "Bulan ini"] as const;
export type DateRangeOption = (typeof RANGE_OPTIONS)[number];

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 11) return "Selamat Pagi,";
  if (hour < 15) return "Selamat Siang,";
  if (hour < 18) return "Selamat Sore,";
  return "Selamat Malam,";
}

interface HeaderCanvasProps {
  /** Nama yang disapa, mis. nama depan user login. Opsional -- kalau kosong, greeting tetap tampil tanpa nama. */
  name?: string;
  headline: ReactNode;
  subtext?: ReactNode;
  /** Tampilkan date-range picker kanan atas (presentasional, lihat catatan di atas). Default true. */
  showRangePicker?: boolean;
  onRangeChange?: (range: DateRangeOption) => void;
}

export function HeaderCanvas({ name, headline, subtext, showRangePicker = true, onRangeChange }: HeaderCanvasProps) {
  const [open, setOpen] = useState(false);
  const [range, setRange] = useState<DateRangeOption>("30 hari terakhir");

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
          {greeting()}
          {name ? ` ${name}` : ""}
        </p>
        <h1 className="mt-0.5 text-xl font-semibold sm:text-2xl" style={{ color: "var(--text)" }}>
          {headline}
        </h1>
        {subtext && (
          <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
            {subtext}
          </p>
        )}
      </div>

      {showRangePicker && (
        <div className="relative shrink-0">
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-1.5 text-sm"
            style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)", color: "var(--text)" }}
            title="Rentang tanggal (belum memfilter data — menunggu dukungan backend)"
          >
            <Calendar className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
            {range}
            <ChevronDown className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
          </button>
          {open && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
              <div
                className="absolute right-0 top-full z-20 mt-1 w-48 overflow-hidden rounded-lg shadow-lg"
                style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-elevated)" }}
              >
                {RANGE_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => {
                      setRange(opt);
                      setOpen(false);
                      onRangeChange?.(opt);
                    }}
                    className="block w-full cursor-pointer px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--hover)]"
                    style={{ color: opt === range ? "var(--accent)" : "var(--text)" }}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
