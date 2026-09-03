import { useState } from "react";
import { Shield } from "lucide-react";
import { PageHeader } from "../components/workspace";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

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

  const { data } = useQuery({
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

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead style={{ backgroundColor: "var(--hover)", borderBottom: "1px solid var(--border)" }}>
            <tr>
              <th className="th">Waktu</th>
              <th className="th">Aksi</th>
              <th className="th">Entitas</th>
              <th className="th">Detail</th>
              <th className="th">IP</th>
              <th className="th">User ID</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
            {(data?.items ?? []).map((item) => (
              <tr key={item.id} className="transition-colors hover:bg-[var(--hover)]">
                <td className="td whitespace-nowrap text-xs" style={{ color: "var(--text-muted)" }}>
                  {new Date(item.created_at).toLocaleString("id-ID")}
                </td>
                <td className="td">
                  <span className={`pill ${badgeCls(item.action)}`}>
                    {item.action}
                  </span>
                </td>
                <td className="td font-mono text-xs">
                  {item.entity_type ?? "-"}
                  {item.entity_id ? ` · ${item.entity_id.slice(0, 8)}…` : ""}
                </td>
                <td className="td max-w-sm truncate text-xs" style={{ color: "var(--text-muted)" }}>
                  {item.detail ? JSON.stringify(item.detail) : "-"}
                </td>
                <td className="td font-mono text-xs">{item.ip ?? "-"}</td>
                <td className="td font-mono text-xs">
                  {item.user_id ? `${item.user_id.slice(0, 8)}…` : "-"}
                </td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="td py-8 text-center" style={{ color: "var(--text-muted)" }}>
                  Belum ada event audit.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
