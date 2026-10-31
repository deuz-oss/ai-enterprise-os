// Validasi sisi klien untuk foto avatar pewawancara AI (pengaturan AI
// Interview). Backend tetap memvalidasi ulang (sumber kebenaran); ini hanya
// supaya user dapat pesan cepat sebelum file besar terunggah.

export const AVATAR_ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const AVATAR_ACCEPT_ATTR = AVATAR_ACCEPTED_TYPES.join(",");
export const AVATAR_MAX_BYTES = 5 * 1024 * 1024;
export const AVATAR_MIN_DIMENSION = 256;

/** Cek tipe & ukuran file. Kembalikan pesan error (Bahasa Indonesia) atau null. */
export function validateAvatarFileMeta(file: { type: string; size: number }): string | null {
  if (!(AVATAR_ACCEPTED_TYPES as readonly string[]).includes(file.type)) {
    return "Format tidak didukung. Pakai JPEG, PNG, atau WebP.";
  }
  if (file.size <= 0) {
    return "File kosong. Pilih foto lain.";
  }
  if (file.size > AVATAR_MAX_BYTES) {
    const mb = (file.size / (1024 * 1024)).toLocaleString("id-ID", { maximumFractionDigits: 1 });
    return `Ukuran file ${mb} MB melebihi batas 5 MB.`;
  }
  return null;
}

/** Cek dimensi gambar minimum. Kembalikan pesan error atau null. */
export function validateAvatarDimensions(width: number, height: number): string | null {
  if (width < AVATAR_MIN_DIMENSION || height < AVATAR_MIN_DIMENSION) {
    return `Resolusi foto ${width}×${height} px terlalu kecil. Minimal ${AVATAR_MIN_DIMENSION}×${AVATAR_MIN_DIMENSION} px.`;
  }
  return null;
}

/** Baca dimensi gambar di browser. `null` = tidak bisa dibaca (file rusak /
 * browser tidak mendukung formatnya) -- pemanggil menganggapnya error. */
export async function readImageDimensions(
  file: Blob
): Promise<{ width: number; height: number } | null> {
  if (typeof createImageBitmap === "function") {
    try {
      const bitmap = await createImageBitmap(file);
      const dims = { width: bitmap.width, height: bitmap.height };
      bitmap.close();
      return dims;
    } catch {
      // Jatuh ke <img> di bawah (mis. Safari lama untuk WebP).
    }
  }
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });
}

/** Validasi lengkap (tipe, ukuran, dimensi). Kembalikan pesan error atau null. */
export async function validateAvatarFile(file: File): Promise<string | null> {
  const metaError = validateAvatarFileMeta(file);
  if (metaError) return metaError;
  const dims = await readImageDimensions(file);
  if (!dims) return "Foto tidak bisa dibaca. Pastikan file gambar tidak rusak.";
  return validateAvatarDimensions(dims.width, dims.height);
}
