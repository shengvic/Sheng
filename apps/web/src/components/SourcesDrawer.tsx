"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { t } from "@/i18n/en";
import { api } from "@/lib/api";

import { Button, Chip, ErrorNote, Spinner } from "./ui";

export function SourcesDrawer({ unitId, onClose }: { unitId: string; onClose: () => void }) {
  const unit = useQuery({ queryKey: ["legal-unit", unitId], queryFn: () => api.legalUnit(unitId) });
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => closeRef.current?.focus(), []);
  const u = unit.data;
  return (
    <aside
      role="dialog"
      aria-modal="false"
      aria-label={t.review.sources}
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l border-border bg-surface shadow-xl"
      data-testid="sources-drawer"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-semibold">{t.review.sources}</h2>
        <Button ref={closeRef} variant="ghost" size="sm" onClick={onClose} aria-label="Close sources">
          ✕
        </Button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {unit.isLoading && <Spinner />}
        <ErrorNote error={unit.error} />
        {u && (
          <>
            {u.is_fixture && (
              <p className="rounded-md border border-medium/40 bg-medium-soft px-3 py-2 text-xs font-medium text-medium">
                {t.review.fixture}
              </p>
            )}
            <div>
              <div className="text-xs uppercase tracking-wide text-muted">{u.jurisdiction}</div>
              <div className="font-medium">{u.source_title}</div>
              <div className="text-sm">
                {u.unit_path}
                {u.heading ? ` — ${u.heading}` : ""}
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Chip tone={u.status === "in_force" ? "ok" : "bad"}>{u.status.replace("_", " ")}</Chip>
              {u.effective_from && <Chip>from {u.effective_from}</Chip>}
              {u.effective_to && <Chip>to {u.effective_to}</Chip>}
            </div>
            <blockquote className="doc-text border-l-2 border-accent pl-3">{u.text}</blockquote>
            {u.official_url && (
              <a className="text-sm text-accent hover:underline" href={u.official_url} target="_blank" rel="noreferrer">
                Official source ↗
              </a>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
