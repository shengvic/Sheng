"use client";

import type { Citation } from "@/lib/types";

import { cx } from "./ui";

const LABEL: Record<Citation["status"], string> = {
  supported: "Supported",
  partial: "Partly supported",
  contradicted: "Contradicted",
  not_found: "Not supported",
  uncited: "No citation",
  invalid_source: "Source not found",
  not_in_force: "Not in force",
  misquoted: "Misquoted",
};

export function citationTone(c: Citation): "ok" | "warn" | "bad" {
  if (c.status === "supported") return "ok";
  if (c.override_reason) return "warn";
  return c.status === "partial" ? "warn" : "bad";
}

export function CitationChip({ citation, onOpen }: { citation: Citation; onOpen: (unitId: string) => void }) {
  const tone = citationTone(citation);
  const icon = tone === "ok" ? "✓" : tone === "warn" ? "!" : "✕";
  const label = citation.override_reason ? `${LABEL[citation.status]} · overridden` : LABEL[citation.status];
  return (
    <button
      type="button"
      disabled={!citation.source_unit_id}
      onClick={() => citation.source_unit_id && onOpen(citation.source_unit_id)}
      title={`${label} (score ${citation.score.toFixed(2)}, checked by ${citation.checker})`}
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
      <span className="truncate">{citation.pinpoint ?? citation.source_unit_id ?? "No source"}</span>
      <span className="sr-only">— {label}</span>
    </button>
  );
}
