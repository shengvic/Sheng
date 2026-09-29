"use client";

import type { Review } from "@/lib/types";

import { cx } from "./ui";

const ALL_STEPS = ["prepare", "compare", "lawcheck", "redline", "memo"];
const LABEL: Record<string, string> = {
  prepare: "Prepare",
  compare: "Playbook",
  lawcheck: "Law check",
  redline: "Redlines",
  memo: "Memo",
};

export function StepProgress({ review }: { review: Review }) {
  const byName = new Map(review.steps.map((s) => [s.name, s]));
  return (
    <ol className="flex items-center gap-1" aria-label="Review progress">
      {ALL_STEPS.map((name, i) => {
        const s = byName.get(name);
        const state = s?.status === "completed" ? "done" : s?.status === "failed" ? "failed" : "todo";
        const active = state === "todo" && review.status === "running" && ALL_STEPS.slice(0, i).every((n) => byName.get(n)?.status === "completed");
        return (
          <li key={name} className="flex items-center gap-1">
            <span
              className={cx(
                "inline-flex h-6 items-center gap-1 rounded-full px-2 text-xs",
                state === "done" && "bg-ok-soft text-ok",
                state === "failed" && "bg-high-soft text-high",
                state === "todo" && (active ? "bg-accent-soft text-accent" : "bg-surface-2 text-muted"),
              )}
              title={s?.error ?? undefined}
            >
              {state === "done" ? "✓" : state === "failed" ? "✕" : active ? "…" : "○"} {LABEL[name]}
            </span>
            {i < ALL_STEPS.length - 1 && <span className="h-px w-3 bg-border" aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}
