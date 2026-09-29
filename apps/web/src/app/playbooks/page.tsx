"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Card, Chip, ErrorNote, SeverityBadge, Spinner, cx } from "@/components/ui";
import { t } from "@/i18n/en";
import { api } from "@/lib/api";
import { humanize } from "@/lib/findings";
import type { PlaybookRule } from "@/lib/types";

function checks(r: PlaybookRule): string[] {
  const out: string[] = [];
  if (r.min_duration_months) out.push(`≥ ${r.min_duration_months} months`);
  if (r.fallback_min_duration_months) out.push(`fallback ≥ ${r.fallback_min_duration_months} months`);
  if (r.max_duration_months) out.push(`≤ ${r.max_duration_months} months`);
  if (r.min_amount != null) out.push(`amount ≥ ${r.min_amount.toLocaleString()}`);
  if (r.max_amount != null) out.push(`amount ≤ ${r.max_amount.toLocaleString()}`);
  if (r.must_include_any?.length) out.push(`mentions ${r.must_include_any.join(" / ")}`);
  if (r.must_not_include_any?.length) out.push(`never “${r.must_not_include_any.join("”, “")}”`);
  return out;
}

export default function PlaybooksPage() {
  const list = useQuery({ queryKey: ["playbooks"], queryFn: api.playbooks });
  const [key, setKey] = useState<string | null>(null);
  const active = key ?? list.data?.[0]?.key ?? null;
  const detail = useQuery({
    queryKey: ["playbook", active],
    queryFn: () => api.playbook(active!),
    enabled: !!active,
  });
  return (
    <div className="mx-auto grid max-w-6xl gap-4 md:grid-cols-[260px_1fr]">
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">{t.nav.playbooks}</h1>
        {list.isLoading && <Spinner />}
        <ErrorNote error={list.error} />
        <ul className="space-y-1">
          {list.data?.map((p) => (
            <li key={`${p.source}:${p.key}`}>
              <button
                type="button"
                onClick={() => setKey(p.key)}
                className={cx(
                  "w-full rounded-md border px-3 py-2 text-left text-sm",
                  active === p.key ? "border-accent bg-accent-soft" : "border-border bg-surface hover:bg-surface-2",
                )}
              >
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted">
                  {p.source === "tenant" ? `Firm · v${p.version}` : "Travo starter"} · {p.rules} rules ·{" "}
                  {p.governing_laws.join(", ")}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <Card className="p-4">
        {detail.isLoading && <Spinner />}
        {detail.data?.spec && (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold">{detail.data.name}</h2>
              <Chip>{detail.data.contract_types.join(", ")}</Chip>
              <Chip>{detail.data.governing_laws.join(", ")} law</Chip>
            </div>
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="py-2 pr-3 font-medium">Clause</th>
                  <th className="py-2 pr-3 font-medium">Firm position</th>
                  <th className="py-2 pr-3 font-medium">Checks</th>
                  <th className="py-2 font-medium">If breached</th>
                </tr>
              </thead>
              <tbody>
                {detail.data.spec.rules.map((r) => (
                  <tr key={r.key} className="border-b border-border align-top last:border-0">
                    <td className="py-2 pr-3">
                      <div className="font-medium">{humanize(r.clause_key)}</div>
                      {r.required && <span className="text-xs text-muted">Required</span>}
                    </td>
                    <td className="py-2 pr-3">
                      <div>{r.standard}</div>
                      {r.rationale && <div className="mt-0.5 text-xs text-muted">{r.rationale}</div>}
                    </td>
                    <td className="py-2 pr-3 text-xs">{checks(r).join(" · ") || "—"}</td>
                    <td className="py-2">
                      <SeverityBadge severity={r.severity ?? "medium"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>
    </div>
  );
}
