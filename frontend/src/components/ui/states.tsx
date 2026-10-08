import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Lock, RotateCw } from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError } from "../../api/client";

/**
 * Primitive state data: loading / kosong / error / tanpa akses.
 *
 * Audit 2026-10-08 (§4 C6, §14): sebagian besar halaman tidak merender error
 * query sama sekali, jadi API gagal atau 403 tampil sebagai "Belum ada data" /
 * KPI nol -- user mengira datanya memang kosong. Komponen di sini membedakan
 * ketiganya secara eksplisit. Pakai `QueryState` untuk blok/kartu, dan
 * `TableStateRow` di dalam `<tbody>` untuk tabel.
 */

/** Minimal bentuk query TanStack yang dibutuhkan (hindari generic berat). */
export interface QueryLike {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => unknown;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-lg ${className}`}
      style={{ backgroundColor: "var(--hover)" }}
    />
  );
}

export function EmptyState({
  title,
  description,
  action,
  compact = false,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`flex flex-col items-center text-center ${compact ? "gap-1 py-6" : "gap-2 py-10"}`}>
      {!compact && <Inbox className="h-6 w-6" style={{ color: "var(--th-color)" }} aria-hidden="true" />}
      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
        {title}
      </p>
      {description && (
        <p className="max-w-md text-sm" style={{ color: "var(--th-color)" }}>
          {description}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

function describeError(error: unknown): { kind: "forbidden" | "not_found" | "other"; message: string } {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return { kind: "forbidden", message: "Role Anda tidak punya akses ke data ini. Hubungi admin bila perlu akses." };
    }
    if (error.status === 404) return { kind: "not_found", message: "Data tidak ditemukan atau sudah dihapus." };
    return { kind: "other", message: error.message || `Server merespons ${error.status}.` };
  }
  if (error instanceof TypeError) {
    return { kind: "other", message: "Tidak bisa terhubung ke server. Periksa koneksi lalu coba lagi." };
  }
  return { kind: "other", message: error instanceof Error ? error.message : "Terjadi kesalahan." };
}

export function ErrorState({
  error,
  onRetry,
  compact = false,
}: {
  error: unknown;
  onRetry?: () => unknown;
  compact?: boolean;
}) {
  const { kind, message } = describeError(error);
  const Icon = kind === "forbidden" ? Lock : AlertTriangle;
  const title =
    kind === "forbidden" ? "Tidak ada akses" : kind === "not_found" ? "Tidak ditemukan" : "Gagal memuat data";
  return (
    <div
      role="alert"
      className={`flex flex-col items-center text-center ${compact ? "gap-1 py-6" : "gap-2 py-10"}`}
    >
      <Icon
        aria-hidden="true"
        className="h-6 w-6"
        style={{ color: kind === "forbidden" ? "var(--th-color)" : "var(--danger)" }}
      />
      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
        {title}
      </p>
      <p className="max-w-md text-sm" style={{ color: "var(--th-color)" }}>
        {message}
      </p>
      {kind === "other" && onRetry && (
        <button type="button" className="btn-secondary mt-2 inline-flex items-center gap-1.5" onClick={() => onRetry()}>
          <RotateCw className="h-3.5 w-3.5" aria-hidden="true" /> Coba lagi
        </button>
      )}
    </div>
  );
}

/**
 * Render children hanya kalau data sudah ada; selain itu loading/error/kosong.
 * `isEmpty` dievaluasi setelah sukses -- isi `empty` untuk pesan kosong.
 */
export function QueryState({
  query,
  isEmpty = false,
  empty,
  loading,
  compact = false,
  children,
}: {
  query: QueryLike;
  isEmpty?: boolean;
  empty?: ReactNode;
  loading?: ReactNode;
  compact?: boolean;
  children: ReactNode;
}) {
  if (query.isPending) {
    return (
      <>
        {loading ?? (
          <div className="space-y-2 py-2" role="status" aria-label="Memuat">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        )}
      </>
    );
  }
  if (query.isError) return <ErrorState error={query.error} onRetry={query.refetch} compact={compact} />;
  if (isEmpty) return <>{empty ?? <EmptyState title="Belum ada data." compact={compact} />}</>;
  return <>{children}</>;
}

/**
 * Baris status di dalam `<tbody>`: skeleton saat loading, ErrorState saat
 * gagal, pesan kosong saat sukses tanpa baris. Mengembalikan `null` bila ada
 * data, jadi aman ditaruh setelah `.map()` baris.
 */
export function TableStateRow({
  query,
  colSpan,
  isEmpty,
  emptyTitle,
  emptyDescription,
  emptyAction,
  skeletonRows = 3,
}: {
  query: QueryLike;
  colSpan: number;
  isEmpty: boolean;
  emptyTitle: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  skeletonRows?: number;
}) {
  if (query.isPending) {
    return (
      <>
        {Array.from({ length: skeletonRows }, (_, i) => (
          <tr key={i} aria-hidden="true">
            <td colSpan={colSpan} className="td">
              <Skeleton className="h-4" />
            </td>
          </tr>
        ))}
      </>
    );
  }
  if (query.isError) {
    return (
      <tr>
        <td colSpan={colSpan} className="td">
          <ErrorState error={query.error} onRetry={query.refetch} compact />
        </td>
      </tr>
    );
  }
  if (!isEmpty) return null;
  return (
    <tr>
      <td colSpan={colSpan} className="td">
        <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} compact />
      </td>
    </tr>
  );
}

/**
 * Loading / gagal / tidak ditemukan untuk halaman detail satu record. Dulu
 * cuma teks merah tanpa jalan kembali (audit 2026-10-08 §7 U5).
 */
export function DetailLoadState({
  isLoading,
  error,
  notFoundTitle,
  backTo,
  backLabel,
  onRetry,
}: {
  isLoading: boolean;
  error: unknown;
  notFoundTitle: string;
  backTo: string;
  backLabel: string;
  onRetry?: () => unknown;
}) {
  if (isLoading) {
    return (
      <div className="space-y-4" role="status" aria-label="Memuat">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  return (
    <div className="card">
      {error ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : (
        <EmptyState title={notFoundTitle} description="Data mungkin sudah dihapus atau tautannya salah." />
      )}
      <div className="flex justify-center pb-4">
        <Link to={backTo} className="btn-secondary">
          ← {backLabel}
        </Link>
      </div>
    </div>
  );
}
