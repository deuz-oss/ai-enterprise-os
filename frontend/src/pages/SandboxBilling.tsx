import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import { api } from "../api/client";
import { PENDING_PM_KEY } from "../lib/billing";
import { CalloutBlock, PageHeader } from "../components/workspace";
import { Button } from "../components/ui";

/**
 * Halaman simulasi gateway untuk PAYMENT_PROVIDER=sandbox (non-produksi).
 * `checkout_url` / `action.url` dari adapter sandbox menunjuk ke sini; tombol
 * memanggil endpoint `/billing/sandbox/...` yang memproses event lewat jalur
 * webhook yang sama dengan Xendit, lalu kembali ke /billing. Di luar sandbox
 * endpoint itu 404 dan halaman ini hanya menampilkan error.
 */

function SandboxFrame({
  title,
  description,
  onSucceed,
  onFail,
}: {
  title: string;
  description: string;
  onSucceed: () => Promise<string>;
  onFail: (() => Promise<string>) | null;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState<"ok" | "fail" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(kind: "ok" | "fail", action: () => Promise<string>) {
    setBusy(kind);
    setError(null);
    try {
      navigate(await action(), { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulasi gagal");
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <PageHeader icon={FlaskConical} title={title} subtitle="Simulasi gateway pembayaran (sandbox)" />
      <CalloutBlock tone="warning">
        Halaman ini hanya untuk pengujian. Tidak ada uang yang ditagih. {description}
      </CalloutBlock>
      {error && <CalloutBlock tone="danger">{error}</CalloutBlock>}
      <div className="flex flex-wrap gap-2">
        <Button loading={busy === "ok"} disabled={busy !== null} onClick={() => run("ok", onSucceed)}>
          Simulasikan sukses
        </Button>
        {onFail && (
          <Button
            variant="danger"
            loading={busy === "fail"}
            disabled={busy !== null}
            onClick={() => run("fail", onFail)}
          >
            Simulasikan gagal
          </Button>
        )}
        <Button variant="ghost" disabled={busy !== null} onClick={() => navigate("/billing", { replace: true })}>
          Batal
        </Button>
      </div>
    </div>
  );
}

/** `/sandbox/billing/:invoiceId/pay` -- invoice langganan/top up/perpanjangan. */
export function SandboxInvoicePay() {
  const { invoiceId = "" } = useParams();
  return (
    <SandboxFrame
      title="Bayar tagihan"
      description={`Invoice ${invoiceId}.`}
      onSucceed={async () => {
        await api.post(`/billing/sandbox/invoices/${encodeURIComponent(invoiceId)}/pay`);
        return "/billing?checkout=success";
      }}
      // Invoice sandbox tidak punya event gagal -- "gagal" = tidak dibayar.
      onFail={async () => "/billing?checkout=failed"}
    />
  );
}

/** `/sandbox/billing/payment-methods/:referenceId/authorize` -- 3DS kartu / tautan GoPay. */
export function SandboxPaymentMethodAuthorize() {
  const { referenceId = "" } = useParams();
  const back = (result: "success" | "failed") => {
    let pmId: string | null = null;
    try {
      pmId = sessionStorage.getItem(PENDING_PM_KEY);
    } catch {
      /* abaikan */
    }
    return pmId
      ? `/billing?pm=${encodeURIComponent(pmId)}&result=${result}`
      : `/billing?pm_ref=${encodeURIComponent(referenceId)}&result=${result}`;
  };
  const ref = encodeURIComponent(referenceId);
  return (
    <SandboxFrame
      title="Otorisasi metode bayar"
      description="Menyetujui atau menolak aktivasi kartu (3DS) / penautan GoPay."
      onSucceed={async () => {
        await api.post(`/billing/sandbox/payment-methods/${ref}/activate`);
        return back("success");
      }}
      onFail={async () => {
        await api.post(`/billing/sandbox/payment-methods/${ref}/fail`);
        return back("failed");
      }}
    />
  );
}
