import { useQuery } from "@tanstack/react-query";
import { TrendingDown, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { api, formatRupiah } from "../api/client";

/** Respons `GET /overview/anomalies` (backend dashboard/anomalies.py). */
export interface KpiAnomalies {
  period: string;
  compared_to: string;
  threshold_pct: number;
  items: {
    kpi: string;
    label: string;
    period: string;
    compared_to: string;
    current: number;
    previous: number;
    change_pct: number;
    sentence: string;
    drivers: { client_id: string | null; name: string; current: number; previous: number; delta: number }[];
    link: string;
  }[];
}

/**
 * Perubahan besar KPI antar dua bulan penuh terakhir (AI opportunity #10):
 * satu kalimat + klien penyumbang terbesar sebagai sumber yang bisa diklik.
 * Angka & kalimat deterministik dari backend; kartu tidak tampil bila tidak
 * ada perubahan di atas ambang (tidak menambah kebisingan dashboard).
 */
export function KpiAnomaliesCard() {
  const query = useQuery({
    queryKey: ["overview-anomalies"],
    queryFn: () => api.get<KpiAnomalies>("/overview/anomalies"),
  });
  const data = query.data;
  if (!data || data.items.length === 0) return null;
  return (
    <section className="card space-y-3" aria-labelledby="kpi-anomalies-title">
      <div>
        <h2 id="kpi-anomalies-title" className="font-semibold" style={{ color: "var(--text)" }}>
          Perubahan besar bulan lalu
        </h2>
        <p className="text-xs" style={{ color: "var(--th-color)" }}>
          {data.period} dibanding {data.compared_to} (bulan penuh) · berubah ≥{Math.round(data.threshold_pct * 100)}%
        </p>
      </div>
      <ul className="space-y-3">
        {data.items.map((item) => {
          const up = item.change_pct > 0;
          const Icon = up ? TrendingUp : TrendingDown;
          return (
            <li key={item.kpi} className="flex items-start gap-3">
              <Icon
                aria-hidden="true"
                className={`mt-0.5 h-4 w-4 shrink-0 ${up ? "text-emerald-600" : "text-rose-600 dark:text-rose-400"}`}
              />
              <div className="min-w-0 space-y-1 text-sm" style={{ color: "var(--text)" }}>
                <p>{item.sentence}</p>
                {item.drivers.length > 0 && (
                  <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs" aria-label={`Penyumbang perubahan ${item.label}`}>
                    {item.drivers.map((d) => (
                      <li key={d.client_id ?? d.name}>
                        {d.client_id ? (
                          <Link to={`/clients/${d.client_id}`} className="hover:underline" style={{ color: "var(--accent)" }}>
                            {d.name}
                          </Link>
                        ) : (
                          d.name
                        )}{" "}
                        <span className="num" style={{ color: "var(--th-color)" }}>
                          {d.delta > 0 ? "+" : "−"}
                          {formatRupiah(Math.abs(d.delta))}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <Link to={item.link} className="inline-block text-xs font-medium hover:underline" style={{ color: "var(--accent)" }}>
                  Lihat detail →
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
