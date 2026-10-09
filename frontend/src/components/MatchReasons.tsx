import { Sparkles } from "lucide-react";

/** Satu baris rincian skor match (backend recruitment `_rule_reasons`). */
export interface MatchReason {
  label: string;
  points: number;
}

/** Bagian penjelasan dari respons `/recruitment/job-orders/{id}/match(es)`. */
export interface MatchExplain {
  match_score: number;
  explain: string;
  explain_source?: "ai" | "rules";
  reasons?: MatchReason[];
  missing: string[];
}

const fmtPoints = (p: number) => (p > 0 ? `+${p}` : String(p));

/** Versi teks (untuk atribut `title`), mis. "Skill cocok: las +70 · Domisili cocok +8 = 78". */
export function matchReasonsText(m: MatchExplain): string {
  const parts = (m.reasons ?? []).map((r) => `${r.label} ${fmtPoints(r.points)}`);
  const breakdown = parts.length ? `${parts.join(" · ")} = ${m.match_score}` : m.explain;
  const ai = m.explain_source === "ai" ? `\nAI: ${m.explain}` : "";
  const missing = m.missing.length ? `\nKurang: ${m.missing.join(", ")}` : "";
  return breakdown + ai + missing;
}

/**
 * Alasan skor match (AI opportunity #8). Rincian poin dihitung deterministik
 * di backend dan jumlahnya = skor; kalimat AI (bila ada) hanya pelengkap dan
 * diberi label supaya recruiter tahu mana fakta hitungan, mana tafsiran AI.
 */
export function MatchReasons({ match }: { match: MatchExplain }) {
  const reasons = match.reasons ?? [];
  return (
    <div className="mt-1 space-y-1.5 text-sm" style={{ color: "var(--text)" }}>
      {match.explain_source === "ai" ? (
        <p className="flex items-start gap-1.5">
          <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" style={{ color: "var(--th-color)" }} />
          <span>
            <span className="text-xs font-semibold" style={{ color: "var(--th-color)" }}>
              Alasan AI:{" "}
            </span>
            {match.explain}
          </span>
        </p>
      ) : (
        reasons.length === 0 && <p>{match.explain}</p>
      )}
      {reasons.length > 0 && (
        <ul className="flex flex-wrap gap-1" aria-label={`Rincian skor ${match.match_score}`}>
          {reasons.map((r) => (
            <li
              key={r.label}
              className={`pill text-[11px] ${r.points > 0 ? "p-green" : r.points < 0 ? "p-orange" : "p-gray"}`}
            >
              {r.label} <span className="num font-semibold">{fmtPoints(r.points)}</span>
            </li>
          ))}
        </ul>
      )}
      {match.missing.length > 0 && (
        <ul className="flex flex-wrap gap-1" aria-label="Persyaratan yang belum terpenuhi">
          {match.missing.map((m) => (
            <li key={m} className="pill p-red text-[11px]">
              Kurang: {m}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
