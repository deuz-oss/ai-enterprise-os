import { ChevronLeft, ChevronRight } from "lucide-react";

/** Kontrol Prev/Next + ringkasan "menampilkan X-Y dari Z" untuk list ber-limit/offset
 * (lihat backend Batch 1c: header X-Total-Count di /candidates, /job-orders). */
export function Pagination({
  offset,
  limit,
  total,
  onOffsetChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onOffsetChange: (offset: number) => void;
}) {
  if (total <= limit && offset === 0) return null;

  const shown = Math.min(offset + limit, total);
  const from = total === 0 ? 0 : offset + 1;

  return (
    <div className="flex items-center justify-between px-1 py-2 text-sm" style={{ color: "var(--text-muted)" }}>
      <span>
        Menampilkan {from}–{shown} dari {total}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="btn-secondary flex items-center gap-1 disabled:cursor-not-allowed disabled:opacity-40"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Sebelumnya
        </button>
        <button
          type="button"
          className="btn-secondary flex items-center gap-1 disabled:cursor-not-allowed disabled:opacity-40"
          disabled={shown >= total}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Berikutnya <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
