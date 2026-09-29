"use client";

import { useState } from "react";

export interface Bar {
  label: string;
  value: number;
  detail?: string;
}

/** Horizontal bar list for one measure (single hue, no legend: the title names it). Values are
 * printed as text so the list doubles as the table view; hover/focus shows the detail. */
export function BarList({ title, bars, format }: { title: string; bars: Bar[]; format: (n: number) => string }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...bars.map((b) => b.value), 0);
  const sorted = [...bars].sort((a, b) => b.value - a.value);
  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-semibold">{title}</figcaption>
      {sorted.length === 0 && <p className="text-sm text-muted">No usage yet.</p>}
      <ul className="space-y-1.5" role="list">
        {sorted.map((b, i) => (
          <li
            key={b.label}
            className="relative grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(i)}
            onBlur={() => setHover(null)}
            tabIndex={0}
            aria-label={`${b.label}: ${format(b.value)}${b.detail ? `, ${b.detail}` : ""}`}
          >
            <span className="truncate text-muted" title={b.label}>
              {b.label}
            </span>
            <span className="h-3.5">
              {/* Square at the baseline, 4px rounded data end; never wider than its share. */}
              <span
                className="block h-full rounded-r-[4px] bg-data-1"
                style={{ width: max > 0 ? `${Math.max((b.value / max) * 100, b.value > 0 ? 1 : 0)}%` : "0%" }}
              />
            </span>
            <span className="tabular-nums">{format(b.value)}</span>
            {hover === i && b.detail && (
              <span
                role="tooltip"
                className="pointer-events-none absolute -top-7 left-40 z-10 rounded-md border border-border bg-surface px-2 py-0.5 text-xs shadow"
              >
                {b.label} · {format(b.value)} · {b.detail}
              </span>
            )}
          </li>
        ))}
      </ul>
    </figure>
  );
}
