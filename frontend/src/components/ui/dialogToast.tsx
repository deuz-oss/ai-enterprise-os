import { useState, type KeyboardEvent } from "react";
import { toast } from "sonner";

/**
 * Pengganti window.confirm/window.prompt (2026-09-12, audit UI/UX) — dialog
 * native browser tidak bisa di-style dan mengkhianati look SaaS di seluruh
 * app. Dibangun di atas sonner (sudah dipasang <Toaster/> di Layout.tsx),
 * bukan komponen modal baru, supaya konsisten dengan satu sistem notifikasi.
 */

export function confirmToast(
  message: string,
  onConfirm: () => void,
  options?: { confirmLabel?: string; cancelLabel?: string }
) {
  toast(message, {
    action: { label: options?.confirmLabel ?? "Ya, lanjutkan", onClick: onConfirm },
    cancel: { label: options?.cancelLabel ?? "Batal", onClick: () => {} },
  });
}

function PromptToastBody({
  toastId,
  message,
  defaultValue,
  placeholder,
  onSubmit,
}: {
  toastId: string | number;
  message: string;
  defaultValue: string;
  placeholder?: string;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState(defaultValue);

  const submit = () => {
    onSubmit(value);
    toast.dismiss(toastId);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") submit();
    if (e.key === "Escape") toast.dismiss(toastId);
  };

  return (
    <div className="flex w-full flex-col gap-2">
      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
        {message}
      </p>
      <input
        autoFocus
        className="input text-sm"
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="flex justify-end gap-2">
        <button className="btn-ghost text-xs" onClick={() => toast.dismiss(toastId)}>
          Batal
        </button>
        <button className="btn-secondary text-xs" onClick={submit}>
          Kirim
        </button>
      </div>
    </div>
  );
}

/** Pengganti window.prompt — mengembalikan nilai lewat callback (async), bukan return value (sync). */
export function promptToast(
  message: string,
  onSubmit: (value: string) => void,
  options?: { defaultValue?: string; placeholder?: string }
) {
  toast.custom(
    (id) => (
      <PromptToastBody
        toastId={id}
        message={message}
        defaultValue={options?.defaultValue ?? ""}
        placeholder={options?.placeholder}
        onSubmit={onSubmit}
      />
    ),
    { duration: Infinity }
  );
}
