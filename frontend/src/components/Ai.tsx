export interface Screening {
  id: string;
  candidate_id: string;
  job_order_id: string | null;
  score: number;
  verdict: string;
  summary: string;
  strengths: string[];
  risks: string[];
  model: string;
  created_at: string;
}

export interface MatchItem {
  candidate: {
    id: string;
    full_name: string;
    status: string;
    expected_salary: number | null;
    cv_file_name: string | null;
  };
  screening: Screening;
}

export interface MatchResult {
  job_order_id: string;
  evaluated: number;
  reused: number;
  results: MatchItem[];
}

const VERDICT_COLORS: Record<string, string> = {
  direkomendasikan: "pill p-green",
  dipertimbangkan: "pill p-yellow",
  tidak_direkomendasikan: "pill p-red",
};

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-700 dark:text-emerald-400";
  if (score >= 50) return "text-amber-700 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function ScoreBadge({ score }: { score: number }) {
  return <span className={`font-bold ${scoreColor(score)}`}>{score}</span>;
}

export function AiResultCard({ screening }: { screening: Screening }) {
  return (
    <div className="rounded-lg border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--hover)" }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${VERDICT_COLORS[screening.verdict] ?? "pill p-gray"}`}>
          {screening.verdict.replace(/_/g, " ")}
        </span>
        <span className="text-sm" style={{ color: "var(--th-color)" }}>
          Skor kecocokan: <ScoreBadge score={screening.score} />/100
        </span>
        {screening.model && (
          <span className="ml-auto text-xs" style={{ color: "var(--th-color)" }}>model: {screening.model}</span>
        )}
      </div>
      <p className="mt-2 text-sm" style={{ color: "var(--text)" }}>{screening.summary}</p>
      {(screening.strengths.length > 0 || screening.risks.length > 0) && (
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {screening.strengths.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
                Kekuatan
              </p>
              <ul className="mt-1 list-disc pl-4 text-xs" style={{ color: "var(--th-color)" }}>
                {screening.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {screening.risks.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">Risiko</p>
              <ul className="mt-1 list-disc pl-4 text-xs" style={{ color: "var(--th-color)" }}>
                {screening.risks.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <p className="mt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
        {new Date(screening.created_at).toLocaleString("id-ID")}
      </p>
    </div>
  );
}
