import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, formatDateTime, formatRupiah, parseRupiahInput } from "../../api/client";
import { autoReloadReasonLabel, type AutoReloadSettings } from "../../lib/billing";
import { Badge, Button, QueryState } from "../ui";
import { useInvalidateBilling } from "./hooks";

function SettingsForm({ settings }: { settings: AutoReloadSettings }) {
  const qc = useQueryClient();
  const invalidate = useInvalidateBilling();
  const [enabled, setEnabled] = useState(settings.enabled);
  const [threshold, setThreshold] = useState(settings.threshold !== null ? String(settings.threshold) : "");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (body: { enabled: boolean; threshold: number | null }) =>
      api.put<AutoReloadSettings>("/billing/auto-reload-settings", body),
    onSuccess: (res) => {
      setError(null);
      qc.setQueryData(["billing-auto-reload"], res);
      invalidate();
      toast.success("Pengaturan auto-reload tersimpan");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal menyimpan pengaturan"),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const parsed = threshold.trim() ? parseRupiahInput(threshold) : null;
    if (threshold.trim() && parsed === null) {
      setError("Ambang batas tidak terbaca. Tulis angka rupiah, mis. 200000 atau 200.000.");
      return;
    }
    save.mutate({ enabled, threshold: parsed });
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <label className="flex items-center gap-2 text-sm" style={{ color: "var(--text)" }}>
        <input type="checkbox" className="h-4 w-4" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Isi saldo otomatis saat saldo menipis
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="block text-xs" style={{ color: "var(--text-muted)" }}>
          Ambang batas (Rp)
          <input
            className="input mt-1 w-full"
            inputMode="numeric"
            placeholder="mis. 200.000"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          />
        </label>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>
          Nominal reload
          <p className="input mt-1 w-full tabular-nums" aria-readonly="true" style={{ opacity: 0.8 }}>
            {formatRupiah(settings.amount)}
          </p>
        </div>
      </div>
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        Nominal reload tetap {formatRupiah(settings.amount)} per pengisian, ditagih ke metode bayar default.
      </p>
      <Button type="submit" variant="secondary" className="w-full" loading={save.isPending}>
        Simpan pengaturan
      </Button>
      {error && (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </form>
  );
}

export function AutoReloadSettingsCard() {
  const settings = useQuery({
    queryKey: ["billing-auto-reload"],
    queryFn: () => api.get<AutoReloadSettings>("/billing/auto-reload-settings"),
  });
  const s = settings.data;
  const reason = s ? autoReloadReasonLabel(s.reason) : null;

  return (
    <div className="card max-w-md space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
          Auto-reload
        </h3>
        {s &&
          (s.effective ? (
            <Badge tone="success">Berjalan</Badge>
          ) : (
            <Badge tone={s.enabled ? "warning" : "neutral"}>{s.enabled ? "Belum berjalan" : "Nonaktif"}</Badge>
          ))}
      </div>
      <QueryState query={settings}>
        {s && (
          <>
            {reason && s.reason !== "disabled" && (
              <p className="text-xs text-amber-700 dark:text-amber-400">{reason}</p>
            )}
            {(s.failure_count > 0 || s.last_error || s.next_attempt_at || s.in_flight) && (
              <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 rounded-lg border p-2 text-xs" style={{ borderColor: "var(--border)" }}>
                {s.in_flight && (
                  <>
                    <dt style={{ color: "var(--text-muted)" }}>Status</dt>
                    <dd style={{ color: "var(--text)" }}>Pengisian sedang diproses</dd>
                  </>
                )}
                {s.failure_count > 0 && (
                  <>
                    <dt style={{ color: "var(--text-muted)" }}>Gagal berturut</dt>
                    <dd style={{ color: "var(--text)" }}>{s.failure_count}×</dd>
                  </>
                )}
                {s.last_error && (
                  <>
                    <dt style={{ color: "var(--text-muted)" }}>Error terakhir</dt>
                    <dd className="text-red-600 dark:text-red-400">{s.last_error}</dd>
                  </>
                )}
                {s.next_attempt_at && (
                  <>
                    <dt style={{ color: "var(--text-muted)" }}>Coba lagi</dt>
                    <dd style={{ color: "var(--text)" }}>{formatDateTime(s.next_attempt_at)}</dd>
                  </>
                )}
              </dl>
            )}
            <SettingsForm key={`${s.enabled}-${s.threshold}`} settings={s} />
          </>
        )}
      </QueryState>
    </div>
  );
}
