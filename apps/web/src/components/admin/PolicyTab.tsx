"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button, Card, Chip, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { usd } from "@/lib/format";
import { TASK_TYPES, type RoutingPlan } from "@/lib/types";

const humanReason = (r: string) => r.replace(/_/g, " ").replace(/^capability missing:/, "missing capability: ");

function PlanView({ plan }: { plan: RoutingPlan }) {
  return (
    <div className="grid gap-3 md:grid-cols-2" data-testid="dry-run-result">
      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
          Would try, in order (preferred tier {plan.preferred_tier})
        </h4>
        {plan.candidates.length === 0 ? (
          <p className="text-sm text-high">
            No permitted model{plan.budget_exceeded ? " (budget exceeded)" : ""} — findings would go to a lawyer.
          </p>
        ) : (
          <ol className="space-y-1 text-sm">
            {plan.candidates.map((c, i) => (
              <li key={c.endpoint_id} className="flex items-center gap-2">
                <span className="w-4 text-muted">{i + 1}.</span>
                <span className="font-mono">{c.endpoint_id}</span>
                <Chip>{c.tier}</Chip>
                <span className="ml-auto text-muted">{usd(c.est_cost_usd)}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Skipped</h4>
        <ul className="space-y-1 text-sm">
          {plan.filtered.map((f) => (
            <li key={f.endpoint_id} className="flex gap-2">
              <span className="font-mono">{f.endpoint_id}</span>
              <span className="text-muted">— {humanReason(f.reason)}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function PolicyTab() {
  const qc = useQueryClient();
  const policy = useQuery({ queryKey: ["admin", "policy"], queryFn: api.policy });
  const endpoints = useQuery({ queryKey: ["admin", "endpoints"], queryFn: api.endpoints });
  const [yaml, setYaml] = useState("");
  const [task, setTask] = useState<string>("law_check");
  const [escalate, setEscalate] = useState(false);
  useEffect(() => {
    if (policy.data) setYaml(policy.data.yaml);
  }, [policy.data]);
  const dirty = !!policy.data && yaml !== policy.data.yaml;

  const save = useMutation({
    mutationFn: () => api.savePolicy(yaml),
    onSuccess: (p) => qc.setQueryData(["admin", "policy"], p),
  });
  const dry = useMutation({
    mutationFn: () =>
      api.dryRun({ task_type: task, escalation_reason: escalate ? "admin_dry_run" : undefined, yaml: dirty ? yaml : undefined }),
  });

  if (policy.isLoading) return <Spinner />;
  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">Model policy</h3>
          <Chip>{policy.data?.source === "tenant" ? `Firm policy v${policy.data.version}` : "Travo default (not yet customised)"}</Chip>
          {dirty && <Chip tone="warn">Unsaved changes</Chip>}
        </div>
        <p className="text-sm text-muted">
          Which AI providers the firm allows, billing mode, default tiers per task and budgets. Matter-level
          conflict blocks are set on each matter and always apply on top.
        </p>
        <textarea
          aria-label="Model policy YAML"
          className={`${inputClass} h-72 w-full py-2 font-mono text-xs`}
          value={yaml}
          spellCheck={false}
          onChange={(e) => setYaml(e.target.value)}
        />
        <ErrorNote error={save.error} />
        <div className="flex gap-2">
          <Button variant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
            Save as new version
          </Button>
          <Button variant="ghost" disabled={!dirty} onClick={() => setYaml(policy.data?.yaml ?? "")}>
            Discard changes
          </Button>
        </div>
      </Card>

      <Card className="space-y-3 p-4">
        <h3 className="font-semibold">Test the policy</h3>
        <p className="text-sm text-muted">
          Shows which models a task would use{dirty ? " under your unsaved changes" : ""}, and why others are skipped.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Task">
            <select className={inputClass} value={task} onChange={(e) => setTask(e.target.value)} aria-label="Task">
              {TASK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </Field>
          <label className="flex h-9 items-center gap-2 text-sm">
            <input type="checkbox" checked={escalate} onChange={(e) => setEscalate(e.target.checked)} />
            Escalated (needs a stronger model)
          </label>
          <Button onClick={() => dry.mutate()} disabled={dry.isPending}>
            Run test
          </Button>
        </div>
        <ErrorNote error={dry.error} />
        {dry.data && <PlanView plan={dry.data} />}
      </Card>

      <Card className="p-4">
        <h3 className="mb-2 font-semibold">Model endpoints available to the router</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="py-1 pr-3 font-medium">Endpoint</th>
              <th className="py-1 pr-3 font-medium">Vendor</th>
              <th className="py-1 pr-3 font-medium">Via</th>
              <th className="py-1 pr-3 font-medium">Tier</th>
              <th className="py-1 pr-3 font-medium">Billing</th>
              <th className="py-1 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {endpoints.data?.map((e) => (
              <tr key={e.id} className="border-t border-border">
                <td className="py-1.5 pr-3 font-mono text-xs">{e.id}</td>
                <td className="py-1.5 pr-3">{e.provider}</td>
                <td className="py-1.5 pr-3 text-muted">{e.via ?? "direct"}</td>
                <td className="py-1.5 pr-3">{e.tier}</td>
                <td className="py-1.5 pr-3">{e.billing === "byo" ? "Firm's key" : e.billing === "proxy" ? "Travo proxy" : "Travo"}</td>
                <td className="py-1.5">{e.enabled ? <Chip tone="ok">available</Chip> : <Chip>not configured</Chip>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
