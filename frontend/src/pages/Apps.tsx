import AppLauncherGrid, { useApps } from "../components/AppLauncherGrid";
import { PageHeader } from "../components/notion";

/// Rute /apps: halaman penuh launcher (grid sama dengan modal workspace).
export default function Apps() {
  const { data: apps, isLoading, error } = useApps();

  if (isLoading) return <p className="text-slate-500">Memuat aplikasi...</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;

  const licensedCount = (apps ?? []).filter((a) => a.licensed).length;

  return (
    <div className="space-y-4">
      <div>
        <PageHeader emoji="🚀" title="Aplikasi" />
        <p className="mt-1 text-sm text-slate-500">
          {licensedCount} dari {apps?.length ?? 0} aplikasi aktif untuk
          perusahaan Anda. Mulai trial 14 hari langsung dari sini — tanpa
          hubungi sales.
        </p>
      </div>

      <AppLauncherGrid />
    </div>
  );
}
