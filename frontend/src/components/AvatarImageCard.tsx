import { useEffect, useId, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { UserRound } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, formatDateTime, previewFile } from "../api/client";
import { confirmDialog } from "./ui/ConfirmDialog";
import { AVATAR_ACCEPT_ATTR, validateAvatarFile } from "../lib/avatarImage";

/** Respons `GET/PUT /ai-interview/settings` (+ endpoint avatar-image). */
export interface AiInterviewSettings {
  retention_days: number;
  has_avatar_image: boolean;
  avatar_image_updated_at: string | null;
}

const SETTINGS_KEY = ["ai-interview-settings"];
const AVATAR_PATH = "/ai-interview/settings/avatar-image";

/**
 * Kartu "Foto avatar pewawancara" di pengaturan AI Interview. Foto dipakai
 * sebagai wajah pewawancara AI pada interview suara bila mode avatar aktif di
 * server; kosong = foto default deployment. Hanya wajah PEWAWANCARA -- produk
 * tidak menganalisis wajah/ekspresi kandidat.
 */
export function AvatarImageCard({ settings }: { settings: AiInterviewSettings | undefined }) {
  const qc = useQueryClient();
  const uid = useId();
  const ids = {
    file: `${uid}-file`,
    help: `${uid}-help`,
    fileError: `${uid}-file-error`,
    consent: `${uid}-consent`,
  };
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasImage = Boolean(settings?.has_avatar_image);
  const updatedAt = settings?.avatar_image_updated_at ?? null;

  // --- Pratinjau foto tersimpan (butuh token -> blob -> object URL) ---
  // Sengaja useEffect, bukan useQuery: object URL harus di-revoke saat ganti /
  // unmount, dan cache query bisa mengembalikan URL yang sudah di-revoke saat
  // komponen dipasang ulang (mis. StrictMode).
  const [savedUrl, setSavedUrl] = useState<string | null>(null);
  const [savedState, setSavedState] = useState<"idle" | "loading" | "missing" | "error">("idle");
  useEffect(() => {
    if (!hasImage) {
      setSavedUrl(null);
      setSavedState("idle");
      return;
    }
    let cancelled = false;
    let url: string | null = null;
    setSavedState("loading");
    // `updatedAt` di query string memaksa browser/proxy tidak memakai cache lama.
    const bust = updatedAt ? `?v=${encodeURIComponent(updatedAt)}` : "";
    previewFile(`${AVATAR_PATH}${bust}`)
      .then((objectUrl) => {
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        url = objectUrl;
        setSavedUrl(objectUrl);
        setSavedState("idle");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSavedUrl(null);
        setSavedState(err instanceof ApiError && err.status === 404 ? "missing" : "error");
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [hasImage, updatedAt]);

  // --- File terpilih (belum diunggah) ---
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [consent, setConsent] = useState(false);
  const [localUrl, setLocalUrl] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const selectSeq = useRef(0);

  useEffect(() => {
    if (!file) {
      setLocalUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setLocalUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function resetSelection() {
    setFile(null);
    setFileError(null);
    setConsent(false);
    setChecking(false);
    selectSeq.current += 1;
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setStatus("");
    setActionError(null);
    setFile(null);
    setFileError(null);
    if (!picked) return;
    const seq = ++selectSeq.current;
    setChecking(true);
    const error = await validateAvatarFile(picked);
    if (seq !== selectSeq.current) return; // user sudah memilih file lain
    setChecking(false);
    if (error) {
      setFileError(error);
      return;
    }
    setFile(picked);
  }

  const upload = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("consent", "true");
      return api.upload<AiInterviewSettings>(AVATAR_PATH, fd, "PUT");
    },
    onSuccess: (data) => {
      qc.setQueryData(SETTINGS_KEY, data);
      qc.invalidateQueries({ queryKey: SETTINGS_KEY });
      resetSelection();
      setStatus("Foto avatar pewawancara tersimpan.");
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const remove = useMutation({
    mutationFn: () => api.delete<AiInterviewSettings>(AVATAR_PATH),
    onSuccess: (data) => {
      if (data) qc.setQueryData(SETTINGS_KEY, data);
      qc.invalidateQueries({ queryKey: SETTINGS_KEY });
      setStatus("Foto avatar dihapus. Interview memakai foto default deployment.");
    },
    onError: (err: Error) => setActionError(err.message),
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!file || !consent || upload.isPending) return;
    setStatus("");
    setActionError(null);
    upload.mutate(file);
  }

  function handleDelete() {
    setStatus("");
    setActionError(null);
    confirmDialog({
      title: "Hapus foto avatar pewawancara?",
      message:
        "Foto ini dihapus permanen dari server. Interview suara berikutnya memakai foto default deployment sampai Anda mengunggah foto baru.",
      confirmLabel: "Hapus foto",
      tone: "danger",
      onConfirm: () => remove.mutate(),
    });
  }

  const busy = upload.isPending || remove.isPending;
  const canUpload = Boolean(file) && consent && !checking && !busy;
  const describedBy = fileError ? `${ids.help} ${ids.fileError}` : ids.help;

  const previewSrc = localUrl ?? savedUrl;
  const previewAlt = localUrl
    ? "Pratinjau foto terpilih untuk wajah pewawancara AI (belum diunggah)"
    : "Foto wajah pewawancara AI yang sedang dipakai";

  return (
    <section className="card space-y-3" aria-labelledby={`${uid}-title`}>
      <div className="flex min-w-0 items-start gap-2.5">
        <UserRound className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--accent)" }} aria-hidden="true" />
        <div className="min-w-0">
          <h2 id={`${uid}-title`} className="text-sm font-medium text-[var(--text)]">
            Foto avatar pewawancara
          </h2>
          <p className="text-xs text-[var(--text-muted)]">
            Dipakai sebagai wajah pewawancara AI pada interview suara bila mode avatar diaktifkan di
            server. Bila kosong, dipakai foto default deployment. Foto hanya untuk tampilan
            pewawancara; wajah dan ekspresi kandidat tidak dianalisis.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        {/* Pratinjau */}
        <div className="flex shrink-0 flex-col items-center gap-1.5 sm:w-32">
          <div
            className="flex h-28 w-28 items-center justify-center overflow-hidden rounded-lg border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}
          >
            {previewSrc ? (
              <img src={previewSrc} alt={previewAlt} className="h-full w-full object-cover" />
            ) : (
              <UserRound className="h-10 w-10 text-[var(--text-muted)]" aria-hidden="true" />
            )}
          </div>
          <p className="text-center text-xs text-[var(--text-muted)]">
            {localUrl
              ? "Pratinjau (belum diunggah)"
              : hasImage && savedState === "loading"
                ? "Memuat foto…"
                : hasImage && savedState === "error"
                  ? "Foto tersimpan gagal dimuat"
                  : hasImage && savedState !== "missing"
                    ? updatedAt
                      ? `Diperbarui ${formatDateTime(updatedAt)}`
                      : "Foto khusus tenant"
                    : "Memakai foto default deployment"}
          </p>
        </div>

        {/* Form unggah */}
        <form className="min-w-0 flex-1 space-y-3" onSubmit={handleSubmit} noValidate>
          <div className="space-y-1.5">
            <label htmlFor={ids.file} className="block text-xs font-medium text-[var(--text)]">
              {hasImage ? "Pilih foto pengganti" : "Pilih foto"}
            </label>
            <input
              ref={fileInputRef}
              id={ids.file}
              type="file"
              accept={AVATAR_ACCEPT_ATTR}
              className="input w-full py-1 text-sm"
              onChange={handleFileChange}
              disabled={busy}
              aria-describedby={describedBy}
              aria-invalid={fileError ? true : undefined}
            />
            <p id={ids.help} className="text-xs text-[var(--text-muted)]">
              Foto wajah satu orang, menghadap depan, pencahayaan jelas. JPEG/PNG/WebP, maks 5 MB,
              minimal 256×256 px.
            </p>
            {checking && (
              <p className="text-xs text-[var(--text-muted)]">Memeriksa foto…</p>
            )}
            {fileError && (
              <p id={ids.fileError} className="text-xs" style={{ color: "var(--danger)" }}>
                {fileError}
              </p>
            )}
          </div>

          <div className="flex items-start gap-2">
            <input
              id={ids.consent}
              type="checkbox"
              className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              disabled={busy}
            />
            <label htmlFor={ids.consent} className="text-xs text-[var(--text)]">
              Saya memiliki izin untuk memakai foto ini sebagai wajah pewawancara AI.
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button type="submit" className="btn py-1 text-xs" disabled={!canUpload}>
              {upload.isPending ? "Mengunggah…" : hasImage ? "Ganti foto" : "Unggah foto"}
            </button>
            {file && !busy && (
              <button type="button" className="btn-secondary py-1 text-xs" onClick={resetSelection}>
                Batal pilih
              </button>
            )}
            {hasImage && (
              <button
                type="button"
                className="btn-secondary py-1 text-xs"
                style={{ color: "var(--danger)" }}
                onClick={handleDelete}
                disabled={busy}
              >
                {remove.isPending ? "Menghapus…" : "Hapus foto"}
              </button>
            )}
          </div>

          <p role="status" aria-live="polite" className="text-xs" style={{ color: "var(--success)" }}>
            {status}
          </p>
          {actionError && (
            <p role="alert" className="text-xs" style={{ color: "var(--danger)" }}>
              {actionError}
            </p>
          )}
        </form>
      </div>
    </section>
  );
}
