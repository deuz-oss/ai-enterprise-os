import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api } from "../api/client";
import { confirmToast } from "./ui/dialogToast";

// Fase 41: field tambahan admin-configurable per entitas CRM -- lihat
// `presales/models.py::CustomFieldDefinition/CustomFieldValue`. Satu
// komponen dipakai ulang untuk Lead/Company/Contact (lihat Leads.tsx)
// supaya tidak duplikat form kelola-field + render-per-tipe tiga kali.
export type CustomFieldEntity = "lead" | "company" | "contact";

export type CustomFieldType =
  | "text"
  | "long_text"
  | "number"
  | "date"
  | "checkbox"
  | "select"
  | "url"
  | "email"
  | "phone";

const CUSTOM_FIELD_TYPE_LABEL: Record<CustomFieldType, string> = {
  text: "Teks",
  long_text: "Teks panjang",
  number: "Angka",
  date: "Tanggal",
  checkbox: "Checkbox",
  select: "Pilihan",
  url: "URL",
  email: "Email",
  phone: "Telepon",
};

interface CustomFieldOption {
  id: string;
  label: string;
  position: number;
}

interface CustomFieldDefinition {
  id: string;
  entity: CustomFieldEntity;
  key: string;
  label: string;
  field_type: CustomFieldType;
  is_required: boolean;
  position: number;
  options: CustomFieldOption[];
}

interface CustomFieldValue {
  field_definition_id: string;
  key: string;
  label: string;
  field_type: CustomFieldType;
  value: string | null;
}

interface CustomFieldsSectionProps {
  entity: CustomFieldEntity;
  entityId: string;
  title?: string;
  description?: string;
  /** Mode ringkas -- tanpa heading besar, dipakai saat section ini nempel
   * inline di dalam baris lain (mis. satu kontak dalam daftar). */
  compact?: boolean;
}

export function CustomFieldsSection({
  entity,
  entityId,
  title = "Field Kustom",
  description,
  compact = false,
}: CustomFieldsSectionProps) {
  const qc = useQueryClient();
  const [showFieldForm, setShowFieldForm] = useState(false);
  const [newFieldType, setNewFieldType] = useState<CustomFieldType>("text");

  const defsKey = ["custom-field-defs", entity];
  const valuesKey = ["custom-field-values", entity, entityId];

  const { data: defs } = useQuery({
    queryKey: defsKey,
    queryFn: () => api.get<CustomFieldDefinition[]>(`/custom-fields/definitions?entity=${entity}`),
  });
  const { data: values } = useQuery({
    queryKey: valuesKey,
    queryFn: () =>
      api.get<CustomFieldValue[]>(`/custom-fields/values?entity=${entity}&entity_id=${entityId}`),
    enabled: Boolean(entityId),
  });

  const setValue = useMutation({
    mutationFn: ({ fieldDefinitionId, value }: { fieldDefinitionId: string; value: string }) =>
      api.put("/custom-fields/values", {
        entity,
        entity_id: entityId,
        field_definition_id: fieldDefinitionId,
        value: value || null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: valuesKey }),
  });

  const createDef = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/custom-fields/definitions", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: defsKey });
      qc.invalidateQueries({ queryKey: valuesKey });
    },
  });

  const deleteDef = useMutation({
    mutationFn: (fieldId: string) => api.delete(`/custom-fields/definitions/${fieldId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: defsKey });
      qc.invalidateQueries({ queryKey: valuesKey });
    },
  });

  return (
    <div>
      {compact ? (
        <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {title}
        </p>
      ) : (
        <>
          <h2 className="mt-6 font-semibold" style={{ color: "var(--text)" }}>
            {title}
          </h2>
          {description && (
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
              {description}
            </p>
          )}
        </>
      )}

      <div className="mt-3 space-y-2">
        {(values ?? []).map((cfv) => {
          const def = defs?.find((d) => d.id === cfv.field_definition_id);
          return (
            <div key={cfv.field_definition_id} className="flex items-start gap-2">
              <div className="flex-1">
                <label className="mb-1 block text-xs" style={{ color: "var(--text-muted)" }}>
                  {cfv.label}
                  {def?.is_required && <span className="text-red-500"> *</span>}
                </label>
                {cfv.field_type === "long_text" ? (
                  <textarea
                    defaultValue={cfv.value ?? ""}
                    className="input"
                    rows={2}
                    onBlur={(e) =>
                      e.target.value !== (cfv.value ?? "") &&
                      setValue.mutate({ fieldDefinitionId: cfv.field_definition_id, value: e.target.value })
                    }
                  />
                ) : cfv.field_type === "checkbox" ? (
                  <input
                    type="checkbox"
                    defaultChecked={cfv.value === "true"}
                    onChange={(e) =>
                      setValue.mutate({
                        fieldDefinitionId: cfv.field_definition_id,
                        value: e.target.checked ? "true" : "false",
                      })
                    }
                  />
                ) : cfv.field_type === "select" ? (
                  <select
                    defaultValue={cfv.value ?? ""}
                    className="input"
                    onChange={(e) =>
                      setValue.mutate({ fieldDefinitionId: cfv.field_definition_id, value: e.target.value })
                    }
                  >
                    <option value="">Pilih...</option>
                    {(def?.options ?? []).map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={
                      cfv.field_type === "number"
                        ? "number"
                        : cfv.field_type === "date"
                          ? "date"
                          : cfv.field_type === "email"
                            ? "email"
                            : "text"
                    }
                    defaultValue={cfv.value ?? ""}
                    className="input"
                    onBlur={(e) =>
                      e.target.value !== (cfv.value ?? "") &&
                      setValue.mutate({ fieldDefinitionId: cfv.field_definition_id, value: e.target.value })
                    }
                  />
                )}
              </div>
              <button
                type="button"
                onClick={() =>
                  confirmToast(
                    `Hapus field "${cfv.label}" untuk semua ${entity === "lead" ? "lead" : entity === "company" ? "company" : "kontak"}?`,
                    () => deleteDef.mutate(cfv.field_definition_id)
                  )
                }
                className="mt-6 rounded p-1 hover:opacity-70"
                style={{ color: "var(--text-muted)" }}
                aria-label={`Hapus field ${cfv.label}`}
                title="Hapus field ini (berlaku untuk semua record entitas ini)"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
        {values?.length === 0 && (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Belum ada field kustom.
          </p>
        )}
      </div>

      {!showFieldForm ? (
        <button type="button" className="btn-secondary mt-3" onClick={() => setShowFieldForm(true)}>
          + Field Baru
        </button>
      ) : (
        <form
          className="mt-3 grid grid-cols-1 gap-2 rounded-lg p-3 sm:grid-cols-2"
          style={{ backgroundColor: "var(--hover)" }}
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const label = (form.elements.namedItem("label") as HTMLInputElement).value.trim();
            const key = (form.elements.namedItem("key") as HTMLInputElement).value.trim();
            const isRequired = (form.elements.namedItem("is_required") as HTMLInputElement).checked;
            const optionsRaw = (form.elements.namedItem("options") as HTMLInputElement)?.value ?? "";
            if (!label || !key) return;
            createDef.mutate(
              {
                entity,
                key,
                label,
                field_type: newFieldType,
                is_required: isRequired,
                options:
                  newFieldType === "select"
                    ? optionsRaw
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean)
                        .map((l) => ({ label: l }))
                    : [],
              },
              {
                onSuccess: () => {
                  form.reset();
                  setShowFieldForm(false);
                  setNewFieldType("text");
                },
              }
            );
          }}
        >
          <input name="label" required placeholder="Nama field (mis. NPWP)" className="input" />
          <input
            name="key"
            required
            placeholder="Key unik (mis. npwp)"
            pattern="[a-z0-9_]+"
            title="Huruf kecil, angka, underscore saja"
            className="input"
          />
          <select
            name="field_type"
            value={newFieldType}
            onChange={(e) => setNewFieldType(e.target.value as CustomFieldType)}
            className="input"
          >
            {(Object.keys(CUSTOM_FIELD_TYPE_LABEL) as CustomFieldType[]).map((t) => (
              <option key={t} value={t}>
                {CUSTOM_FIELD_TYPE_LABEL[t]}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)" }}>
            <input type="checkbox" name="is_required" /> Wajib diisi
          </label>
          {newFieldType === "select" && (
            <input
              name="options"
              placeholder="Opsi, pisahkan koma (mis. Payroll Only, Full Outsourcing)"
              className="input sm:col-span-2"
            />
          )}
          <div className="flex gap-2 sm:col-span-2">
            <button className="btn" disabled={createDef.isPending}>
              Simpan Field
            </button>
            <button type="button" className="btn-secondary" onClick={() => setShowFieldForm(false)}>
              Batal
            </button>
          </div>
          {createDef.error && (
            <p className="text-sm text-red-600 dark:text-red-400 sm:col-span-2">
              {(createDef.error as Error).message}
            </p>
          )}
        </form>
      )}
    </div>
  );
}
