import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileSignature, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../api/client";
import { Badge, Button, Card } from "../components/ui";
import { PageHeader } from "../components/workspace";
import type { Lead } from "./Leads";

/** Quotation generator (PRD Fase 20 item 2) — draft dibuat dari template
 * (field_schema dinamis), lewat approval satu level (admin/management),
 * baru bisa dikirim (render PDF + simpan ke storage). Halaman ini sengaja
 * TIDAK pakai modal (belum ada primitive-nya di codebase) — form inline
 * expand, sama seperti JobOrders.tsx/Leads.tsx.
 */

interface TemplateField {
  key: string;
  label: string;
  type: string;
}

interface QuotationTemplateT {
  id: string;
  name: string;
  field_schema: TemplateField[];
  is_active: boolean;
}

interface Quotation {
  id: string;
  lead_id: string;
  template_id: string;
  field_values: Record<string, string | number>;
  status: string;
  rejection_note: string | null;
  sent_at: string | null;
  created_at: string;
}

const STATUS_TONE: Record<
  string,
  "neutral" | "info" | "success" | "warning" | "danger" | "accent"
> = {
  draft: "neutral",
  pending_approval: "warning",
  approved: "info",
  rejected: "danger",
  sent: "success",
  accepted_by_client: "success",
  expired: "danger",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  pending_approval: "Menunggu Approval",
  approved: "Disetujui",
  rejected: "Ditolak",
  sent: "Terkirim",
  accepted_by_client: "Diterima Klien",
  expired: "Kedaluwarsa",
};

export default function Quotations() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [leadId, setLeadId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: leads } = useQuery({
    queryKey: ["leads-lookup"],
    queryFn: () => api.get<Lead[]>("/leads?limit=1000"),
  });
  const { data: templates } = useQuery({
    queryKey: ["quotation-templates"],
    queryFn: () => api.get<QuotationTemplateT[]>("/quotation-templates?active_only=true"),
  });
  const { data: quotations } = useQuery({
    queryKey: ["quotations"],
    queryFn: () => api.get<Quotation[]>("/quotations"),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["quotations"] });

  const createQuotation = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/quotations", body),
    onSuccess: () => {
      setShowForm(false);
      setLeadId("");
      setTemplateId("");
      invalidate();
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
  });
  const submitApproval = useMutation({
    mutationFn: (id: string) => api.post(`/quotations/${id}/submit-approval`, {}),
    onSuccess: invalidate,
  });
  const approve = useMutation({
    mutationFn: (id: string) => api.post(`/quotations/${id}/approve`, {}),
    onSuccess: invalidate,
  });
  const reject = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.post(`/quotations/${id}/reject`, { note }),
    onSuccess: invalidate,
  });
  const send = useMutation({
    mutationFn: (id: string) => api.post(`/quotations/${id}/send`, {}),
    onSuccess: invalidate,
  });

  const selectedTemplate = templates?.find((t) => t.id === templateId);

  function leadName(id: string) {
    return leads?.find((l) => l.id === id)?.company_name ?? "—";
  }

  function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!leadId || !templateId || !selectedTemplate) return;
    const form = new FormData(e.currentTarget);
    const field_values: Record<string, string> = {};
    for (const f of selectedTemplate.field_schema) {
      field_values[f.key] = String(form.get(f.key) ?? "");
    }
    createQuotation.mutate({ lead_id: leadId, template_id: templateId, field_values });
  }

  async function openDownload(id: string) {
    const { url } = await api.get<{ url: string }>(`/quotations/${id}/download-url`);
    window.open(url, "_blank");
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader icon={FileSignature} title="Quotation" />
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Tutup" : "+ Quotation Baru"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <select
                value={leadId}
                onChange={(e) => setLeadId(e.target.value)}
                className="input"
                required
              >
                <option value="">Pilih lead...</option>
                {(leads ?? []).map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.company_name}
                  </option>
                ))}
              </select>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className="input"
                required
              >
                <option value="">Pilih template...</option>
                {(templates ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            {selectedTemplate && selectedTemplate.field_schema.length > 0 && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {selectedTemplate.field_schema.map((f) => (
                  <input
                    key={f.key}
                    name={f.key}
                    placeholder={f.label}
                    className="input"
                    type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                  />
                ))}
              </div>
            )}
            {templates?.length === 0 && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Belum ada template quotation aktif. Buat template dulu lewat API
                /quotation-templates.
              </p>
            )}
            <Button
              type="submit"
              loading={createQuotation.isPending}
              disabled={!leadId || !templateId}
            >
              Simpan Quotation
            </Button>
          </form>
        </Card>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--hover)" }}>
            <tr>
              <th className="th">Lead</th>
              <th className="th">Status</th>
              <th className="th">Dibuat</th>
              <th className="th">Aksi</th>
            </tr>
          </thead>
          <tbody style={{ borderTop: "1px solid var(--border)" }}>
            {(quotations ?? []).map((q) => (
              <tr
                key={q.id}
                onClick={() => setSelectedId(q.id === selectedId ? null : q.id)}
                className="cursor-pointer transition-colors"
                style={{
                  backgroundColor: selectedId === q.id ? "var(--accent-tint)" : undefined,
                }}
              >
                <td className="td font-medium">{leadName(q.lead_id)}</td>
                <td className="td">
                  <Badge tone={STATUS_TONE[q.status] ?? "neutral"}>
                    {STATUS_LABEL[q.status] ?? q.status}
                  </Badge>
                </td>
                <td className="td">{new Date(q.created_at).toLocaleDateString("id-ID")}</td>
                <td className="td" onClick={(e) => e.stopPropagation()}>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {q.status === "draft" && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => submitApproval.mutate(q.id)}
                      >
                        Ajukan Approval
                      </Button>
                    )}
                    {q.status === "pending_approval" && (
                      <>
                        <Button size="sm" onClick={() => approve.mutate(q.id)}>
                          <ThumbsUp className="h-3.5 w-3.5" /> Setuju
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => {
                            const note = window.prompt("Catatan penolakan (wajib):");
                            if (note) reject.mutate({ id: q.id, note });
                          }}
                        >
                          <ThumbsDown className="h-3.5 w-3.5" /> Tolak
                        </Button>
                      </>
                    )}
                    {q.status === "approved" && (
                      <Button size="sm" onClick={() => send.mutate(q.id)}>
                        <Send className="h-3.5 w-3.5" /> Kirim
                      </Button>
                    )}
                    {(q.status === "sent" || q.status === "accepted_by_client") && (
                      <Button size="sm" variant="secondary" onClick={() => openDownload(q.id)}>
                        <Download className="h-3.5 w-3.5" /> Unduh
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {(quotations ?? []).length === 0 && (
              <tr>
                <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada quotation.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId &&
        (() => {
          const q = quotations?.find((x) => x.id === selectedId);
          if (!q) return null;
          return (
            <Card title="Detail Quotation" subtitle={leadName(q.lead_id)}>
              <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                {Object.entries(q.field_values).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                      {k}
                    </dt>
                    <dd style={{ color: "var(--text)" }}>{String(v)}</dd>
                  </div>
                ))}
              </dl>
              {q.rejection_note && (
                <p className="mt-3 text-sm text-red-600 dark:text-red-400">
                  Catatan penolakan: {q.rejection_note}
                </p>
              )}
            </Card>
          );
        })()}
    </div>
  );
}
