"use client";

import { wordDiff } from "@/lib/diff";

export function RedlineDiff({ before, after }: { before: string; after: string }) {
  const parts = wordDiff(before, after);
  return (
    <p className="doc-text whitespace-pre-wrap text-[13px]">
      {parts.map((p, i) =>
        p.op === "eq" ? (
          <span key={i}>{p.text}</span>
        ) : p.op === "ins" ? (
          <ins key={i} className="redline">
            {p.text}
          </ins>
        ) : (
          <del key={i} className="redline">
            {p.text}
          </del>
        ),
      )}
    </p>
  );
}
