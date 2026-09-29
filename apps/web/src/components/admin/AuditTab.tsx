"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Card, Chip, ErrorNote, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { when } from "@/lib/format";

export function AuditTab() {
  const [action, setAction] = useState("");
  const audit = useQuery({
    queryKey: ["admin", "audit", action],
    queryFn: () => api.audit({ action: action || undefined }),
  });
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <input
          className={`${inputClass} w-72`}
          placeholder="Filter by action, e.g. auth.login"
          aria-label="Filter by action"
          value={action}
          onChange={(e) => setAction(e.target.value.trim())}
        />
        <span className="text-xs text-muted">Append-only; newest first.</span>
      </div>
      <ErrorNote error={audit.error} />
      <Card>
        <table className="w-full text-sm" data-testid="audit-table">
          <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">When</th>
              <th className="px-3 py-2 font-medium">Action</th>
              <th className="px-3 py-2 font-medium">Resource</th>
              <th className="px-3 py-2 font-medium">Result</th>
              <th className="px-3 py-2 font-medium">Details</th>
            </tr>
          </thead>
          <tbody>
            {audit.data?.map((e) => (
              <tr key={e.id} className="border-b border-border align-top last:border-0">
                <td className="whitespace-nowrap px-3 py-1.5 text-muted">{when(e.created_at)}</td>
                <td className="px-3 py-1.5 font-mono text-xs">{e.action}</td>
                <td className="px-3 py-1.5 text-xs">
                  {e.resource_type}
                  {e.resource_id ? ` · ${e.resource_id.slice(0, 12)}` : ""}
                </td>
                <td className="px-3 py-1.5">
                  <Chip tone={e.result === "ok" ? "ok" : "bad"}>{e.result}</Chip>
                </td>
                <td className="max-w-md truncate px-3 py-1.5 font-mono text-xs text-muted" title={JSON.stringify(e.details)}>
                  {Object.keys(e.details).length ? JSON.stringify(e.details) : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
