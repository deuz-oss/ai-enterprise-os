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
  direkomendasikan: "bg-emerald-100 text-emerald-700",
  dipertimbangkan: "bg-amber-100 text-amber-700",
  tidak_direkomendasikan: "bg-red-100 text-red-600",
};

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-600";
  if (score >= 50) return "text-amber-600";
  return "text-red-500";
}

export function ScoreBadge({ score }: { score: number }) {
  return <span className={`font-bold ${scoreColor(score)}`}>{score}</span>;
}

export function AiResultCard({ screening }: { screening: Screening }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`badge border-0 ${VERDICT_COLORS[screening.verdict] ?? ""}`}>
          {screening.verdict.replace(/_/g, " ")}
        </span>
        <span className="text-sm text-slate-500">
          Skor kecocokan: <ScoreBadge score={screening.score} />/100
        </span>
        {screening.model && (
          <span className="ml-auto text-xs text-slate-400">model: {screening.model}</span>
        )}
      </div>
      <p className="mt-2 text-sm text-slate-700">{screening.summary}</p>
      {(screening.strengths.length > 0 || screening.risks.length > 0) && (
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {screening.strengths.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                Kekuatan
              </p>
              <ul className="mt-1 list-disc pl-4 text-xs text-slate-600">
                {screening.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {screening.risks.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-red-600">Risiko</p>
              <ul className="mt-1 list-disc pl-4 text-xs text-slate-600">
                {screening.risks.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <p className="mt-2 text-[11px] text-slate-400">
        {new Date(screening.created_at).toLocaleString("id-ID")}
      </p>
    </div>
  );
}
