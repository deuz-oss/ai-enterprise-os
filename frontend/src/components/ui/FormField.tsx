import { useId, type ReactNode } from "react";

/**
 * Label + kontrol + petunjuk + error untuk satu kolom form (audit 2026-11-11
 * Phase 1, §9).
 *
 * Menggantikan label berupa placeholder ("Email *"): placeholder hilang begitu
 * user mengetik, kontrasnya rendah, dan bukan nama aksesibel yang andal.
 * Komponen ini yang memegang id, jadi label, petunjuk, dan pesan error selalu
 * tersambung ke kontrolnya (`htmlFor`, `aria-describedby`, `aria-invalid`).
 *
 *   <FormField label="Email" required error={emailError}>
 *     {(field) => <input {...field} name="email" type="email" className="input" />}
 *   </FormField>
 */
export interface FieldControlProps {
  id: string;
  required?: boolean;
  "aria-invalid"?: true;
  "aria-describedby"?: string;
}

export function FormField({
  label,
  required = false,
  hint,
  error,
  className = "",
  children,
}: {
  label: string;
  required?: boolean;
  hint?: ReactNode;
  error?: string | null;
  className?: string;
  children: (field: FieldControlProps) => ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className={`space-y-1 ${className}`}>
      <label htmlFor={id} className="block text-sm font-medium" style={{ color: "var(--text)" }}>
        {label}
        {required && (
          <span className="ml-0.5" style={{ color: "var(--danger)" }} aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children({
        id,
        required: required || undefined,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy,
      })}
      {hint && (
        <p id={hintId} className="text-xs" style={{ color: "var(--th-color)" }}>
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
