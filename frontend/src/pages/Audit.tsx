import { useState } from "react";
import { PageHeader } from "../components/notion";
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
  auth: "bg-slate-100 text-slate-600",
  cv: "bg-blue-100 text-blue-700",
  contract: "bg-indigo-100 text-indigo-700",
  employee_document: "bg-violet-100 text-violet-700",
  legal_document: "bg-cyan-100 text-cyan-700",
  esign: "bg-emerald-100 text-emerald-700",
};

function badgeCls(action: string): string {
  const prefix = action.split(".")[0];
  return ACTION_BADGES[prefix] ?? "bg-slate-100 text-slate-600";
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
        <PageHeader emoji="🛡️" title="Jejak Audit" />
        <span className="text-xs text-slate-400">
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
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Waktu</th>
              <th className="th">Aksi</th>
              <th className="th">Entitas</th>
              <th className="th">Detail</th>
              <th className="th">IP</th>
              <th className="th">User ID</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(data?.items ?? []).map((item) => (
              <tr key={item.id} className="hover:bg-slate-50">
                <td className="td whitespace-nowrap text-xs text-slate-500">
                  {new Date(item.created_at).toLocaleString("id-ID")}
                </td>
                <td className="td">
                  <span className={`badge border-0 ${badgeCls(item.action)}`}>
                    {item.action}
                  </span>
                </td>
                <td className="td font-mono text-xs">
                  {item.entity_type ?? "-"}
                  {item.entity_id ? ` · ${item.entity_id.slice(0, 8)}…` : ""}
                </td>
                <td className="td max-w-sm truncate text-xs text-slate-500">
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
                <td colSpan={6} className="td py-8 text-center text-slate-400">
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
