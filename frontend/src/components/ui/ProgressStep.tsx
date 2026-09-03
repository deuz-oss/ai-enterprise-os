import { Check } from "lucide-react";

/**
 * Komponen dasar #4 — BARU, belum ada padanannya di index.css sebelum ini.
 * Dipakai pertama kali untuk tracker Placement (Fase 21 PRD: sourced ->
 * screening -> interview -> submit -> ... -> onboarded).
 *
 * Sengaja pakai var(--accent) untuk state "selesai"/"aktif" — ini komponen
 * yang PALING langsung kelihatan efeknya begitu token warna final
 * (teal/coral/dll) diputuskan, karena literally garis & bulatan yang jadi
 * representasi visual "kemajuan" ke depan.
 */

interface ProgressStepProps {
  steps: string[];
  currentIndex: number; // 0-based; step di index ini dianggap "sedang berjalan"
}

export function ProgressStep({ steps, currentIndex }: ProgressStepProps) {
  return (
    <div>
      <div className="flex items-center">
        {steps.map((_, i) => {
          const isDone = i < currentIndex;
          const isActive = i === currentIndex;
          const isLast = i === steps.length - 1;
          return (
            <div key={i} className="flex flex-1 items-center last:flex-none">
              <div
                className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-xs font-medium"
                style={
                  isDone || isActive
                    ? { backgroundColor: "var(--accent)", color: "#fff" }
                    : { border: "1px solid var(--border)", color: "var(--text-muted)" }
                }
              >
                {isDone ? <Check className="h-3 w-3" /> : i + 1}
              </div>
              {!isLast && (
                <div
                  className="h-0.5 flex-1"
                  style={{ backgroundColor: isDone ? "var(--accent)" : "var(--border)" }}
                />
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex text-[11px]" style={{ color: "var(--text-muted)" }}>
        {steps.map((label, i) => (
          <div key={i} className="flex-1 text-center first:text-left last:text-right">
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
