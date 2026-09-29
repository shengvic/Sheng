"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { usd } from "@/lib/format";
import type { SpendRow } from "@/lib/types";

import { BarList } from "./BarList";

// Bars measure model calls (always meaningful); cost is printed alongside, because Travo's own
// T0 model is free and a $0 bar chart would show nothing.
const toBars = (rows: SpendRow[], label: (k: string | null) => string) =>
  rows.map((r) => ({ label: label(r.key), value: r.calls, detail: `${usd(r.cost_usd)} spend` }));
const calls = (n: number) => `${n.toLocaleString()} call${n === 1 ? "" : "s"}`;

export function SpendTab() {
  const spend = useQuery({ queryKey: ["admin", "spend"], queryFn: api.spend });
  const matters = useQuery({ queryKey: ["matters"], queryFn: api.matters });
  if (spend.isLoading) return <Spinner />;
  if (spend.error) return <ErrorNote error={spend.error} />;
  const s = spend.data!;
  const total = s.by_task.reduce((a, r) => a + r.cost_usd, 0);
  const totalCalls = s.by_task.reduce((a, r) => a + r.calls, 0);
  const matterName = (id: string | null) =>
    !id ? "No matter" : (matters.data?.find((m) => m.id === id)?.number ?? `Matter ${id.slice(0, 8)} (walled)`);
  const tierShare = s.by_tier.reduce((acc, r) => ({ ...acc, [r.key ?? "none"]: r.calls }), {} as Record<string, number>);
  const frontierShare = totalCalls ? ((tierShare.T2 ?? 0) / totalCalls) * 100 : 0;
  return (
    <div className="space-y-4" data-testid="spend">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ["Model spend", usd(total)],
          ["Model calls", totalCalls.toLocaleString()],
          ["Frontier (T2) share of calls", `${frontierShare.toFixed(0)}%`],
        ].map(([k, v]) => (
          <Card key={k} className="p-4">
            <div className="text-xs uppercase tracking-wide text-muted">{k}</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums">{v}</div>
          </Card>
        ))}
      </div>
      <Card className="grid gap-6 p-4 lg:grid-cols-3">
        <BarList title="Model calls by task" bars={toBars(s.by_task, (k) => (k ?? "unknown").replace(/_/g, " "))} format={calls} />
        <BarList title="Model calls by tier" bars={toBars(s.by_tier, (k) => k ?? "no model")} format={calls} />
        <BarList title="Model calls by matter" bars={toBars(s.by_matter, matterName)} format={calls} />
      </Card>
      <p className="text-xs text-muted">
        Hover or focus a bar for its spend. Travo&apos;s own rules model (T0) costs nothing, so spend stays at $0.00 until
        paid model endpoints are configured. Matters you are not a member of appear by id only.
      </p>
    </div>
  );
}
