import { useState } from "react";
import { formatRupiah } from "../api/client";
import { describeSalaryChange } from "../lib/salary";
import { confirmDialog } from "./ui/ConfirmDialog";
import { CurrencyInput } from "./ui/CurrencyInput";

/**
 * Edit gaji pokok dengan pengaman (audit 2026-11-11 Top-20 #5).
 *
 * Dulu: `<input type="number">` tanpa label + satu klik Simpan -- salah ketik
 * satu nol langsung tersimpan tanpa pesan. Kini: nominal berformat ribuan,
 * lalu dialog konfirmasi yang menampilkan lama -> baru beserta persentasenya;
 * perubahan besar diberi peringatan. Tidak ada perubahan = tutup tanpa request.
 */
export function SalaryEditForm({
  current,
  pending,
  onSave,
  onUnchanged,
}: {
  current: number;
  pending: boolean;
  onSave: (next: number) => void;
  onUnchanged: () => void;
}) {
  const [value, setValue] = useState<number | null>(current);
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (value === null) {
      setError("Isi nominal gaji pokok.");
      return;
    }
    if (value === current) {
      onUnchanged();
      return;
    }
    const change = describeSalaryChange(current, value);
    confirmDialog({
      title: "Ubah gaji pokok?",
      message:
        `${formatRupiah(current)} → ${formatRupiah(value)} per bulan (${change.summary}). ` +
        "Dipakai payroll, BPJS, dan PPh 21 mulai run berikutnya; perubahan dicatat di audit.",
      details: change.large ? (
        <p className="text-sm" style={{ color: "var(--danger)" }}>
          Perubahan ini besar ({change.summary}). Periksa lagi jumlah nolnya sebelum menyimpan.
        </p>
      ) : undefined,
      confirmLabel: "Simpan Gaji",
      tone: change.large ? "danger" : "primary",
      onConfirm: () => onSave(value),
    });
  }

  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <CurrencyInput
        autoFocus
        value={value}
        onChange={(next) => {
          setValue(next);
          setError(null);
        }}
        aria-label="Gaji pokok per bulan (rupiah)"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? "salary-edit-error" : undefined}
        className="input w-36 py-1 text-xs"
      />
      <button disabled={pending} className="btn-secondary py-1 text-xs">
        Simpan
      </button>
      {error && (
        <span id="salary-edit-error" role="alert" className="text-xs" style={{ color: "var(--danger)" }}>
          {error}
        </span>
      )}
    </form>
  );
}
