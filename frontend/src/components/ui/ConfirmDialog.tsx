import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

/**
 * Dialog konfirmasi modal untuk aksi yang TIDAK BISA DIBATALKAN (finalisasi
 * payroll, batal e-Faktur, posting jurnal, kirim email ke pihak luar, dst.) --
 * audit 2026-10-08 (docs/design/FULL_AUDIT-2026-10-08.md §9). `confirmToast`
 * tetap dipakai untuk aksi ringan (hapus item kecil); toast tidak modal dan
 * mudah terlewat, jadi tidak cocok untuk aksi berisiko tinggi.
 *
 * Dibangun di atas `<dialog>` native (`showModal()`): latar otomatis inert,
 * Escape menutup, fokus terkurung di dialog -- tanpa dependency baru. Fokus
 * awal di tombol Batal (default aman), lalu dikembalikan ke elemen pemicu.
 *
 * Pakai imperatif seperti confirmToast: `confirmDialog({...})`. Host-nya
 * (`<ConfirmDialogHost />`) dipasang sekali di Layout.tsx.
 */

export interface ConfirmDialogOptions {
  title: string;
  /** Konsekuensi aksi, ditulis eksplisit (apa yang terjadi & bisa/tidak dibatalkan). */
  message: string;
  confirmLabel: string;
  tone?: "danger" | "primary";
  /** Kalau diisi, user wajib mengetik teks ini persis sebelum tombol aktif. */
  requireText?: string;
  /** Konten tambahan di bawah pesan (mis. hasil tinjauan sebelum finalisasi). */
  details?: ReactNode;
  /** Kolom teks opsional (mis. alasan); nilainya diteruskan ke onConfirm. */
  input?: {
    label: string;
    placeholder?: string;
    /** Kembalikan pesan error untuk menonaktifkan tombol konfirmasi, atau null. */
    validate?: (value: string) => string | null;
  };
  onConfirm: (inputValue: string) => void;
}

type Listener = (options: ConfirmDialogOptions) => void;
let listener: Listener | null = null;

export function confirmDialog(options: ConfirmDialogOptions) {
  if (listener) {
    listener(options);
    return;
  }
  // Host belum terpasang (mis. halaman publik): jangan pernah menjalankan aksi
  // tanpa konfirmasi -- lebih baik gagal terlihat di dev.
  console.error("confirmDialog dipanggil tanpa <ConfirmDialogHost /> terpasang");
}

export function ConfirmDialogHost() {
  const [options, setOptions] = useState<ConfirmDialogOptions | null>(null);
  const [typed, setTyped] = useState("");
  const [inputValue, setInputValue] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    listener = (next) => {
      triggerRef.current = document.activeElement;
      setTyped("");
      setInputValue("");
      setOptions(next);
    };
    return () => {
      listener = null;
    };
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!options || !dialog) return;
    if (!dialog.open) dialog.showModal();
    if (!options.requireText) cancelRef.current?.focus();
  }, [options]);

  function close() {
    dialogRef.current?.close();
  }

  // Dipanggil untuk semua jalur tutup (Batal, Escape, submit) lewat event `close`.
  function handleClosed() {
    setOptions(null);
    const trigger = triggerRef.current;
    if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!options || !canConfirm) return;
    const run = options.onConfirm;
    const value = inputValue.trim();
    close();
    run(value);
  }

  const inputError = options?.input?.validate ? options.input.validate(inputValue.trim()) : null;
  const canConfirm = (!options?.requireText || typed.trim() === options.requireText) && !inputError;
  const danger = (options?.tone ?? "danger") === "danger";

  return (
    <dialog
      ref={dialogRef}
      onClose={handleClosed}
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-message"
      className={`m-auto w-[calc(100%-2rem)] rounded-xl p-0 backdrop:bg-black/45 ${
        options?.details ? "max-w-2xl" : "max-w-md"
      }`}
      style={{
        backgroundColor: "var(--bg-elevated)",
        color: "var(--text)",
        border: "1px solid var(--border)",
        boxShadow: "0 12px 40px rgba(15,15,15,0.25)",
      }}
    >
      {options && (
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="flex gap-3">
            {danger && (
              <span
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                style={{ backgroundColor: "var(--danger-tint)", color: "var(--danger)" }}
                aria-hidden="true"
              >
                <AlertTriangle className="h-5 w-5" />
              </span>
            )}
            <div className="space-y-1.5">
              <h2 id="confirm-dialog-title" className="text-base font-semibold">
                {options.title}
              </h2>
              <p id="confirm-dialog-message" className="text-sm" style={{ color: "var(--text-muted)" }}>
                {options.message}
              </p>
            </div>
          </div>

          {options.details && (
            <div className="max-h-[50vh] overflow-y-auto rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
              {options.details}
            </div>
          )}

          {options.input && (
            <div className="space-y-1.5">
              <label htmlFor="confirm-dialog-extra" className="block text-sm">
                {options.input.label}
              </label>
              <textarea
                id="confirm-dialog-extra"
                className="input min-h-[72px]"
                placeholder={options.input.placeholder}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                aria-invalid={inputError ? true : undefined}
                aria-describedby={inputError ? "confirm-dialog-extra-error" : undefined}
              />
              {inputError && (
                <p id="confirm-dialog-extra-error" className="text-xs" style={{ color: "var(--danger)" }}>
                  {inputError}
                </p>
              )}
            </div>
          )}

          {options.requireText && (
            <div className="space-y-1.5">
              <label htmlFor="confirm-dialog-input" className="block text-sm">
                Ketik <strong className="font-mono">{options.requireText}</strong> untuk melanjutkan
              </label>
              <input
                id="confirm-dialog-input"
                className="input font-mono"
                autoComplete="off"
                autoFocus
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
              />
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button ref={cancelRef} type="button" className="btn-secondary" onClick={close}>
              Batal
            </button>
            <button type="submit" className={danger ? "btn-danger" : "btn"} disabled={!canConfirm}>
              {options.confirmLabel}
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}
