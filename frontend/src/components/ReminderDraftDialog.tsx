import { useEffect, useRef, useState } from "react";
import { Copy, Mail, Sparkles } from "lucide-react";

/** Respons `POST /finance/invoices/{id}/reminder-draft` (backend finance/reminder.py). */
export interface ReminderDraft {
  invoice_id: string;
  to: string | null;
  subject: string;
  body: string;
  days_overdue: number;
  source: "ai" | "template";
}

/**
 * Draf email pengingat pembayaran (audit 2026-10-08 Phase 6). Aplikasi TIDAK
 * mengirim apa pun: user menyunting, menyalin, atau membuka di aplikasi email
 * sendiri. Umpan balik "Tersalin" ditampilkan di dalam dialog karena toast
 * sonner berada di bawah top layer <dialog> modal.
 */
export function ReminderDraftDialog({ draft, onClose }: { draft: ReminderDraft; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(`${subject}\n\n${body}`);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const mailto = `mailto:${draft.to ?? ""}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="reminder-title"
      className="m-auto w-[calc(100%-2rem)] max-w-2xl rounded-xl p-0 backdrop:bg-black/45"
      style={{ backgroundColor: "var(--bg-elevated)", color: "var(--text)", border: "1px solid var(--border)" }}
    >
      <div className="space-y-3 p-5">
        <div>
          <h2 id="reminder-title" className="text-base font-semibold">
            Draf pengingat pembayaran
          </h2>
          <p className="text-sm" style={{ color: "var(--th-color)" }}>
            Terlambat {draft.days_overdue} hari. Tidak dikirim otomatis -- periksa, sunting, lalu kirim dari email Anda.
          </p>
        </div>
        {draft.source === "ai" && (
          <p className="flex items-center gap-1.5 text-xs" style={{ color: "var(--th-color)" }}>
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Disusun AI dari data invoice; nomor &amp; nominal sudah
            dicocokkan dengan sistem.
          </p>
        )}
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Kepada</span>
          <input className="input" value={draft.to ?? ""} readOnly placeholder="Email PIC klien belum diisi" />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Subjek</span>
          <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} />
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium">Isi</span>
          <textarea className="input min-h-[220px]" value={body} onChange={(e) => setBody(e.target.value)} />
        </label>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {copied && (
            <span role="status" className="mr-auto text-sm" style={{ color: "var(--success)" }}>
              Tersalin ke clipboard.
            </span>
          )}
          <button type="button" className="btn-secondary" onClick={() => ref.current?.close()}>
            Tutup
          </button>
          <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={copy}>
            <Copy className="h-4 w-4" aria-hidden="true" /> Salin
          </button>
          <a className="btn inline-flex items-center gap-1.5" href={mailto}>
            <Mail className="h-4 w-4" aria-hidden="true" /> Buka di email
          </a>
        </div>
      </div>
    </dialog>
  );
}
