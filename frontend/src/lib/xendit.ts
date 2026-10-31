/**
 * Tokenisasi kartu di browser lewat Xendit.js. Nomor kartu/CVN hanya
 * diteruskan ke Xendit.js dan TIDAK PERNAH dikirim ke backend AEOS -- backend
 * hanya menerima `card_token_id` (skema `PaymentMethodIn` extra="forbid").
 *
 * TODO verifikasi: bentuk API Xendit.js (`Xendit.setPublishableKey`,
 * `Xendit.card.createToken(data, cb)`, field `is_multiple_use` /
 * `should_authenticate`, status token "VERIFIED") diambil dari dokumentasi
 * Xendit.js v1 dan belum diuji terhadap akun Xendit sungguhan, termasuk
 * apakah token multi-use ini diterima Payment Methods API v2 sebagai
 * `card_token_id`. Uji di mode test Xendit sebelum produksi.
 */

const XENDIT_JS_URL = "https://js.xendit.co/v1/xendit.min.js";

interface XenditToken {
  id: string;
  status: string;
  payer_authentication_url?: string;
  failure_reason?: string;
}

interface XenditError {
  error_code?: string;
  message?: string;
}

interface XenditGlobal {
  setPublishableKey: (key: string) => void;
  card: {
    createToken: (
      data: Record<string, unknown>,
      cb: (err: XenditError | null, token: XenditToken) => void
    ) => void;
  };
}

declare global {
  interface Window {
    Xendit?: XenditGlobal;
  }
}

let loading: Promise<XenditGlobal> | null = null;

export function loadXendit(): Promise<XenditGlobal> {
  if (window.Xendit) return Promise.resolve(window.Xendit);
  if (loading) return loading;
  loading = new Promise<XenditGlobal>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = XENDIT_JS_URL;
    script.async = true;
    script.onload = () => {
      if (window.Xendit) resolve(window.Xendit);
      else reject(new Error("Xendit.js termuat tetapi objek Xendit tidak ditemukan."));
    };
    script.onerror = () => {
      loading = null;
      reject(new Error("Gagal memuat Xendit.js. Periksa koneksi lalu coba lagi."));
    };
    document.head.appendChild(script);
  });
  return loading;
}

export interface CardInput {
  number: string;
  expMonth: string;
  expYear: string;
  cvn: string;
}

/** Kembalikan id token kartu multi-use. Melempar Error dengan pesan siap tampil. */
export async function tokenizeCard(publicKey: string, card: CardInput): Promise<string> {
  const xendit = await loadXendit();
  xendit.setPublishableKey(publicKey);
  const year = card.expYear.trim().length === 2 ? `20${card.expYear.trim()}` : card.expYear.trim();
  return new Promise<string>((resolve, reject) => {
    xendit.card.createToken(
      {
        card_number: card.number.replace(/\s/g, ""),
        card_exp_month: card.expMonth.trim().padStart(2, "0"),
        card_exp_year: year,
        card_cvn: card.cvn.trim(),
        is_multiple_use: true,
        should_authenticate: false,
      },
      (err, token) => {
        if (err) {
          reject(new Error(err.message || err.error_code || "Tokenisasi kartu gagal."));
          return;
        }
        if (token.status !== "VERIFIED") {
          reject(new Error(token.failure_reason || `Kartu belum terverifikasi (status ${token.status}).`));
          return;
        }
        resolve(token.id);
      }
    );
  });
}
