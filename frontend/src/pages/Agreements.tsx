import { Fragment, FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Download, FileCheck2, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../api/client";
import { Badge, Button, Card, KpiCard, PillTabs, type PillTab } from "../components/ui";
import { PageHeader } from "../components/workspace";
import type { Lead } from "./Leads";

/** Agreement generator (PRD Fase 20 item 3-4) — sama pola dengan
 * Quotations.tsx, bedanya: status tambahan `internal_review` (klausul
 * legal wajib direview sebelum dikirim), output `.docx` (bukan PDF), dan
 * pengiriman ke klien lewat e-signature (Privy/sandbox), bukan sekadar
 * "sent" langsung selesai.
 */

interface TemplateField {
  key: string;
  label: string;
  type: string;
}

interface AgreementTemplateT {
  id: string;
  name: string;
  field_schema: TemplateField[];
  is_active: boolean;
}

interface Agreement {
  id: string;
  lead_id: string;
  template_id: string;
  field_values: Record<string, string | number>;
  status: string;
  review_note: string | null;
  sent_at: string | null;
  signed_at: string | null;
  created_at: string;
}

const STATUS_TONE: Record<
  string,
  "neutral" | "info" | "success" | "warning" | "danger" | "accent"
> = {
  draft: "neutral",
  internal_review: "warning",
  approved: "info",
  sent: "accent",
  signed: "success",
  declined: "danger",
  expired: "danger",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  internal_review: "Review Internal",
  approved: "Disetujui",
  sent: "Menunggu Tanda Tangan",
  signed: "Ditandatangani",
  declined: "Ditolak",
  expired: "Kedaluwarsa",
};

export default function Agreements() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [leadId, setLeadId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sendFormId, setSendFormId] = useState<string | null>(null);

  const { data: leads } = useQuery({
    queryKey: ["leads-lookup"],
    queryFn: () => api.get<Lead[]>("/leads?limit=1000"),
  });
  const { data: templates } = useQuery({
    queryKey: ["agreement-templates"],
    queryFn: () => api.get<AgreementTemplateT[]>("/agreement-templates?active_only=true"),
  });
  const { data: agreements } = useQuery({
    queryKey: ["agreements"],
    queryFn: () => api.get<Agreement[]>("/agreements"),
  });
  const [statusTab, setStatusTab] = useState("");
  const filteredAgreements = useMemo(
    () => (agreements ?? []).filter((a) => !statusTab || a.status === statusTab),
    [agreements, statusTab]
  );
  const statusTabs: PillTab[] = useMemo(() => {
    const all = agreements ?? [];
    return [
      { key: "", label: "Semua", count: all.length },
      ...Object.keys(STATUS_LABEL).map((s) => ({
        key: s,
        label: STATUS_LABEL[s],
        count: all.filter((a) => a.status === s).length,
      })),
    ];
  }, [agreements]);
  const reviewCount = (agreements ?? []).filter((a) => a.status === "internal_review").length;
  const awaitingSignCount = (agreements ?? []).filter((a) => a.status === "sent").length;
  const signedCount = (agreements ?? []).filter((a) => a.status === "signed").length;

  const invalidate = () => qc.invalidateQueries({ queryKey: ["agreements"] });

  const createAgreement = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/agreements", body),
    onSuccess: () => {
      setShowForm(false);
      setLeadId("");
      setTemplateId("");
      invalidate();
    },
  });
  const submitReview = useMutation({
    mutationFn: (id: string) => api.post(`/agreements/${id}/submit-review`, {}),
    onSuccess: invalidate,
  });
  const approve = useMutation({
    mutationFn: (id: string) => api.post(`/agreements/${id}/approve`, {}),
    onSuccess: invalidate,
  });
  const decline = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      api.post(`/agreements/${id}/decline`, { note }),
    onSuccess: invalidate,
  });
  const sendEsign = useMutation({
    mutationFn: ({
      id,
      signer_name,
      signer_email,
    }: {
      id: string;
      signer_name: string;
      signer_email: string;
    }) => api.post(`/agreements/${id}/send-esign`, { signer_name, signer_email }),
    onSuccess: () => {
      setSendFormId(null);
      invalidate();
    },
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
    createAgreement.mutate({ lead_id: leadId, template_id: templateId, field_values });
  }

  function handleSend(e: FormEvent<HTMLFormElement>, id: string) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    sendEsign.mutate({
      id,
      signer_name: String(form.get("signer_name") ?? ""),
      signer_email: String(form.get("signer_email") ?? ""),
    });
  }

  async function openDownload(id: string) {
    const { url } = await api.get<{ url: string }>(`/agreements/${id}/download-url`);
    window.open(url, "_blank");
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader icon={FileCheck2} title="Agreement" />
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Tutup" : "+ Agreement Baru"}
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
                Belum ada template agreement aktif. Buat template dulu lewat API
                /agreement-templates.
              </p>
            )}
            <Button
              type="submit"
              loading={createAgreement.isPending}
              disabled={!leadId || !templateId}
            >
              Simpan Agreement
            </Button>
          </form>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Total Agreement" value={(agreements ?? []).length} icon={FileCheck2} iconTone="info" />
        <KpiCard
          label="Review Internal"
          value={reviewCount}
          icon={Clock}
          iconTone="warning"
          badge={reviewCount > 0 ? { label: "Perlu Tindakan", tone: "warning" } : undefined}
        />
        <KpiCard label="Menunggu TTD" value={awaitingSignCount} icon={Send} iconTone="accent" />
        <KpiCard label="Ditandatangani" value={signedCount} icon={CheckCircle2} iconTone="success" />
      </div>

      <PillTabs tabs={statusTabs} value={statusTab} onChange={setStatusTab} />

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
            {filteredAgreements.map((a) => (
              <Fragment key={a.id}>
                <tr
                  onClick={() => setSelectedId(a.id === selectedId ? null : a.id)}
                  className="cursor-pointer transition-colors"
                  style={{
                    backgroundColor: selectedId === a.id ? "var(--accent-tint)" : undefined,
                  }}
                >
                  <td className="td font-medium">{leadName(a.lead_id)}</td>
                  <td className="td">
                    <Badge tone={STATUS_TONE[a.status] ?? "neutral"}>
                      {STATUS_LABEL[a.status] ?? a.status}
                    </Badge>
                  </td>
                  <td className="td">{new Date(a.created_at).toLocaleDateString("id-ID")}</td>
                  <td className="td" onClick={(e) => e.stopPropagation()}>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {a.status === "draft" && (
                        <Button size="sm" variant="secondary" onClick={() => submitReview.mutate(a.id)}>
                          Ajukan Review
                        </Button>
                      )}
                      {a.status === "internal_review" && (
                        <>
                          <Button size="sm" onClick={() => approve.mutate(a.id)}>
                            <ThumbsUp className="h-3.5 w-3.5" /> Setuju
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => {
                              const note = window.prompt("Catatan penolakan (wajib):");
                              if (note) decline.mutate({ id: a.id, note });
                            }}
                          >
                            <ThumbsDown className="h-3.5 w-3.5" /> Tolak
                          </Button>
                        </>
                      )}
                      {a.status === "approved" && (
                        <Button
                          size="sm"
                          onClick={() => setSendFormId(sendFormId === a.id ? null : a.id)}
                        >
                          <Send className="h-3.5 w-3.5" /> Kirim untuk TTD
                        </Button>
                      )}
                      {(a.status === "sent" || a.status === "signed") && (
                        <Button size="sm" variant="secondary" onClick={() => openDownload(a.id)}>
                          <Download className="h-3.5 w-3.5" /> Unduh
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
                {sendFormId === a.id && (
                  <tr onClick={(e) => e.stopPropagation()}>
                    <td colSpan={4} className="td" style={{ backgroundColor: "var(--hover)" }}>
                      <form
                        onSubmit={(e) => handleSend(e, a.id)}
                        className="flex flex-wrap items-center gap-2"
                      >
                        <input
                          name="signer_name"
                          required
                          placeholder="Nama penandatangan klien *"
                          className="input w-auto py-1 text-xs"
                        />
                        <input
                          name="signer_email"
                          type="email"
                          required
                          placeholder="Email penandatangan *"
                          className="input w-auto py-1 text-xs"
                        />
                        <Button type="submit" size="sm" loading={sendEsign.isPending}>
                          Kirim
                        </Button>
                      </form>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {filteredAgreements.length === 0 && (
              <tr>
                <td colSpan={4} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  {(agreements ?? []).length === 0 ? "Belum ada agreement." : "Tidak ada agreement untuk status ini."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedId &&
        (() => {
          const a = agreements?.find((x) => x.id === selectedId);
          if (!a) return null;
          return (
            <Card title="Detail Agreement" subtitle={leadName(a.lead_id)}>
              <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                {Object.entries(a.field_values).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                      {k}
                    </dt>
                    <dd style={{ color: "var(--text)" }}>{String(v)}</dd>
                  </div>
                ))}
              </dl>
              {a.review_note && (
                <p className="mt-3 text-sm text-red-600 dark:text-red-400">
                  Catatan penolakan: {a.review_note}
                </p>
              )}
            </Card>
          );
        })()}
    </div>
  );
}
