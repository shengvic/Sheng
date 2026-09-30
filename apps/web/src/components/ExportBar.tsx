"use client";

import { findingTitle, useT } from "@/i18n/context";
import type { ExportGate, Finding } from "@/lib/types";

import { Button, Chip } from "./ui";

export function ExportBar({
  gate,
  findings,
  busy,
  onExport,
  onJump,
  lastExport,
}: {
  gate: ExportGate | undefined;
  findings: Finding[];
  busy: boolean;
  onExport: (format: "redline_docx" | "memo_docx") => void;
  onJump: (findingId: string) => void;
  lastExport: string | null;
}) {
  const t = useT();
  if (!gate) return null;
  const byId = new Map(findings.map((f) => [f.id, f]));
  return (
    <section className="rounded-lg border border-border bg-surface p-3" aria-label={t.review.export} data-testid="export-bar">
      <div className="flex flex-wrap items-center gap-2">
        {gate.open ? (
          <Chip tone="ok">{t.review.gateOpen}</Chip>
        ) : (
          <span className="text-sm font-medium">
            {t.review.gateBlocked} <span className="text-muted">({gate.blocking.length})</span>
          </span>
        )}
        <div className="ml-auto flex gap-2">
          <Button variant="primary" size="sm" disabled={!gate.open || busy} onClick={() => onExport("redline_docx")}>
            {t.review.exportRedline}
          </Button>
          <Button size="sm" disabled={!gate.open || busy} onClick={() => onExport("memo_docx")}>
            {t.review.exportMemo}
          </Button>
        </div>
      </div>
      {!gate.open && (
        <ul className="mt-2 flex max-h-28 flex-wrap gap-1.5 overflow-y-auto">
          {gate.blocking.map((b, i) => {
            const f = b.finding_id ? byId.get(b.finding_id) : undefined;
            const name = f ? findingTitle(t, f) : t.review.finding;
            const label =
              b.type === "citation_unsupported"
                ? t.review.gateCitation(t.citation[b.status ?? ""] ?? b.status ?? "", name)
                : b.type === "review_not_completed"
                  ? t.review.gateReview(t.matter.status[b.status ?? ""] ?? b.status ?? "")
                  : name;
            return (
              <li key={i}>
                <button
                  type="button"
                  className="rounded-full border border-border px-2 py-0.5 text-xs hover:border-accent hover:text-accent"
                  onClick={() => b.finding_id && onJump(b.finding_id)}
                >
                  {label}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {lastExport && <p className="mt-2 text-xs text-muted">{t.review.downloaded(lastExport)}</p>}
    </section>
  );
}
