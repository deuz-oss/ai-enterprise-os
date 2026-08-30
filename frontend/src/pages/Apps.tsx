import AppLauncherGrid, { useApps } from "../components/AppLauncherGrid";
import { Rocket } from "lucide-react";
import { PageHeader } from "../components/notion";

/// Rute /apps: halaman penuh launcher (grid sama dengan modal workspace).
export default function Apps() {
  const { data: apps, isLoading, error } = useApps();

  if (isLoading) return <p className="text-[var(--n-text-muted)]">Memuat aplikasi...</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;

  const licensedCount = (apps ?? []).filter((a) => a.licensed).length;

  return (
    <div className="space-y-4">
      <div>
        <PageHeader icon={Rocket} title="Aplikasi" />
        <p className="mt-1 text-sm text-[var(--n-text-muted)]">
          {licensedCount} dari {apps?.length ?? 0} aplikasi aktif untuk
          perusahaan Anda. Mulai trial 14 hari langsung dari sini — tanpa
          hubungi sales.
        </p>
      </div>

      <AppLauncherGrid />
    </div>
  );
}
