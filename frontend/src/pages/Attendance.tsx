import { FormEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadFile } from "../api/client";
import { CalloutBlock, PageHeader, PropertiesPanel, PropertyRow } from "../components/notion";

interface EmployeeRow {
  id: string;
  employee_no: string;
  full_name: string;
  employment_type: string;
}

interface DailyRecord {
  id: string;
  employee_id: string;
  date: string;
  status: string;
  clock_in: string | null;
  clock_out: string | null;
  overtime_hours: number;
  source: string;
  notes: string | null;
}

interface SummaryRow {
  id: string;
  employee_id: string;
  year: number;
  month: number;
  present_days: number;
  overtime_hours: number;
  client_approved: boolean;
}

interface ImportResult {
  inserted: number;
  updated: number;
  failed: { row: number; employee_no: string; error: string }[];
}

const STATUS_LABELS: Record<string, string> = {
  hadir: "Hadir",
  terlambat: "Terlambat",
  izin: "Izin",
  sakit: "Sakit",
  cuti: "Cuti",
  alpa: "Alpa",
  libur: "Libur",
  dinas_luar: "Dinas Luar",
};

// C2: warna titik kalender per status (hex Notion).
const STATUS_DOT: Record<string, string> = {
  hadir: "#0f7b6c",
  terlambat: "#cb912f",
  izin: "#2383e2",
  sakit: "#9065b0",
  cuti: "#d9730d",
  alpa: "#e03e3e",
  libur: "#9f9f9f",
  dinas_luar: "#5b5bd6",
};

export default function Attendance() {
  const qc = useQueryClient();
  const [period, setPeriod] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  });
  const [view, setView] = useState<"tabel" | "kalender">("tabel");
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => api.get<EmployeeRow[]>("/employees"),
  });

  const { data: records } = useQuery({
    queryKey: ["attendance-records", period],
    queryFn: () =>
      api.get<DailyRecord[]>(`/attendance/records?year=${period.year}&month=${period.month}`),
  });

  const { data: summaries } = useQuery({
    queryKey: ["attendance-summaries", period],
    queryFn: () =>
      api.get<SummaryRow[]>(`/payroll/attendance?year=${period.year}&month=${period.month}`),
  });

  const upsertRecord = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/attendance/records", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance-records"] });
      qc.invalidateQueries({ queryKey: ["attendance-summaries"] });
    },
  });

  const importCsv = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<ImportResult>("/attendance/import", form);
    },
    onSuccess: (data) => {
      setImportResult(data);
      qc.invalidateQueries({ queryKey: ["attendance-records"] });
      qc.invalidateQueries({ queryKey: ["attendance-summaries"] });
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const validateSummary = useMutation({
    mutationFn: ({ id, lane }: { id: string; lane: string }) =>
      api.post(`/attendance/summaries/${id}/validate?lane=${lane}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance-summaries"] }),
  });

  function handleManual(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    upsertRecord.mutate({
      employee_id: form.get("employee_id"),
      date: form.get("date"),
      status: form.get("status"),
      clock_in: form.get("clock_in") ? `${form.get("date")} ${form.get("clock_in")}` : null,
      clock_out: form.get("clock_out") ? `${form.get("date")} ${form.get("clock_out")}` : null,
      overtime_hours: Number(form.get("overtime_hours") || 0),
      notes: form.get("notes") || null,
    });
  }

  const empMap = new Map((employees ?? []).map((e) => [e.id, e]));

  return (
    <div className="space-y-4">
      <PageHeader emoji="📅" title="Absensi Harian" subtitle="Record harian clock-in/out, impor mesin fingerprint, dan validasi dua jalur" />

      <CalloutBlock emoji="ℹ️" tone="info">
        Validasi dua jalur: karyawan <b>internal</b> divalidasi HR, karyawan <b>eksternal</b> divalidasi
        Operations/approval klien. Rekap bulanan adalah artefak agregasi otomatis dari record harian.
      </CalloutBlock>

      <div className="card flex flex-wrap items-center gap-2">
        <input
          type="number"
          value={period.month}
          min={1}
          max={12}
          onChange={(e) => setPeriod({ ...period, month: Number(e.target.value) })}
          className="input w-20"
        />
        <input
          type="number"
          value={period.year}
          onChange={(e) => setPeriod({ ...period, year: Number(e.target.value) })}
          className="input w-24"
        />
        {/* C2: toggle Tabel / Kalender ala segmented view Notion */}
        <div
          className="flex overflow-hidden rounded text-sm"
          style={{ border: "1px solid var(--n-border)" }}
        >
          {(["tabel", "kalender"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="px-3 py-1.5 capitalize transition-colors"
              style={{
                backgroundColor: view === v ? "var(--n-hover)" : "transparent",
                color: view === v ? "var(--n-text)" : "var(--n-text-muted)",
                fontWeight: view === v ? 500 : 400,
              }}
            >
              {v === "tabel" ? "▤ " : "◔ "}
              {v}
            </button>
          ))}
        </div>
        <button className="btn-secondary text-xs" onClick={() => downloadFile("/attendance/template")}>
          Unduh Template CSV
        </button>
      </div>

      {/* C2: Kalender bulanan */}
      {view === "kalender" && (
        <div className="card">
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>
            Kalender — {period.month}/{period.year}
          </h2>
          <p className="mt-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
            Titik warna = status kehadiran per karyawan (arahkan kursor untuk nama).
          </p>
          <div className="mt-3 grid grid-cols-7 gap-1 text-xs">
            {["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"].map((d) => (
              <div
                key={d}
                className="pb-1 text-center font-semibold"
                style={{ color: "var(--n-text-muted)" }}
              >
                {d}
              </div>
            ))}
            {(() => {
              const first = new Date(period.year, period.month - 1, 1);
              const offset = (first.getDay() + 6) % 7; // Senin = 0
              const days = new Date(period.year, period.month, 0).getDate();
              const byDate = new Map<string, DailyRecord[]>();
              for (const r of records ?? []) {
                const list = byDate.get(r.date) ?? [];
                list.push(r);
                byDate.set(r.date, list);
              }
              const cells: (number | null)[] = [
                ...Array.from({ length: offset }, () => null),
                ...Array.from({ length: days }, (_, i) => i + 1),
              ];
              return cells.map((day, idx) => {
                if (day === null) return <div key={`pad-${idx}`} />;
                const iso = `${period.year}-${String(period.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const dayRecords = byDate.get(iso) ?? [];
                const shown = dayRecords.slice(0, 4);
                const extra = dayRecords.length - shown.length;
                return (
                  <div
                    key={iso}
                    className="min-h-[64px] rounded p-1"
                    style={{ border: "1px solid var(--n-border)" }}
                  >
                    <div className="text-right text-[11px]" style={{ color: "var(--n-text-muted)" }}>
                      {day}
                    </div>
                    <div className="flex flex-wrap gap-1 px-0.5 pt-0.5">
                      {shown.map((r) => {
                        const emp = empMap.get(r.employee_id);
                        return (
                          <span
                            key={r.id}
                            title={`${emp?.full_name ?? r.employee_id} · ${STATUS_LABELS[r.status] ?? r.status}`}
                            className="inline-block h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: STATUS_DOT[r.status] ?? "#9f9f9f" }}
                          />
                        );
                      })}
                      {extra > 0 && (
                        <span style={{ color: "var(--n-text-muted)" }}>+{extra}</span>
                      )}
                    </div>
                  </div>
                );
              });
            })()}
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-[11px]">
            {Object.entries(STATUS_DOT).map(([k, c]) => (
              <span key={k} className="flex items-center gap-1" style={{ color: "var(--n-text-muted)" }}>
                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: c }} />
                {STATUS_LABELS[k]}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Rekap bulanan - validasi dua jalur */}
      {view === "tabel" && (
      <div className="card overflow-x-auto p-0">
        <div className="border-b p-4" style={{ borderColor: "var(--n-border)" }}>
          <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>
            Rekap Bulanan — {period.month}/{period.year}
          </h2>
          <p className="mt-1 text-xs" style={{ color: "var(--n-text-muted)" }}>
            Tervalidasi menjadi masukan Saltab. Jalur: internal→HR, eksternal→Ops.
          </p>
        </div>
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)" }}>
            <tr>
              <th className="th">Karyawan</th>
              <th className="th">Jenis</th>
              <th className="th">Hadir</th>
              <th className="th">Lembur</th>
              <th className="th">Status Validasi</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(summaries ?? []).map((s) => {
              const emp = empMap.get(s.employee_id);
              return (
                <tr key={s.id}>
                  <td className="td">{emp?.full_name ?? s.employee_id}</td>
                  <td className="td text-xs">{emp?.employment_type ?? "-"}</td>
                  <td className="td">{s.present_days}</td>
                  <td className="td">{s.overtime_hours}</td>
                  <td className="td">
                    {s.client_approved ? (
                      <span className="pill p-green">tervalidasi</span>
                    ) : (
                      <div className="flex gap-2">
                        <button
                          onClick={() => validateSummary.mutate({ id: s.id, lane: "hr" })}
                          className="btn-secondary py-1 text-xs"
                        >
                          Validasi HR
                        </button>
                        <button
                          onClick={() => validateSummary.mutate({ id: s.id, lane: "klien" })}
                          className="btn-secondary py-1 text-xs"
                        >
                          Approval Klien
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
            {summaries?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada rekap untuk periode ini — buat record harian dulu.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {validateSummary.error && (
          <p className="px-4 pb-3 text-sm text-red-600">{(validateSummary.error as Error).message}</p>
        )}
      </div>
      )}

      {/* Record harian */}
      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>
          Input Manual
        </h2>
        <form onSubmit={handleManual} className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-4">
          <select name="employee_id" required className="input">
            {(employees ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.employee_no} · {e.full_name} ({e.employment_type})
              </option>
            ))}
          </select>
          <input name="date" type="date" required className="input" />
          <select name="status" defaultValue="hadir" className="input">
            {Object.entries(STATUS_LABELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <input name="overtime_hours" type="number" placeholder="Jam lembur" className="input" />
          <input name="clock_in" type="time" className="input" />
          <input name="clock_out" type="time" className="input" />
          <input name="notes" placeholder="Catatan" className="input sm:col-span-2" />
          <button className="btn sm:col-span-2">Simpan Record</button>
        </form>
      </div>

      <div className="card">
        <h2 className="font-semibold" style={{ color: "var(--n-text)" }}>
          Impor CSV Mesin Fingerprint
        </h2>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input ref={fileRef} type="file" accept=".csv" className="input w-auto" />
          <button
            className="btn-secondary"
            onClick={() => {
              const file = fileRef.current?.files?.[0];
              if (file) importCsv.mutate(file);
            }}
          >
            Upload & Impor
          </button>
        </div>
        {importResult && (
          <div className="mt-3">
            <PropertiesPanel>
              <PropertyRow icon="✅" label="Berhasil">
                {importResult.inserted} baru, {importResult.updated} diperbarui
              </PropertyRow>
              <PropertyRow icon="⚠️" label="Gagal">
                {importResult.failed.length} baris
              </PropertyRow>
            </PropertiesPanel>
            {importResult.failed.length > 0 && (
              <table className="mt-2 w-full text-xs">
                <thead>
                  <tr>
                    <th className="th">Baris</th>
                    <th className="th">No Induk</th>
                    <th className="th">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {importResult.failed.map((f, i) => (
                    <tr key={i}>
                      <td className="td">{f.row}</td>
                      <td className="td font-mono">{f.employee_no}</td>
                      <td className="td text-red-600">{f.error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {view === "tabel" && (
      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--n-hover)" }}>
            <tr>
              <th className="th">Tanggal</th>
              <th className="th">Karyawan</th>
              <th className="th">Status</th>
              <th className="th">Clock-in/out</th>
              <th className="th">Lembur</th>
              <th className="th">Sumber</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--n-border)" }}>
            {(records ?? []).map((r) => {
              const emp = empMap.get(r.employee_id);
              return (
                <tr key={r.id}>
                  <td className="td font-mono text-xs">{r.date}</td>
                  <td className="td">{emp?.full_name ?? r.employee_id}</td>
                  <td className="td">
                    <span className="pill p-gray">{STATUS_LABELS[r.status] ?? r.status}</span>
                  </td>
                  <td className="td text-xs">
                    {r.clock_in ? new Date(r.clock_in).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) : "—"} /{" "}
                    {r.clock_out ? new Date(r.clock_out).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) : "—"}
                  </td>
                  <td className="td">{r.overtime_hours}</td>
                  <td className="td text-xs">{r.source}</td>
                </tr>
              );
            })}
            {records?.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--n-text-muted)" }}>
                  Belum ada record untuk periode ini.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
