import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { api, formatDate } from "../api/client";

/** Respons `GET /employees/compliance-digest` (backend hrd/compliance_digest.py). */
interface Digest {
  week: string;
  counts: { contracts_ending: number; contracts_lapsed: number; bpjs_missing: number };
  contracts_ending: { employee_id: string; employee_name: string; contract_no: string; end_date: string; days_left: number; action: string }[];
  contracts_lapsed: { employee_id: string; employee_name: string; contract_no: string; end_date: string; days_overdue: number; action: string }[];
  bpjs_missing: { employee_id: string; employee_name: string; missing: string[]; action: string }[];
}

function Section({
  title,
  count,
  tone,
  children,
}: {
  title: string;
  count: number;
  tone: string;
  children: React.ReactNode;
}) {
  if (count === 0) return null;
  return (
    <details open={count <= 5} className="text-sm">
      <summary className="cursor-pointer font-medium" style={{ color: "var(--text)" }}>
        <span className={`pill ${tone} mr-2`}>{count}</span>
        {title}
      </summary>
      <ul className="mt-1.5 space-y-1 pl-1">{children}</ul>
    </details>
  );
}

function EmployeeLink({ id, name }: { id: string; name: string }) {
  return (
    <Link to={`/employees/${id}`} className="font-medium hover:underline" style={{ color: "var(--accent)" }}>
      {name}
    </Link>
  );
}

/**
 * Digest kepatuhan kontrak & BPJS (AI opportunity #4). Isinya sama dengan
 * notifikasi mingguan ke admin/HR, tapi selalu terkini saat halaman dibuka.
 * Menggantikan callout lama "Reminder Kontrak ≤30 hari" (subset dari ini).
 */
export function ComplianceDigestCard() {
  const { data } = useQuery({
    queryKey: ["compliance-digest"],
    queryFn: () => api.get<Digest>("/employees/compliance-digest"),
  });
  // Tautan notifikasi digest -> /employees#kepatuhan: SPA tidak menggulir ke
  // hash sendiri, dan kartu baru ada setelah data dimuat.
  const { hash } = useLocation();
  useEffect(() => {
    if (data && hash === "#kepatuhan") document.getElementById("kepatuhan")?.scrollIntoView({ block: "start" });
  }, [data, hash]);
  if (!data) return null;
  const total = data.counts.contracts_ending + data.counts.contracts_lapsed + data.counts.bpjs_missing;
  return (
    <section id="kepatuhan" className="card space-y-2" aria-labelledby="kepatuhan-title">
      <h2 id="kepatuhan-title" className="flex items-center gap-2 font-semibold" style={{ color: "var(--text)" }}>
        {total ? (
          <ShieldAlert className="h-4 w-4 text-amber-600" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
        )}
        Kepatuhan minggu ini <span className="text-xs font-normal" style={{ color: "var(--th-color)" }}>({data.week})</span>
      </h2>
      {total === 0 ? (
        <p className="text-sm" style={{ color: "var(--th-color)" }}>
          Semua beres: tidak ada kontrak yang segera berakhir atau lewat, dan BPJS karyawan aktif lengkap.
        </p>
      ) : (
        <>
          <Section title="Kontrak sudah lewat, karyawan masih aktif" count={data.counts.contracts_lapsed} tone="p-red">
            {data.contracts_lapsed.map((c) => (
              <li key={c.employee_id}>
                <EmployeeLink id={c.employee_id} name={c.employee_name} /> — {c.contract_no} berakhir{" "}
                {formatDate(c.end_date)} ({c.days_overdue} hari lalu).{" "}
                <span style={{ color: "var(--th-color)" }}>{c.action}</span>
              </li>
            ))}
          </Section>
          <Section title="Kontrak berakhir ≤ 30 hari" count={data.counts.contracts_ending} tone="p-yellow">
            {data.contracts_ending.map((c) => (
              <li key={c.employee_id}>
                <EmployeeLink id={c.employee_id} name={c.employee_name} /> — {c.contract_no} berakhir{" "}
                {formatDate(c.end_date)} ({c.days_left} hari lagi).{" "}
                <span style={{ color: "var(--th-color)" }}>{c.action}</span>
              </li>
            ))}
          </Section>
          <Section title="BPJS belum lengkap" count={data.counts.bpjs_missing} tone="p-orange">
            {data.bpjs_missing.map((b) => (
              <li key={b.employee_id}>
                <EmployeeLink id={b.employee_id} name={b.employee_name} /> —{" "}
                <span style={{ color: "var(--th-color)" }}>{b.action}</span>
              </li>
            ))}
          </Section>
        </>
      )}
    </section>
  );
}
