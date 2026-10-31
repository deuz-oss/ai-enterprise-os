import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CreditCard, Loader2, Smartphone, Star, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, formatDate } from "../../api/client";
import {
  isForceableDeleteConflict,
  parsePmReturn,
  PM_STATUS_META,
  pmIdFromReference,
  pmPollState,
  PENDING_PM_KEY,
  SANDBOX_CARD_TOKENS,
  type PaymentConfig,
  type PaymentMethod,
  type PaymentMethodCreated,
} from "../../lib/billing";
import { tokenizeCard } from "../../lib/xendit";
import { CalloutBlock } from "../workspace";
import { Badge, Button, confirmDialog, DataTable, type Column } from "../ui";
import { useInvalidateBilling } from "./hooks";

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS = 90_000;

function AddPaymentMethodForm({ config, onAdded }: { config: PaymentConfig; onAdded: (pm: PaymentMethodCreated) => void }) {
  const [type, setType] = useState<"card" | "gopay">("card");
  const [sandboxToken, setSandboxToken] = useState<string>(SANDBOX_CARD_TOKENS[0].value);
  // Data kartu hanya hidup di state komponen ini dan diteruskan ke Xendit.js --
  // TIDAK PERNAH masuk body request ke backend AEOS.
  const [card, setCard] = useState({ number: "", expMonth: "", expYear: "", cvn: "" });
  const [error, setError] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: async (): Promise<PaymentMethodCreated> => {
      if (type === "gopay") return api.post<PaymentMethodCreated>("/billing/payment-methods", { type: "gopay" });
      let tokenId: string;
      if (config.provider === "sandbox") {
        tokenId = sandboxToken;
      } else {
        if (!config.xendit_public_key) throw new Error("Kunci publik Xendit belum dikonfigurasi.");
        tokenId = await tokenizeCard(config.xendit_public_key, card);
      }
      return api.post<PaymentMethodCreated>("/billing/payment-methods", { type: "card", card_token_id: tokenId });
    },
    onSuccess: (pm) => {
      setError(null);
      setCard({ number: "", expMonth: "", expYear: "", cvn: "" });
      onAdded(pm);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal menambah metode bayar"),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    add.mutate();
  }

  const supports = (t: "card" | "gopay") => config.supported_types.includes(t);

  return (
    <form onSubmit={submit} className="card space-y-3" aria-labelledby="add-pm-title">
      <h3 id="add-pm-title" className="text-sm font-semibold" style={{ color: "var(--text)" }}>
        Tambah metode bayar
      </h3>
      <fieldset className="flex flex-wrap gap-4 text-sm" style={{ color: "var(--text)" }}>
        <legend className="sr-only">Jenis metode bayar</legend>
        {supports("card") && (
          <label className="flex items-center gap-2">
            <input type="radio" name="pm_type" checked={type === "card"} onChange={() => setType("card")} />
            <CreditCard className="h-4 w-4" aria-hidden="true" /> Kartu kredit/debit
          </label>
        )}
        {supports("gopay") && (
          <label className="flex items-center gap-2">
            <input type="radio" name="pm_type" checked={type === "gopay"} onChange={() => setType("gopay")} />
            <Smartphone className="h-4 w-4" aria-hidden="true" /> GoPay
          </label>
        )}
      </fieldset>

      {type === "card" && config.provider === "sandbox" && (
        <label className="block text-xs" style={{ color: "var(--text-muted)" }}>
          Token kartu uji (sandbox)
          <select className="input mt-1 w-full" value={sandboxToken} onChange={(e) => setSandboxToken(e.target.value)}>
            {SANDBOX_CARD_TOKENS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.value} — {t.label}
              </option>
            ))}
          </select>
        </label>
      )}

      {type === "card" && config.provider === "xendit" && (
        <div className="grid grid-cols-6 gap-2">
          <label className="col-span-6 block text-xs" style={{ color: "var(--text-muted)" }}>
            Nomor kartu
            <input
              className="input mt-1 w-full font-mono"
              inputMode="numeric"
              autoComplete="cc-number"
              required
              value={card.number}
              onChange={(e) => setCard({ ...card, number: e.target.value })}
            />
          </label>
          <label className="col-span-2 block text-xs" style={{ color: "var(--text-muted)" }}>
            Bulan (MM)
            <input
              className="input mt-1 w-full"
              inputMode="numeric"
              autoComplete="cc-exp-month"
              maxLength={2}
              required
              value={card.expMonth}
              onChange={(e) => setCard({ ...card, expMonth: e.target.value })}
            />
          </label>
          <label className="col-span-2 block text-xs" style={{ color: "var(--text-muted)" }}>
            Tahun (YYYY)
            <input
              className="input mt-1 w-full"
              inputMode="numeric"
              autoComplete="cc-exp-year"
              maxLength={4}
              required
              value={card.expYear}
              onChange={(e) => setCard({ ...card, expYear: e.target.value })}
            />
          </label>
          <label className="col-span-2 block text-xs" style={{ color: "var(--text-muted)" }}>
            CVN
            <input
              className="input mt-1 w-full"
              inputMode="numeric"
              autoComplete="cc-csc"
              maxLength={4}
              required
              value={card.cvn}
              onChange={(e) => setCard({ ...card, cvn: e.target.value })}
            />
          </label>
          <p className="col-span-6 text-xs" style={{ color: "var(--text-muted)" }}>
            Data kartu diproses langsung oleh Xendit dan tidak disimpan di server AEOS.
          </p>
        </div>
      )}

      {type === "gopay" && (
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Anda akan diarahkan ke GoPay untuk menautkan akun, lalu kembali ke halaman ini.
        </p>
      )}

      {error && (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <Button type="submit" loading={add.isPending}>
        {type === "gopay" ? "Tautkan GoPay" : "Simpan kartu"}
      </Button>
    </form>
  );
}

export function PaymentMethodsSection() {
  const invalidate = useInvalidateBilling();
  const [searchParams, setSearchParams] = useSearchParams();
  const returned = parsePmReturn(`?${searchParams.toString()}`);
  const pollStartRef = useRef<number>(Date.now());
  const [pollingId, setPollingId] = useState<string | null>(returned?.pmId ?? null);

  const config = useQuery({
    queryKey: ["billing-payment-config"],
    queryFn: () => api.get<PaymentConfig>("/billing/payment-config"),
    staleTime: 10 * 60_000,
  });
  const methods = useQuery({
    queryKey: ["billing-payment-methods"],
    queryFn: () => api.get<PaymentMethod[]>("/billing/payment-methods"),
    refetchInterval: (q) => {
      if (!pollingId) return false;
      if (Date.now() - pollStartRef.current > POLL_TIMEOUT_MS) return false;
      return pmPollState(q.state.data, pollingId) === "pending" ? POLL_INTERVAL_MS : false;
    },
  });

  // `?pm_ref=` (dari halaman sandbox tanpa id) -> resolve ke id setelah list termuat.
  useEffect(() => {
    if (pollingId || !returned?.pmRef || !methods.data) return;
    const id = pmIdFromReference(returned.pmRef, methods.data);
    if (id) {
      pollStartRef.current = Date.now();
      setPollingId(id);
    }
  }, [pollingId, returned?.pmRef, methods.data]);

  // Selesaikan polling saat status final, lalu bersihkan parameter URL.
  const pollState = pmPollState(methods.data, pollingId);
  const timedOut = pollingId !== null && pollState === "pending" && Date.now() - pollStartRef.current > POLL_TIMEOUT_MS;
  useEffect(() => {
    if (!pollingId || !methods.data) return;
    if (pollState === "pending" && !timedOut) return;
    const pm = methods.data.find((m) => m.id === pollingId);
    if (pollState === "active") toast.success(`${pm?.label ?? "Metode bayar"} aktif.`);
    else if (pollState === "failed")
      toast.error(`Aktivasi gagal${pm?.failure_reason ? `: ${pm.failure_reason}` : ""}.`);
    else if (timedOut) toast.info("Aktivasi masih diproses. Muat ulang halaman beberapa saat lagi.");
    try {
      sessionStorage.removeItem(PENDING_PM_KEY);
    } catch {
      /* sessionStorage tidak tersedia -- abaikan */
    }
    setPollingId(null);
    const next = new URLSearchParams(searchParams);
    next.delete("pm");
    next.delete("pm_ref");
    next.delete("result");
    setSearchParams(next, { replace: true });
    invalidate();
    // Dependensi sengaja dibatasi ke hasil polling (searchParams/invalidate tidak memicu ulang).
  }, [pollState, timedOut, pollingId, methods.data]);

  // refetchInterval berhenti setelah batas waktu tanpa memicu render -- paksa
  // satu render ulang supaya `timedOut` terevaluasi dan polling ditutup.
  const [, forceRender] = useState(0);
  useEffect(() => {
    if (!pollingId) return;
    const t = window.setTimeout(() => forceRender((n) => n + 1), POLL_TIMEOUT_MS + 500);
    return () => window.clearTimeout(t);
  }, [pollingId]);

  const setDefault = useMutation({
    mutationFn: (id: string) => api.post<PaymentMethod[]>(`/billing/payment-methods/${id}/default`),
    onSuccess: () => {
      toast.success("Metode bayar default diperbarui");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Gagal mengubah default"),
  });
  const remove = useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) =>
      api.delete<void>(`/billing/payment-methods/${id}${force ? "?force=true" : ""}`),
    onSuccess: (_res, vars) => {
      toast.success(vars.force ? "Metode bayar dihapus; auto-reload dimatikan" : "Metode bayar dihapus");
      invalidate();
    },
    onError: (e, vars) => {
      if (!vars.force && isForceableDeleteConflict(e)) {
        confirmDialog({
          title: "Hapus paksa metode bayar?",
          message: `${e instanceof Error ? e.message : ""} Menghapus paksa akan MEMATIKAN auto-reload sampai Anda mengaktifkannya lagi dengan metode bayar lain.`,
          confirmLabel: "Hapus & matikan auto-reload",
          onConfirm: () => remove.mutate({ id: vars.id, force: true }),
        });
        return;
      }
      toast.error(e instanceof Error ? e.message : "Gagal menghapus metode bayar");
    },
  });

  function handleAdded(pm: PaymentMethodCreated) {
    if (pm.action?.url) {
      try {
        sessionStorage.setItem(PENDING_PM_KEY, pm.id);
      } catch {
        /* abaikan */
      }
      window.location.href = pm.action.url;
      return;
    }
    if (pm.status === "active") toast.success(`${pm.label} ditambahkan.`);
    else if (pm.status === "failed") toast.error(`Kartu ditolak${pm.failure_reason ? `: ${pm.failure_reason}` : ""}.`);
    else {
      pollStartRef.current = Date.now();
      setPollingId(pm.id);
    }
    invalidate();
  }

  const columns: Column<PaymentMethod>[] = [
    {
      key: "label",
      header: "Metode",
      cell: (m) => (
        <span className="flex items-center gap-2">
          {m.type === "gopay" ? (
            <Smartphone className="h-4 w-4 shrink-0" aria-hidden="true" />
          ) : (
            <CreditCard className="h-4 w-4 shrink-0" aria-hidden="true" />
          )}
          <span>
            {m.label}
            {m.type === "card" && m.card_exp_month && m.card_exp_year && (
              <span className="ml-1 text-xs" style={{ color: "var(--text-muted)" }}>
                exp {String(m.card_exp_month).padStart(2, "0")}/{m.card_exp_year}
              </span>
            )}
          </span>
          {m.is_default && (
            <Badge tone="accent" title="Dipakai untuk perpanjangan & auto-reload">
              Default
            </Badge>
          )}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (m) => {
        const meta = PM_STATUS_META[m.status];
        return (
          <span className="flex flex-wrap items-center gap-1.5">
            <Badge tone={meta?.tone ?? "neutral"}>{meta?.label ?? m.status}</Badge>
            {m.id === pollingId && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-label="Memeriksa status" />}
            {m.failure_reason && (
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {m.failure_reason}
              </span>
            )}
          </span>
        );
      },
    },
    { key: "added", header: "Ditambahkan", className: "whitespace-nowrap", cell: (m) => formatDate(m.created_at) },
    {
      key: "actions",
      header: <span className="sr-only">Aksi</span>,
      cell: (m) => (
        <span className="flex justify-end gap-1.5">
          {m.status === "active" && !m.is_default && (
            <Button
              size="sm"
              variant="secondary"
              icon={<Star className="h-3.5 w-3.5" aria-hidden="true" />}
              loading={setDefault.isPending && setDefault.variables === m.id}
              onClick={() => setDefault.mutate(m.id)}
            >
              Jadikan default
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Hapus ${m.label}`}
            icon={<Trash2 className="h-3.5 w-3.5" aria-hidden="true" />}
            loading={remove.isPending && remove.variables?.id === m.id}
            onClick={() =>
              confirmDialog({
                title: `Hapus ${m.label}?`,
                message: m.is_default
                  ? "Ini metode bayar default. Perpanjangan dan auto-reload tidak bisa ditagih otomatis sampai ada metode default lain."
                  : "Metode bayar akan dilepas dari akun ini dan tidak bisa dipakai lagi.",
                confirmLabel: "Hapus",
                onConfirm: () => remove.mutate({ id: m.id, force: false }),
              })
            }
          >
            Hapus
          </Button>
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      {pollingId && pollState === "pending" && !timedOut && (
        <CalloutBlock tone="info" icon={Loader2}>
          Menunggu konfirmasi aktivasi dari gateway pembayaran…
        </CalloutBlock>
      )}
      <DataTable
        label="Metode bayar tersimpan"
        rows={methods.data}
        columns={columns}
        rowKey={(m) => m.id}
        query={methods}
        emptyTitle="Belum ada metode bayar."
        emptyDescription="Tambahkan kartu atau GoPay agar perpanjangan langganan dan auto-reload bisa ditagih otomatis."
      />
      {config.data &&
        (config.data.provider ? (
          <AddPaymentMethodForm config={config.data} onAdded={handleAdded} />
        ) : (
          <CalloutBlock tone="warning">
            Gateway pembayaran belum dikonfigurasi di server, jadi metode bayar belum bisa ditambahkan.
          </CalloutBlock>
        ))}
    </div>
  );
}
