import { Skeleton } from "./states";

/** Placeholder saat chunk halaman (React.lazy) sedang dimuat. `fullScreen`
 * untuk route di luar Layout (login, portal publik); tanpa itu dipakai di
 * dalam area konten Layout sehingga sidebar/topbar tetap terlihat. */
export function PageFallback({ fullScreen = false }: { fullScreen?: boolean }) {
  if (fullScreen) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: "var(--bg)" }}
        role="status"
        aria-label="Memuat halaman"
      >
        <Skeleton className="h-2 w-40" />
      </div>
    );
  }
  return (
    <div className="space-y-4" role="status" aria-label="Memuat halaman">
      <Skeleton className="h-7 w-56" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-64" />
    </div>
  );
}
