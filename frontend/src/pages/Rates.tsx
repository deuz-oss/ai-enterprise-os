import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { CalloutBlock, PageHeader } from "../components/notion";

interface Pph21Row {
  id: string;
  effective_from: string;
  ptkp_diri: number;
  ptkp_kawin: number;
  ptkp_tanggungan: number;
}
interface BpjsRow {
  id: string;
  effective_from: string;
  kesehatan_employer: number;
  kesehatan_employee: number;
  kesehatan_cap: number;
  jht_employer: number;
  jht_employee: number;
  jp_employer: number;
  jp_employee: number;
  jp_cap: number;
  jkm_rate: number;
}
interface BillingRow {
  id: string;
  effective_from: string;
  ppn_rate: number;
  pph23_rate: number;
  due_days: number;
}
interface BankFeeRow {
  id: string;
  bank_name: string;
  fee: number;
}

const fmt = (v: number) => new Intl.NumberFormat("id-ID").format(v);

export default function Rates() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"pph21" | "bpjs" | "billing" | "bank">("pph21");

  const pph21 = useQuery({ queryKey: ["rates-pph21"], queryFn: () => api.get<Pph21Row[]>("/rates/pph21") });
  const bpjs = useQuery({ queryKey: ["rates-bpjs"], queryFn: () => api.get<BpjsRow[]>("/rates/bpjs") });
  const billing = useQuery({ queryKey: ["rates-billing"], queryFn: () => api.get<BillingRow[]>("/rates/billing") });
  const bankFees = useQuery({ queryKey: ["rates-bank"], queryFn: () => api.get<BankFeeRow[]>("/rates/bank-fees") });

  const createPph21 = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/rates/pph21", body),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["rates-pph21"] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal menyimpan"),
  });
  const createBpjs = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/rates/bpjs", body),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["rates-bpjs"] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal menyimpan"),
  });
  const createBilling = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/rates/billing", body),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["rates-billing"] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal menyimpan"),
  });
  const saveBankFee = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/rates/bank-fees", body),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["rates-bank"] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Gagal menyimpan"),
  });

  function handlePph21(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      createPph21.mutate({
        effective_from: f.get("effective_from"),
        ptkp_diri: Number(f.get("ptkp_diri")),
        ptkp_kawin: Number(f.get("ptkp_kawin")),
        ptkp_tanggungan: Number(f.get("ptkp_tanggungan")),
        max_tanggungan: 3,
        pasal17_brackets: JSON.parse(String(f.get("pasal17_brackets"))),
        ter_a: JSON.parse(String(f.get("ter_a"))),
        ter_b: JSON.parse(String(f.get("ter_b"))),
        ter_c: JSON.parse(String(f.get("ter_c"))),
      });
    } catch (err) {
      setError(`JSON bracket tidak valid: ${err instanceof Error ? err.message : err}`);
    }
  }

  function handleBpjs(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      createBpjs.mutate({
        effective_from: f.get("effective_from"),
        kesehatan_employer: Number(f.get("kesehatan_employer")),
        kesehatan_employee: Number(f.get("kesehatan_employee")),
        kesehatan_cap: Number(f.get("kesehatan_cap")),
        jht_employer: Number(f.get("jht_employer")),
        jht_employee: Number(f.get("jht_employee")),
        jp_employer: Number(f.get("jp_employer")),
        jp_employee: Number(f.get("jp_employee")),
        jp_cap: Number(f.get("jp_cap")),
        jkm_rate: Number(f.get("jkm_rate")),
        jkk_rates: JSON.parse(String(f.get("jkk_rates"))),
        default_jkk_category: Number(f.get("default_jkk_category") || 2),
      });
    } catch (err) {
      setError(`JSON JKK tidak valid: ${err instanceof Error ? err.message : err}`);
    }
  }

  function handleBilling(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    createBilling.mutate({
      effective_from: f.get("effective_from"),
      ppn_rate: Number(f.get("ppn_rate")),
      pph23_rate: Number(f.get("pph23_rate")),
      due_days: Number(f.get("due_days")),
    });
  }

  const th = "th";
  const td = "td";

  return (
    <div className="space-y-4">
      <PageHeader emoji="🧮" title="Tarif & Rate" subtitle="Rate ber-versi per tanggal efektif — terpisah dari kode; laporan historis memakai snapshot" />

      <div className="flex gap-2">
        {(
          [
            ["pph21", "PPh 21"],
            ["bpjs", "BPJS"],
            ["billing", "Billing"],
            ["bank", "Bank Fee"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className="rounded px-3 py-1.5 text-sm transition-colors"
            style={{
              border: "1px solid var(--n-border)",
              backgroundColor: tab === k ? "var(--n-hover)" : "transparent",
              color: tab === k ? "var(--n-text)" : "var(--n-text-muted)",
              fontWeight: tab === k ? 500 : 400,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <CalloutBlock emoji="⚠️" tone="danger">{error}</CalloutBlock>}

      {tab === "pph21" && (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead style={{ backgroundColor: "var(--n-hover)" }}>
                <tr>
                  <th className={th}>Efektif Sejak</th>
                  <th className={th}>PTKP Diri</th>
                  <th className={th}>PTKP Kawin</th>
                  <th className={th}>PTKP Tanggungan</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
                {(pph21.data ?? []).map((r) => (
                  <tr key={r.id}>
                    <td className={`${td} font-medium`}>{r.effective_from}</td>
                    <td className={td}>Rp {fmt(Number(r.ptkp_diri))}</td>
                    <td className={td}>Rp {fmt(Number(r.ptkp_kawin))}</td>
                    <td className={td}>Rp {fmt(Number(r.ptkp_tanggungan))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <form onSubmit={handlePph21} className="card space-y-2">
            <h2 className="font-semibold text-notion">Versi Baru PPh 21</h2>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
              <input name="effective_from" type="date" required className="input" />
              <input name="ptkp_diri" type="number" required placeholder="PTKP diri (Rp)" className="input" />
              <input name="ptkp_kawin" type="number" placeholder="PTKP kawin (Rp)" className="input" />
              <input name="ptkp_tanggungan" type="number" placeholder="PTKP per tanggungan" className="input" />
            </div>
            {(
              [
                ["pasal17_brackets", "Pasal 17 (JSON, null = tak terbatas)"],
                ["ter_a", "TER A (JSON)"],
                ["ter_b", "TER B (JSON)"],
                ["ter_c", "TER C (JSON)"],
              ] as const
            ).map(([name, ph]) => (
              <textarea
                key={name}
                name={name}
                rows={2}
                placeholder={ph}
                className="input font-mono text-xs"
                defaultValue={name === "pasal17_brackets" ? "[[60000000, 0.05], [250000000, 0.15], [500000000, 0.25], [5000000000, 0.30], [null, 0.35]]" : ""}
              />
            ))}
            <button className="btn" disabled={createPph21.isPending}>
              Simpan Versi PPh 21
            </button>
          </form>
        </>
      )}

      {tab === "bpjs" && (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead style={{ backgroundColor: "var(--n-hover)" }}>
                <tr>
                  <th className={th}>Efektif</th>
                  <th className={th}>Kes. Psk/Pyd</th>
                  <th className={th}>Cap Kes.</th>
                  <th className={th}>JHT Psk/Pyd</th>
                  <th className={th}>JP Psk/Pyd</th>
                  <th className={th}>Cap JP</th>
                  <th className={th}>JKM</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
                {(bpjs.data ?? []).map((r) => (
                  <tr key={r.id}>
                    <td className={`${td} font-medium`}>{r.effective_from}</td>
                    <td className={`${td} font-mono text-xs`}>
                      {r.kesehatan_employer}/{r.kesehatan_employee}
                    </td>
                    <td className={td}>{fmt(Number(r.kesehatan_cap))}</td>
                    <td className={`${td} font-mono text-xs`}>
                      {r.jht_employer}/{r.jht_employee}
                    </td>
                    <td className={`${td} font-mono text-xs`}>
                      {r.jp_employer}/{r.jp_employee}
                    </td>
                    <td className={td}>{fmt(Number(r.jp_cap))}</td>
                    <td className={`${td} font-mono text-xs`}>{r.jkm_rate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <form onSubmit={handleBpjs} className="card space-y-2">
            <h2 className="font-semibold text-notion">Versi Baru BPJS</h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <input name="effective_from" type="date" required className="input" />
              <input name="kesehatan_employer" type="number" step="0.0001" placeholder="Kes psk (0.04)" className="input" />
              <input name="kesehatan_employee" type="number" step="0.0001" placeholder="Kes pyd (0.01)" className="input" />
              <input name="kesehatan_cap" type="number" placeholder="Cap kes" className="input" />
              <input name="jht_employer" type="number" step="0.0001" placeholder="JHT psk" className="input" />
              <input name="jht_employee" type="number" step="0.0001" placeholder="JHT pyd" className="input" />
              <input name="jp_employer" type="number" step="0.0001" placeholder="JP psk" className="input" />
              <input name="jp_employee" type="number" step="0.0001" placeholder="JP pyd" className="input" />
              <input name="jp_cap" type="number" placeholder="Cap JP" className="input" />
              <input name="jkm_rate" type="number" step="0.0001" placeholder="JKM" className="input" />
            </div>
            <div className="flex gap-2">
              <textarea name="jkk_rates" rows={1} placeholder='JKK JSON: {"1":0.0024,...}' className="input flex-1 font-mono text-xs" />
              <input name="default_jkk_category" type="number" min={1} max={5} defaultValue={2} className="input w-24" title="Default kategori JKK" />
            </div>
            <button className="btn" disabled={createBpjs.isPending}>
              Simpan Versi BPJS
            </button>
          </form>
        </>
      )}

      {tab === "billing" && (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead style={{ backgroundColor: "var(--n-hover)" }}>
                <tr>
                  <th className={th}>Efektif Sejak</th>
                  <th className={th}>PPN</th>
                  <th className={th}>PPh 23</th>
                  <th className={th}>Jatuh Tempo (hari)</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
                {(billing.data ?? []).map((r) => (
                  <tr key={r.id}>
                    <td className={`${td} font-medium`}>{r.effective_from}</td>
                    <td className={`${td} font-mono text-xs`}>{(Number(r.ppn_rate) * 100).toFixed(0)}%</td>
                    <td className={`${td} font-mono text-xs`}>{(Number(r.pph23_rate) * 100).toFixed(0)}%</td>
                    <td className={td}>{r.due_days}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <form onSubmit={handleBilling} className="card grid grid-cols-1 gap-2 sm:grid-cols-4">
            <input name="effective_from" type="date" required className="input" />
            <input name="ppn_rate" type="number" step="0.0001" required placeholder="PPN (0.12)" className="input" />
            <input name="pph23_rate" type="number" step="0.0001" placeholder="PPh23 (0.02)" className="input" />
            <input name="due_days" type="number" required placeholder="Due days" className="input" />
            <button className="btn sm:col-span-4" disabled={createBilling.isPending}>
              Simpan Versi Billing
            </button>
          </form>
        </>
      )}

      {tab === "bank" && (
        <>
          <CalloutBlock emoji="🏦" tone="info">
            Potongan admin otomatis di slip gaji. Bank Mandiri group = gratis.
          </CalloutBlock>
          <div className="card space-y-3">
            <h2 className="font-semibold text-notion">Daftar Biaya Admin Bank</h2>
            {(bankFees.data ?? []).map((f) => (
              <form
                key={f.id}
                className="flex items-center gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = new FormData(e.currentTarget);
                  saveBankFee.mutate({
                    bank_name: f.bank_name,
                    fee: Number(form.get("fee")),
                    is_mandiri_group: f.bank_name.toLowerCase().includes("mandiri"),
                  });
                }}
              >
                <span className="w-48 truncate text-sm">{f.bank_name}</span>
                <input name="fee" type="number" defaultValue={Number(f.fee)} className="input w-32" />
                <button className="btn-secondary text-xs">Simpan</button>
              </form>
            ))}
            <form
              className="flex items-center gap-2 border-t pt-3"
              style={{ borderColor: "var(--n-border)" }}
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                saveBankFee.mutate({
                  bank_name: String(form.get("bank_name") || ""),
                  fee: Number(form.get("fee") || 3500),
                  is_mandiri_group: false,
                });
                e.currentTarget.reset();
              }}
            >
              <input name="bank_name" required placeholder="Nama bank baru" className="input w-48" />
              <input name="fee" type="number" defaultValue={3500} className="input w-32" />
              <button className="btn text-xs">+ Tambah Bank</button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
