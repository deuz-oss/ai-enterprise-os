import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

/**
 * Dialog modal umum (audit 2026-11-11 Phase 1, Top-20 #10).
 *
 * Menggantikan lima overlay buatan tangan (`<div className="fixed inset-0">`)
 * yang tidak punya semantik dialog: tanpa `role`, fokus bisa lari ke halaman
 * di belakangnya, dan fokus tidak kembali ke pemicu. Dibangun di atas
 * `<dialog>` native + `showModal()` -- sama seperti `ConfirmDialog` -- jadi
 * latar otomatis inert, Escape menutup, dan fokus terkurung tanpa dependency.
 *
 * Pemakaian: render saat terbuka saja, tutup lewat `onClose`.
 *
 *   {open && (
 *     <Dialog title="Preview Slip Gaji" onClose={() => setOpen(false)} size="lg">
 *       ...
 *     </Dialog>
 *   )}
 *
 * `ConfirmDialog` tetap untuk konfirmasi aksi; ini untuk konten/form bebas.
 * Catatan: toast sonner berada DI BAWAH top layer dialog modal -- tampilkan
 * error/sukses di dalam dialog, atau tutup dialog dulu.
 */

type DialogSize = "sm" | "md" | "lg";

const SIZE_CLASS: Record<DialogSize, string> = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
};

export interface DialogProps {
  /** Nama dialog untuk pembaca layar; tampil sebagai judul kecuali `bare`. */
  title: string;
  description?: ReactNode;
  onClose: () => void;
  size?: DialogSize;
  /** "top": menempel di atas (palet perintah, pratinjau tinggi). */
  position?: "center" | "top";
  /** Tanpa header & padding bawaan -- isi mengatur tata letaknya sendiri. */
  bare?: boolean;
  /** Kelas tambahan untuk elemen `<dialog>` (mis. latar gelap kamera). */
  className?: string;
  /** Kelas untuk pembungkus isi (di bawah header). */
  bodyClassName?: string;
  children: ReactNode;
}

export function Dialog({
  title,
  description,
  onClose,
  size = "md",
  position = "center",
  bare = false,
  className = "",
  bodyClassName = "",
  children,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  // Pemicu dicatat SEKALI: StrictMode (dev) menjalankan efek dua kali, dan pada
  // putaran kedua elemen aktif sudah berada di dalam dialog.
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (triggerRef.current === null) triggerRef.current = document.activeElement;
    const trigger = triggerRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => {
      // Kembalikan fokus ke pemicu setelah dialog BENAR-BENAR dilepas. Ditunda
      // satu tick + cek isConnected: StrictMode (dev) menjalankan cleanup ini
      // sekali saat dialog masih terpasang, dan saat itu fokus tidak boleh
      // dicuri keluar dari dialog.
      window.setTimeout(() => {
        if (dialog?.isConnected) return;
        if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
      }, 0);
    };
  }, []);

  // Tutup lewat `close()` native (bukan langsung `onClose`) supaya browser
  // ikut mengembalikan fokus; event `close` lalu memanggil `onClose`.
  const requestClose = () => {
    const dialog = ref.current;
    if (dialog?.open) dialog.close();
    else onClose();
  };

  return (
    <dialog
      ref={ref}
      // Dipicu Escape maupun `close()`; pemanggil melepas komponennya.
      onClose={onClose}
      // Klik pada backdrop = klik pada elemen <dialog> itu sendiri (isi
      // dibungkus div selebar dialog, jadi klik di isi tidak sampai ke sini).
      onClick={(e) => {
        if (e.target === e.currentTarget) requestClose();
      }}
      aria-labelledby={bare ? undefined : titleId}
      aria-label={bare ? title : undefined}
      aria-describedby={!bare && description ? descriptionId : undefined}
      className={`w-[calc(100%-2rem)] rounded-xl p-0 backdrop:bg-black/45 ${SIZE_CLASS[size]} ${
        position === "top" ? "mx-auto mb-auto mt-[8vh]" : "m-auto"
      } ${className}`}
      style={{
        backgroundColor: "var(--bg-elevated)",
        color: "var(--text)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-overlay)",
      }}
    >
      {bare ? (
        <div className={bodyClassName}>{children}</div>
      ) : (
        <div className="flex max-h-[calc(100vh-6rem)] flex-col">
          <div
            className="flex items-start justify-between gap-3 px-5 py-3"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <div className="space-y-1">
              <h2 id={titleId} className="text-base font-semibold">
                {title}
              </h2>
              {description && (
                <p id={descriptionId} className="text-sm" style={{ color: "var(--text-muted)" }}>
                  {description}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={requestClose}
              aria-label="Tutup"
              className="btn-ghost -mr-2 inline-flex h-8 w-8 shrink-0 items-center justify-center p-0"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <div className={`min-h-0 flex-1 overflow-y-auto ${bodyClassName || "p-5"}`}>{children}</div>
        </div>
      )}
    </dialog>
  );
}
