import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";

/** Halaman publik onboarding self-service kandidat -- TANPA Layout/sidebar,
 * tanpa login, diakses via link ber-token yang dibagikan HR dari kartu
 * Placement (JobOrderDetail.tsx, "Kirim Link Onboarding"). Data yang
 * disubmit di sini DI-STAGING (backend belum menulis ke Employee) --
 * HR wajib review & terapkan dulu lewat panel review di JobOrderDetail. */

interface Address {
  province?: string;
  city?: string;
  district?: string;
  postal_code?: string;
  detail?: string;
}

interface SubmittedData {
  phone?: string;
  ktp_no?: string;
  npwp_no?: string;
  bank_name?: string;
  bank_account?: string;
  marital_status?: string;
  dependents?: number;
  emergency_contact_name?: string;
  emergency_contact_relation?: string;
  emergency_contact_phone?: string;
  citizen_address?: Address;
  residential_address?: Address;
}

interface DocumentSummary {
  document_type: string;
  file_name: string;
}

interface OnboardingViewData {
  candidate_name: string | null;
  status: "invited" | "submitted" | "applied" | "revoked";
  expires_at: string;
  requested_document_types: string[];
  submitted_data: SubmittedData;
  documents: DocumentSummary[];
}

/** Label tampilan -- daftar dokumen yang SUNGGUH diminta ditentukan HR per
 * undangan (`requested_document_types` dari backend), bukan set tetap. */
const DOC_TYPE_LABEL: Record<string, string> = {
  ktp: "KTP",
  npwp: "NPWP",
  kartu_keluarga: "Kartu Keluarga (KK)",
  ijazah: "Ijazah",
  skck: "SKCK",
  sim: "SIM",
  buku_tabungan: "Buku Tabungan",
  paklaring: "Paklaring",
  surat_keterangan_sehat: "Surat Keterangan Sehat",
  bpjs_kesehatan: "BPJS Kesehatan",
  bpjs_ketenagakerjaan: "BPJS Ketenagakerjaan",
  kartu_bpjs_kesehatan: "Kartu BPJS Kesehatan",
  kartu_bpjs_ketenagakerjaan: "Kartu BPJS Ketenagakerjaan",
  lainnya: "Lainnya",
};

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold text-[var(--text)]">Data Onboarding</h1>
        {children}
      </div>
    </main>
  );
}

function AddressFields({
  value,
  onChange,
  prefix,
}: {
  value: Address;
  onChange: (next: Address) => void;
  prefix: string;
}) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <input
        placeholder="Provinsi"
        value={value.province ?? ""}
        onChange={(e) => onChange({ ...value, province: e.target.value })}
        className="input"
        name={`${prefix}_province`}
      />
      <input
        placeholder="Kota/Kabupaten"
        value={value.city ?? ""}
        onChange={(e) => onChange({ ...value, city: e.target.value })}
        className="input"
        name={`${prefix}_city`}
      />
      <input
        placeholder="Kecamatan"
        value={value.district ?? ""}
        onChange={(e) => onChange({ ...value, district: e.target.value })}
        className="input"
        name={`${prefix}_district`}
      />
      <input
        placeholder="Kode Pos"
        value={value.postal_code ?? ""}
        onChange={(e) => onChange({ ...value, postal_code: e.target.value })}
        className="input"
        name={`${prefix}_postal_code`}
      />
      <textarea
        placeholder="Detail alamat (jalan, RT/RW, dll.)"
        value={value.detail ?? ""}
        onChange={(e) => onChange({ ...value, detail: e.target.value })}
        className="input sm:col-span-2"
        rows={2}
        name={`${prefix}_detail`}
      />
    </div>
  );
}

export default function OnboardingSelfService() {
  const { token } = useParams<{ token: string }>();
  const qc = useQueryClient();

  const [phone, setPhone] = useState("");
  const [ktpNo, setKtpNo] = useState("");
  const [npwpNo, setNpwpNo] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankAccount, setBankAccount] = useState("");
  const [maritalStatus, setMaritalStatus] = useState("tk");
  const [dependents, setDependents] = useState(0);
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyRelation, setEmergencyRelation] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [citizenAddress, setCitizenAddress] = useState<Address>({});
  const [residentialAddress, setResidentialAddress] = useState<Address>({});
  const [sameAsCitizen, setSameAsCitizen] = useState(false);
  const [consent, setConsent] = useState(false);
  const [prefilled, setPrefilled] = useState(false);

  const view = useQuery({
    queryKey: ["onboarding-view", token],
    queryFn: () => api.get<OnboardingViewData>(`/onboarding/${token}`),
    retry: false,
  });

  useEffect(() => {
    if (!view.data || prefilled) return;
    const d = view.data.submitted_data;
    setPhone(d.phone ?? "");
    setKtpNo(d.ktp_no ?? "");
    setNpwpNo(d.npwp_no ?? "");
    setBankName(d.bank_name ?? "");
    setBankAccount(d.bank_account ?? "");
    setMaritalStatus(d.marital_status ?? "tk");
    setDependents(d.dependents ?? 0);
    setEmergencyName(d.emergency_contact_name ?? "");
    setEmergencyRelation(d.emergency_contact_relation ?? "");
    setEmergencyPhone(d.emergency_contact_phone ?? "");
    setCitizenAddress(d.citizen_address ?? {});
    setResidentialAddress(d.residential_address ?? {});
    setPrefilled(true);
  }, [view.data, prefilled]);

  const submit = useMutation({
    mutationFn: () =>
      api.post(`/onboarding/${token}`, {
        phone,
        ktp_no: ktpNo,
        npwp_no: npwpNo,
        bank_name: bankName,
        bank_account: bankAccount,
        marital_status: maritalStatus,
        dependents,
        emergency_contact_name: emergencyName,
        emergency_contact_relation: emergencyRelation,
        emergency_contact_phone: emergencyPhone,
        citizen_address: citizenAddress,
        residential_address: sameAsCitizen ? citizenAddress : residentialAddress,
        consent,
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["onboarding-view", token] }),
  });

  const uploadDoc = useMutation({
    mutationFn: ({ documentType, file }: { documentType: string; file: File }) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("document_type", documentType);
      return api.upload(`/onboarding/${token}/documents`, fd);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["onboarding-view", token] }),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    submit.mutate();
  }

  if (view.isLoading) {
    return (
      <Shell>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Memuat...
        </p>
      </Shell>
    );
  }

  if (view.error) {
    const status = view.error instanceof ApiError ? view.error.status : 0;
    const msg =
      status === 410
        ? "Link onboarding ini sudah kedaluwarsa. Hubungi HR untuk link baru."
        : status === 409
          ? "Data onboarding ini sudah diterapkan atau link sudah dibatalkan HR."
          : status === 404
            ? "Link onboarding tidak valid."
            : (view.error as Error).message;
    return (
      <Shell>
        <div className="card">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {msg}
          </p>
        </div>
      </Shell>
    );
  }

  const data = view.data!;
  const uploadedTypes = new Set(data.documents.map((d) => d.document_type));

  return (
    <Shell>
      <div className="card space-y-1">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {data.candidate_name ? `Halo, ${data.candidate_name}.` : "Halo."} Lengkapi data di bawah
          untuk proses onboarding sebagai karyawan baru.
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Link berlaku s.d. {new Date(data.expires_at).toLocaleString("id-ID")}
        </p>
      </div>

      {submit.isSuccess ? (
        <div className="card border-emerald-600">
          <p className="pill p-green">Data tersimpan</p>
          <p className="mt-2 text-sm" style={{ color: "var(--text)" }}>
            Data Anda sudah kami terima dan akan direview oleh HR. Anda masih bisa mengunggah
            dokumen di bawah, atau membuka link ini lagi kalau perlu memperbaiki data.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="card space-y-4">
          <h3 className="font-semibold" style={{ color: "var(--text)" }}>
            Data Pribadi
          </h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input
              placeholder="No. Telepon"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="input"
            />
            <input
              placeholder="No. KTP"
              value={ktpNo}
              onChange={(e) => setKtpNo(e.target.value)}
              className="input"
            />
            <input
              placeholder="No. NPWP (kalau ada)"
              value={npwpNo}
              onChange={(e) => setNpwpNo(e.target.value)}
              className="input"
            />
            <select
              value={maritalStatus}
              onChange={(e) => setMaritalStatus(e.target.value)}
              className="input"
              aria-label="Status pernikahan"
            >
              <option value="tk">Belum Menikah (TK)</option>
              <option value="k">Menikah (K)</option>
            </select>
            <div className="flex flex-col gap-1">
              <label htmlFor="dependents" className="text-xs" style={{ color: "var(--text-muted)" }}>
                Jumlah Tanggungan
              </label>
              <input
                id="dependents"
                type="number"
                min={0}
                value={dependents}
                onChange={(e) => setDependents(Number(e.target.value) || 0)}
                className="input"
              />
            </div>
          </div>

          <h3 className="font-semibold" style={{ color: "var(--text)" }}>
            Rekening Bank
          </h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input
              placeholder="Nama Bank"
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
              className="input"
            />
            <input
              placeholder="No. Rekening"
              value={bankAccount}
              onChange={(e) => setBankAccount(e.target.value)}
              className="input"
            />
          </div>

          <h3 className="font-semibold" style={{ color: "var(--text)" }}>
            Alamat KTP
          </h3>
          <AddressFields value={citizenAddress} onChange={setCitizenAddress} prefix="citizen" />

          <div className="flex items-center justify-between">
            <h3 className="font-semibold" style={{ color: "var(--text)" }}>
              Alamat Domisili
            </h3>
            <label className="inline-flex items-center gap-1.5 text-xs">
              <input
                type="checkbox"
                checked={sameAsCitizen}
                onChange={(e) => setSameAsCitizen(e.target.checked)}
              />
              Sama dengan alamat KTP
            </label>
          </div>
          {!sameAsCitizen && (
            <AddressFields
              value={residentialAddress}
              onChange={setResidentialAddress}
              prefix="residential"
            />
          )}

          <h3 className="font-semibold" style={{ color: "var(--text)" }}>
            Kontak Darurat
          </h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <input
              placeholder="Nama"
              value={emergencyName}
              onChange={(e) => setEmergencyName(e.target.value)}
              className="input"
            />
            <input
              placeholder="Hubungan (mis. Ibu, Suami)"
              value={emergencyRelation}
              onChange={(e) => setEmergencyRelation(e.target.value)}
              className="input"
            />
            <input
              placeholder="No. Telepon"
              value={emergencyPhone}
              onChange={(e) => setEmergencyPhone(e.target.value)}
              className="input"
            />
          </div>

          <label className="flex items-start gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5"
            />
            Saya menyetujui data pribadi di atas diproses oleh perusahaan untuk keperluan
            administrasi kepegawaian, sesuai UU Perlindungan Data Pribadi (UU PDP).
          </label>

          {submit.error && (
            <p className="text-sm text-red-600">{(submit.error as Error).message}</p>
          )}
          <button type="submit" className="btn w-full" disabled={!consent || submit.isPending}>
            {submit.isPending ? "Menyimpan..." : "Simpan Data"}
          </button>
        </form>
      )}

      <div className="card space-y-3">
        <h3 className="font-semibold" style={{ color: "var(--text)" }}>
          Unggah Dokumen
        </h3>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Format PDF, PNG, atau JPEG, maksimal 10 MB. Unggah ulang akan mengganti file sebelumnya.
        </p>
        {data.requested_document_types.map((key) => (
          <div key={key} className="flex flex-wrap items-center gap-2">
            <span className="w-40 text-sm font-medium" style={{ color: "var(--text)" }}>
              {DOC_TYPE_LABEL[key] ?? key}
            </span>
            {uploadedTypes.has(key) && (
              <span className="pill p-green text-xs">
                {data.documents.find((d) => d.document_type === key)?.file_name}
              </span>
            )}
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              className="input w-auto py-1 text-xs"
              aria-label={`Unggah ${DOC_TYPE_LABEL[key] ?? key}`}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadDoc.mutate({ documentType: key, file });
                e.target.value = "";
              }}
            />
          </div>
        ))}
        {uploadDoc.error && (
          <p className="text-sm text-red-600">{(uploadDoc.error as Error).message}</p>
        )}
      </div>
    </Shell>
  );
}
