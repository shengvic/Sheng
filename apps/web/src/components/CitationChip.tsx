"use client";

import { useT } from "@/i18n/context";
import type { Citation } from "@/lib/types";

import { cx } from "./ui";


export function citationTone(c: Citation): "ok" | "warn" | "bad" {
  if (c.status === "supported") return "ok";
  if (c.override_reason) return "warn";
  return c.status === "partial" ? "warn" : "bad";
}

export function CitationChip({ citation, onOpen }: { citation: Citation; onOpen: (unitId: string) => void }) {
  const t = useT();
  const tone = citationTone(citation);
  const icon = tone === "ok" ? "✓" : tone === "warn" ? "!" : "✕";
  const base = t.citation[citation.status] ?? citation.status;
  const label = citation.override_reason ? `${base} · ${t.citation.overridden}` : base;
  return (
    <button
      type="button"
      disabled={!citation.source_unit_id}
      onClick={() => citation.source_unit_id && onOpen(citation.source_unit_id)}
      title={t.citationTooltip(label, citation.score.toFixed(2), citation.checker)}
      className={cx(
        "inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-left text-[11px] font-medium",
        tone === "ok" && "border-ok/40 bg-ok-soft text-ok",
        tone === "warn" && "border-medium/40 bg-medium-soft text-medium",
        tone === "bad" && "border-high/40 bg-high-soft text-high",
        citation.source_unit_id && "hover:underline",
      )}
      data-testid="citation-chip"
    >
      <span aria-hidden>{icon}</span>
      <span className="truncate">{citation.pinpoint ?? citation.source_unit_id ?? t.citation.noSource}</span>
      <span className="sr-only">— {label}</span>
    </button>
  );
}
