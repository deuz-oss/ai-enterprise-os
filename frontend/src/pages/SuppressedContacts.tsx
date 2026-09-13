import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserX } from "lucide-react";
import { PageHeader, CalloutBlock } from "../components/workspace";
import { api } from "../api/client";
import { confirmToast } from "../components/ui/dialogToast";

// Fase 45 -- company/contact yang ditandai "jangan hubungi lagi" (opt-out,
// sudah jadi klien kompetitor, komplain, dst.). Beda dari fitur "Black
// Lists" rekrutmen (approval berjenjang untuk kandidat) -- ini murni
// daftar administratif ringan, aktif langsung tanpa review, dan tidak
// memblokir apa pun secara hard (lihat presales/models.py::SuppressedContact).

interface Company {
  id: string;
  name: string;
}

interface Contact {
  id: string;
  company_id: string;
  name: string;
}

interface SuppressedEntry {
  id: string;
  company_id: string | null;
  contact_id: string | null;
  label: string;
  reason: string;
  created_by: string;
  creator_name: string;
  created_at: string;
}

export default function SuppressedContacts() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [targetType, setTargetType] = useState<"company" | "contact">("company");
  const [selectedCompanyId, setSelectedCompanyId] = useState("");

  const { data: entries } = useQuery({
    queryKey: ["suppressed-contacts"],
    queryFn: () => api.get<SuppressedEntry[]>("/suppressed-contacts"),
  });
  const { data: companies } = useQuery({
    queryKey: ["companies-lookup"],
    queryFn: () => api.get<Company[]>("/companies?limit=1000"),
  });
  const { data: companyContacts } = useQuery({
    queryKey: ["company-contacts", selectedCompanyId],
    queryFn: () => api.get<Contact[]>(`/companies/${selectedCompanyId}/contacts`),
    enabled: Boolean(selectedCompanyId) && targetType === "contact",
  });

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/suppressed-contacts", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suppressed-contacts"] });
      setShowForm(false);
      setSelectedCompanyId("");
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/suppressed-contacts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suppressed-contacts"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader icon={UserX} title="Suppression List" />
        <button className="btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Tutup" : "+ Tandai Suppress"}
        </button>
      </div>

      <CalloutBlock tone="info">
        Daftar company/contact yang tidak boleh di-follow-up lagi (opt-out, sudah jadi klien
        kompetitor, komplain, dst.) -- murni daftar &amp; pengingat visual, tidak memblokir
        pembuatan lead secara paksa. Siapa pun bisa tandai/lepas sendiri tanpa approval.
      </CalloutBlock>

      {showForm && (
        <form
          className="card grid grid-cols-1 gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const reason = (form.elements.namedItem("reason") as HTMLTextAreaElement).value.trim();
            const contactId = (form.elements.namedItem("contact_id") as HTMLSelectElement)?.value;
            if (!reason || !selectedCompanyId) return;
            if (targetType === "contact" && !contactId) return;
            create.mutate({
              company_id: targetType === "company" ? selectedCompanyId : null,
              contact_id: targetType === "contact" ? contactId : null,
              reason,
            });
          }}
        >
          <div className="flex gap-4 sm:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="target_type"
                checked={targetType === "company"}
                onChange={() => setTargetType("company")}
              />
              Seluruh perusahaan
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="target_type"
                checked={targetType === "contact"}
                onChange={() => setTargetType("contact")}
              />
              Satu kontak saja
            </label>
          </div>
          <select
            required
            value={selectedCompanyId}
            onChange={(e) => setSelectedCompanyId(e.target.value)}
            className="input"
            aria-label="Pilih perusahaan"
          >
            <option value="">Pilih perusahaan...</option>
            {(companies ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          {targetType === "contact" && (
            <select name="contact_id" required className="input" aria-label="Pilih kontak">
              <option value="">Pilih kontak...</option>
              {(companyContacts ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          <textarea
            name="reason"
            required
            placeholder="Alasan (mis. Sudah jadi klien kompetitor, minta opt-out)"
            className="input sm:col-span-2"
            rows={2}
          />
          <button className="btn sm:col-span-2" disabled={create.isPending}>
            Simpan
          </button>
          {create.error && (
            <p className="text-sm text-red-600 dark:text-red-400 sm:col-span-2">
              {(create.error as Error).message}
            </p>
          )}
        </form>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead
            style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--hover)" }}
          >
            <tr>
              <th className="th">Target</th>
              <th className="th">Alasan</th>
              <th className="th">Ditandai Oleh</th>
              <th className="th">Tanggal</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody style={{ borderTop: "1px solid var(--border)" }}>
            {(entries ?? []).map((entry) => (
              <tr key={entry.id}>
                <td className="td font-medium">{entry.label}</td>
                <td className="td">{entry.reason}</td>
                <td className="td">{entry.creator_name}</td>
                <td className="td">
                  {new Date(entry.created_at).toLocaleDateString("id-ID", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </td>
                <td className="td">
                  <button
                    type="button"
                    onClick={() =>
                      confirmToast(`Lepas suppression untuk "${entry.label}"?`, () =>
                        remove.mutate(entry.id)
                      )
                    }
                    className="text-xs font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                  >
                    Lepas
                  </button>
                </td>
              </tr>
            ))}
            {entries?.length === 0 && (
              <tr>
                <td colSpan={5} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada entri suppression.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
