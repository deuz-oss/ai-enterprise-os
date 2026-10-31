import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, formatDateTime } from "../../api/client";
import { validateEmail, validateNpwp, type BillingProfile } from "../../lib/billing";
import { Button, QueryState } from "../ui";

function ProfileFields({ profile }: { profile: BillingProfile }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    legal_name: profile.legal_name ?? "",
    npwp: profile.npwp ?? "",
    address: profile.address ?? "",
    billing_email: profile.billing_email ?? "",
  });
  const [touched, setTouched] = useState(false);
  const npwpError = validateNpwp(form.npwp);
  const emailError = validateEmail(form.billing_email);
  const nameError = form.legal_name.trim() ? null : "Nama legal wajib diisi.";
  const invalid = Boolean(npwpError || emailError || nameError);

  const save = useMutation({
    mutationFn: () =>
      api.put<BillingProfile>("/billing/profile", {
        legal_name: form.legal_name.trim(),
        npwp: form.npwp.trim() || null,
        address: form.address.trim() || null,
        billing_email: form.billing_email.trim() || null,
      }),
    onSuccess: (res) => {
      qc.setQueryData(["billing-profile"], res);
      toast.success("Profil penagihan tersimpan");
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Gagal menyimpan profil"),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!invalid) save.mutate();
  }

  const fieldError = (msg: string | null, id: string) =>
    touched && msg ? (
      <span id={id} className="mt-1 block text-xs text-red-600 dark:text-red-400">
        {msg}
      </span>
    ) : null;

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      <label className="block text-xs" style={{ color: "var(--text-muted)" }}>
        Nama legal (tertera di kwitansi) *
        <input
          className="input mt-1 w-full"
          value={form.legal_name}
          maxLength={255}
          aria-invalid={touched && nameError ? true : undefined}
          aria-describedby={touched && nameError ? "bp-name-err" : undefined}
          onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
        />
        {fieldError(nameError, "bp-name-err")}
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs" style={{ color: "var(--text-muted)" }}>
          NPWP
          <input
            className="input mt-1 w-full font-mono"
            inputMode="numeric"
            placeholder="15 atau 16 digit"
            maxLength={22}
            value={form.npwp}
            aria-invalid={touched && npwpError ? true : undefined}
            aria-describedby={touched && npwpError ? "bp-npwp-err" : undefined}
            onChange={(e) => setForm({ ...form, npwp: e.target.value })}
          />
          {fieldError(npwpError, "bp-npwp-err")}
        </label>
        <label className="block text-xs" style={{ color: "var(--text-muted)" }}>
          Email penagihan
          <input
            className="input mt-1 w-full"
            type="email"
            maxLength={255}
            value={form.billing_email}
            aria-invalid={touched && emailError ? true : undefined}
            aria-describedby={touched && emailError ? "bp-email-err" : undefined}
            onChange={(e) => setForm({ ...form, billing_email: e.target.value })}
          />
          {fieldError(emailError, "bp-email-err")}
        </label>
      </div>
      <label className="block text-xs" style={{ color: "var(--text-muted)" }}>
        Alamat
        <textarea
          className="input mt-1 min-h-[72px] w-full"
          maxLength={1000}
          value={form.address}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="secondary" loading={save.isPending}>
          Simpan profil
        </Button>
        {profile.updated_at && (
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Terakhir diperbarui {formatDateTime(profile.updated_at)}
          </span>
        )}
      </div>
    </form>
  );
}

export function BillingProfileForm() {
  const profile = useQuery({
    queryKey: ["billing-profile"],
    queryFn: () => api.get<BillingProfile>("/billing/profile"),
  });
  return (
    <div className="card space-y-3">
      <div>
        <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>
          Profil penagihan
        </h3>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Identitas pembeli yang dicetak pada kwitansi.
        </p>
      </div>
      <QueryState query={profile}>
        {/* key: reset isian bila data server berubah (mis. disimpan dari tab lain). */}
        {profile.data && <ProfileFields key={profile.data.updated_at ?? "baru"} profile={profile.data} />}
      </QueryState>
    </div>
  );
}
