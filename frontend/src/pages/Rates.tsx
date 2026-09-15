import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Calculator } from "lucide-react";
import { CalloutBlock, PageHeader } from "../components/workspace";
import { PillTabs, type PillTab } from "../components/ui";

interface Pph21Row {
  id: string;
  effective_from: string;
  ptkp_diri: number;
  ptkp_kawin: number;
  ptkp_tanggungan: number;
  pasal17_brackets: [number | null, number][];
  ter_a: [number | null, number][];
  ter_b: [number | null, number][];
  ter_c: [number | null, number][];
}

/** Satu baris tabel bracket pajak: batas atas (Rp, string krn dikontrol
 * input) + tarif (persen, string). Baris terakhir boleh batas atas kosong
 * (artinya "tak terbatas" / null di JSON backend). */
interface BracketRow {
  upper: string;
  rate: string;
}

const DEFAULT_PASAL17_ROWS: BracketRow[] = [
  { upper: "60000000", rate: "5" },
  { upper: "250000000", rate: "15" },
  { upper: "500000000", rate: "25" },
  { upper: "5000000000", rate: "30" },
  { upper: "", rate: "35" },
];
const BLANK_BRACKET_ROWS: BracketRow[] = [{ upper: "", rate: "" }];

function bracketsToRows(raw: [number | null, number][] | undefined): BracketRow[] {
  if (!raw || raw.length === 0) return BLANK_BRACKET_ROWS;
  return raw.map(([upper, rate]) => ({
    upper: upper === null ? "" : String(upper),
    rate: String(Math.round(Number(rate) * 10000) / 100),
  }));
}

/** Validasi + konversi baris editor -> JSON `[[upper|null, rate], ...]` yang
 * dipahami backend (`_deser_brackets`). Hanya baris terakhir boleh batas
 * atas kosong; batas atas harus naik (ascending); tarif 0-100%. Menggantikan
 * `JSON.parse` bebas yang sebelumnya bisa menerima bentuk apa pun tanpa
 * validasi (DES-010, audit desain 2026-09-15) -- salah ketik di sini dulu
 * berarti salah potong PPh 21 semua karyawan tanpa ketahuan sampai payroll
 * jalan. */
function validateBracketRows(
  rows: BracketRow[],
  label: string
): { brackets: (number | null)[][] } | { error: string } {
  const parsed: { upper: number | null; rate: number }[] = [];
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const isLast = i === rows.length - 1;
    const rateNum = Number(row.rate);
    if (row.rate.trim() === "" || Number.isNaN(rateNum) || rateNum < 0 || rateNum > 100) {
      return { error: `${label}, baris ${i + 1}: tarif harus angka 0-100%` };
    }
    let upperNum: number | null;
    if (row.upper.trim() === "") {
      if (!isLast) {
        return { error: `${label}, baris ${i + 1}: cuma baris terakhir boleh "tak terbatas"` };
      }
      upperNum = null;
    } else {
      upperNum = Number(row.upper);
      if (Number.isNaN(upperNum) || upperNum <= 0) {
        return { error: `${label}, baris ${i + 1}: batas atas harus angka positif` };
      }
      const prevUpper = i > 0 ? parsed[i - 1].upper : null;
      if (prevUpper !== null && upperNum <= prevUpper) {
        return { error: `${label}, baris ${i + 1}: batas atas harus lebih besar dari baris sebelumnya` };
      }
    }
    parsed.push({ upper: upperNum, rate: rateNum });
  }
  if (parsed.length === 0) return { error: `${label}: minimal 1 baris` };
  return { brackets: parsed.map((p) => [p.upper, Math.round((p.rate / 100) * 1_000_000) / 1_000_000]) };
}

function BracketRowsEditor({
  label,
  rows,
  onChange,
}: {
  label: string;
  rows: BracketRow[];
  onChange: (rows: BracketRow[]) => void;
}) {
  function updateRow(i: number, patch: Partial<BracketRow>) {
    onChange(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
        {label}
      </p>
      <div className="space-y-1">
        {rows.map((row, i) => {
          const isLast = i === rows.length - 1;
          const unbounded = isLast && row.upper === "";
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="w-4 shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>
                {i + 1}
              </span>
              <input
                type="number"
                min={1}
                placeholder="Batas atas (Rp)"
                aria-label={`${label} baris ${i + 1} batas atas (Rp)`}
                className="input flex-1 text-xs"
                value={row.upper}
                disabled={unbounded}
                onChange={(e) => updateRow(i, { upper: e.target.value })}
              />
              <input
                type="number"
                min={0}
                max={100}
                step="0.01"
                placeholder="Tarif"
                aria-label={`${label} baris ${i + 1} tarif (%)`}
                className="input w-20 text-xs"
                value={row.rate}
                onChange={(e) => updateRow(i, { rate: e.target.value })}
              />
              <span className="w-3 shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>
                %
              </span>
              {isLast && (
                <label
                  className="flex shrink-0 items-center gap-1 whitespace-nowrap text-xs"
                  style={{ color: "var(--text-muted)" }}
                >
                  <input
                    type="checkbox"
                    checked={unbounded}
                    onChange={(e) => updateRow(i, { upper: e.target.checked ? "" : row.upper })}
                  />
                  tak terbatas
                </label>
              )}
              {rows.length > 1 && (
                <button
                  type="button"
                  title={`Hapus baris ${i + 1}`}
                  className="btn-ghost shrink-0 px-1.5 text-xs text-rose-600 dark:text-rose-400"
                  onClick={() => onChange(rows.filter((_, idx) => idx !== i))}
                >
                  ×
                </button>
              )}
            </div>
          );
        })}
      </div>
      <button
        type="button"
        className="btn-secondary text-xs"
        onClick={() => onChange([...rows, { upper: "", rate: "" }])}
      >
        + Tambah Baris
      </button>
    </div>
  );
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

  // Baris bracket PPh 21 (Pasal 17 + TER A/B/C) dikontrol lewat state, bukan
  // FormData mentah -- diganti dari textarea JSON (DES-010). Diisi otomatis
  // dari versi PALING BARU (pph21.data[0], list sudah terurut DESC di
  // backend) begitu data datang, supaya admin EDIT tabel yang sudah ada
  // (26-27 baris utk TER) alih-alih ngetik dari nol. `seeded` mencegah
  // effect menimpa perubahan yang sedang diketik admin kalau query refetch.
  const [pasal17Rows, setPasal17Rows] = useState<BracketRow[]>(DEFAULT_PASAL17_ROWS);
  const [terARows, setTerARows] = useState<BracketRow[]>(BLANK_BRACKET_ROWS);
  const [terBRows, setTerBRows] = useState<BracketRow[]>(BLANK_BRACKET_ROWS);
  const [terCRows, setTerCRows] = useState<BracketRow[]>(BLANK_BRACKET_ROWS);
  const [bracketsSeeded, setBracketsSeeded] = useState(false);
  useEffect(() => {
    const latest = pph21.data?.[0];
    if (!latest || bracketsSeeded) return;
    setPasal17Rows(bracketsToRows(latest.pasal17_brackets));
    setTerARows(bracketsToRows(latest.ter_a));
    setTerBRows(bracketsToRows(latest.ter_b));
    setTerCRows(bracketsToRows(latest.ter_c));
    setBracketsSeeded(true);
  }, [pph21.data, bracketsSeeded]);

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
    const pasal17 = validateBracketRows(pasal17Rows, "Pasal 17");
    if ("error" in pasal17) return setError(pasal17.error);
    const terA = validateBracketRows(terARows, "TER A");
    if ("error" in terA) return setError(terA.error);
    const terB = validateBracketRows(terBRows, "TER B");
    if ("error" in terB) return setError(terB.error);
    const terC = validateBracketRows(terCRows, "TER C");
    if ("error" in terC) return setError(terC.error);
    createPph21.mutate({
      effective_from: f.get("effective_from"),
      ptkp_diri: Number(f.get("ptkp_diri")),
      ptkp_kawin: Number(f.get("ptkp_kawin")),
      ptkp_tanggungan: Number(f.get("ptkp_tanggungan")),
      max_tanggungan: 3,
      pasal17_brackets: pasal17.brackets,
      ter_a: terA.brackets,
      ter_b: terB.brackets,
      ter_c: terC.brackets,
    });
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
      <PageHeader icon={Calculator} title="Tarif & Rate" subtitle="Rate ber-versi per tanggal efektif — terpisah dari kode; laporan historis memakai snapshot" />

      {/* Bukan filter status/kategori atas satu tabel (§1.5) -- ini pemilih
          4 dataset rate yang berbeda sama sekali, jadi count per-tab tidak
          bermakna dan sengaja tidak ditampilkan. Cuma dipakai gaya pill
          yang sama untuk konsistensi visual antar halaman archetype B. */}
      <PillTabs
        tabs={
          [
            { key: "pph21", label: "PPh 21" },
            { key: "bpjs", label: "BPJS" },
            { key: "billing", label: "Billing" },
            { key: "bank", label: "Bank Fee" },
          ] satisfies PillTab[]
        }
        value={tab}
        onChange={(k) => setTab(k as typeof tab)}
      />

      {error && <CalloutBlock tone="danger">{error}</CalloutBlock>}

      {tab === "pph21" && (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead style={{ backgroundColor: "var(--hover)" }}>
                <tr>
                  <th className={th}>Efektif Sejak</th>
                  <th className={th}>PTKP Diri</th>
                  <th className={th}>PTKP Kawin</th>
                  <th className={th}>PTKP Tanggungan</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
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
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Versi Baru PPh 21</h2>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
              <input name="effective_from" type="date" required className="input" aria-label="Berlaku sejak (PPh 21)" />
              <input name="ptkp_diri" type="number" required placeholder="PTKP diri (Rp)" className="input" />
              <input name="ptkp_kawin" type="number" placeholder="PTKP kawin (Rp)" className="input" />
              <input name="ptkp_tanggungan" type="number" placeholder="PTKP per tanggungan" className="input" />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <BracketRowsEditor label="Pasal 17" rows={pasal17Rows} onChange={setPasal17Rows} />
              <BracketRowsEditor label="TER A" rows={terARows} onChange={setTerARows} />
              <BracketRowsEditor label="TER B" rows={terBRows} onChange={setTerBRows} />
              <BracketRowsEditor label="TER C" rows={terCRows} onChange={setTerCRows} />
            </div>
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
              <thead style={{ backgroundColor: "var(--hover)" }}>
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
              <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
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
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Versi Baru BPJS</h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <input name="effective_from" type="date" required className="input" aria-label="Berlaku sejak (BPJS)" />
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
              <thead style={{ backgroundColor: "var(--hover)" }}>
                <tr>
                  <th className={th}>Efektif Sejak</th>
                  <th className={th}>PPN</th>
                  <th className={th}>PPh 23</th>
                  <th className={th}>Jatuh Tempo (hari)</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
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
            <input name="effective_from" type="date" required className="input" aria-label="Berlaku sejak (Billing)" />
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
          <CalloutBlock tone="info">
            Potongan admin otomatis di slip gaji. Bank Mandiri group = gratis.
          </CalloutBlock>
          <div className="card space-y-3">
            <h2 className="font-semibold" style={{ color: "var(--text)" }}>Daftar Biaya Admin Bank</h2>
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
              style={{ borderColor: "var(--border)" }}
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
