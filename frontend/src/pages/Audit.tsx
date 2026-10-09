import { useState } from "react";
import { Shield } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { DataTable, type Column } from "../components/ui";
import { useQuery } from "@tanstack/react-query";
import { api, formatDateTime } from "../api/client";

interface AuditItem {
  id: string;
  tenant_id: string | null;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  object_key: string | null;
  ip: string | null;
  created_at: string;
  detail: Record<string, unknown> | null;
}

const ACTION_BADGES: Record<string, string> = {
  auth: "p-gray",
  cv: "p-blue",
  contract: "p-indigo",
  employee_document: "p-violet",
  legal_document: "p-blue",
  esign: "p-green",
};

function badgeCls(action: string): string {
  const prefix = action.split(".")[0];
  return ACTION_BADGES[prefix] ?? "p-gray";
}

export default function Audit() {
  const [actionPrefix, setActionPrefix] = useState("");
  const [entityType, setEntityType] = useState("");

  const auditQuery = useQuery({
    queryKey: ["audit", actionPrefix, entityType],
    queryFn: () => {
      const params = new URLSearchParams();
      if (actionPrefix) params.set("action_prefix", actionPrefix);
      if (entityType) params.set("entity_type", entityType);
      return api.get<{ total: number; items: AuditItem[] }>(
        `/audit/logs?${params.toString()}`
      );
    },
  });
  const data = auditQuery.data;

  const auditColumns: Column<AuditItem>[] = [
    {
      key: "time",
      header: "Waktu",
      className: "whitespace-nowrap text-xs",
      cell: (item) => formatDateTime(item.created_at),
    },
    { key: "action", header: "Aksi", cell: (item) => <span className={`pill ${badgeCls(item.action)}`}>{item.action}</span> },
    {
      key: "entity",
      header: "Entitas",
      className: "font-mono text-xs",
      cell: (item) => `${item.entity_type ?? "-"}${item.entity_id ? ` · ${item.entity_id.slice(0, 8)}…` : ""}`,
    },
    {
      key: "detail",
      header: "Detail",
      className: "max-w-sm truncate text-xs",
      cell: (item) => {
        const detail = item.detail ? JSON.stringify(item.detail) : "-";
        return <span title={detail}>{detail}</span>;
      },
    },
    { key: "ip", header: "IP", className: "font-mono text-xs", cell: (item) => item.ip ?? "-" },
    {
      key: "user",
      header: "User ID",
      className: "font-mono text-xs",
      cell: (item) => (item.user_id ? `${item.user_id.slice(0, 8)}…` : "-"),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader icon={Shield} title="Jejak Audit" />
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {data ? `${data.total} event` : "..."} · append-only
        </span>
      </div>

      <div className="card flex flex-wrap items-center gap-3">
        <select
          className="input w-auto"
          value={actionPrefix}
          onChange={(e) => setActionPrefix(e.target.value)}
          aria-label="Filter jenis aksi"
        >
          <option value="">Semua aksi</option>
          {["auth.", "cv.", "contract.", "employee_document.", "legal_document.", "esign."].map(
            (p) => (
              <option key={p} value={p}>
                {p.replace(".", "")}
              </option>
            )
          )}
        </select>
        <input
          className="input w-auto"
          placeholder="Entity type (mis. candidate)"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
        />
      </div>

      {/* Tanpa sort: API hanya mengembalikan 100 event terbaru (urut waktu),
          sort satu halaman terpotong akan menyesatkan. */}
      {data && data.total > data.items.length && (
        <p className="text-sm" style={{ color: "var(--th-color)" }}>
          Menampilkan {data.items.length} event terbaru dari {data.total}. Persempit dengan filter di atas.
        </p>
      )}
      <DataTable
        label="Event audit"
        rows={data?.items}
        columns={auditColumns}
        rowKey={(item) => item.id}
        query={auditQuery}
        emptyTitle={actionPrefix || entityType ? "Tidak ada event untuk filter ini." : "Belum ada event audit."}
      />
    </div>
  );
}
