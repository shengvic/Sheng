"use client";

import type { Finding, RoutingRow } from "@/lib/types";
import { usd } from "@/lib/format";

import { Chip } from "./ui";

const TASKS: Record<Finding["kind"], string[]> = {
  playbook: ["playbook_compare", "redline"],
  law: ["law_check", "validate_claim"],
};

export function WhyModel({ finding, routing }: { finding: Finding; routing: RoutingRow[] }) {
  const rows = routing.filter((r) => TASKS[finding.kind].includes(r.task_type));
  if (!rows.length) return <p className="text-xs text-muted">No routing records for this finding.</p>;
  return (
    <div className="space-y-2 text-xs" data-testid="why-model">
      {rows.map((r) => (
        <div key={r.id} className="rounded-md border border-border p-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium">{r.task_type.replace("_", " ")}</span>
            <span aria-hidden>→</span>
            <span className="font-mono">{r.chosen_endpoint ?? "none"}</span>
            {r.chosen_tier && <Chip>{r.chosen_tier}</Chip>}
            {r.escalation_reason && <Chip tone="warn">escalated: {r.escalation_reason.replace(/_/g, " ")}</Chip>}
            {r.outcome !== "ok" && <Chip tone="bad">{r.outcome.replace("_", " ")}</Chip>}
            <span className="ml-auto text-muted">
              {usd(r.cost_usd)} · {r.latency_ms} ms
            </span>
          </div>
          {r.filtered.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-muted">
              {r.filtered.map((f) => (
                <li key={f.endpoint_id}>
                  <span className="font-mono">{f.endpoint_id}</span> skipped — {f.reason.replace(/_/g, " ")}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
