import { X } from "lucide-react";
import { useSearchParams } from "react-router-dom";

/**
 * Baris "filter aktif dari URL" (mis. hasil ⌘K "Tampilkan daftar: …", AI
 * opportunity #5). Daftar yang tersaring diam-diam membingungkan, jadi
 * filter selalu ditulis eksplisit dengan tombol hapus.
 */
export function UrlFilterBar({ labels }: { labels: string[] }) {
  const [, setSearchParams] = useSearchParams();
  if (labels.length === 0) return null;
  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-lg px-3 py-2 text-xs"
      style={{ backgroundColor: "var(--accent-tint)", color: "var(--text)" }}
      role="status"
    >
      <span className="font-semibold">Filter aktif:</span>
      {labels.map((l) => (
        <span key={l} className="pill p-gray">
          {l}
        </span>
      ))}
      <button
        type="button"
        className="ml-auto inline-flex items-center gap-1 font-medium hover:underline"
        style={{ color: "var(--accent)" }}
        onClick={() => setSearchParams({}, { replace: true })}
      >
        <X className="h-3.5 w-3.5" aria-hidden="true" /> Hapus filter
      </button>
    </div>
  );
}
