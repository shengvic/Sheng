"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { useT } from "@/i18n/context";
import { api } from "@/lib/api";

import { Button, Chip, ErrorNote, Spinner } from "./ui";

export function SourcesDrawer({ unitId, onClose }: { unitId: string; onClose: () => void }) {
  const t = useT();
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
        <Button ref={closeRef} variant="ghost" size="sm" onClick={onClose} aria-label={t.review.closeSources}>
          ✕
        </Button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {unit.isLoading && <Spinner />}
        <ErrorNote error={unit.error} />
        {u && (
          <>
            {u.is_fixture ? (
              <p className="rounded-md border border-medium/40 bg-medium-soft px-3 py-2 text-xs font-medium text-medium">
                {t.review.fixture}
              </p>
            ) : (
              u.review_status !== "verified" && (
                <p
                  className="rounded-md border border-medium/40 bg-medium-soft px-3 py-2 text-xs font-medium text-medium"
                  data-testid="unverified-source"
                >
                  {t.review.unverified}
                </p>
              )
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
              <Chip tone={u.status === "in_force" ? "ok" : "bad"}>{t.review.unitStatus[u.status] ?? u.status}</Chip>
              {u.effective_from && <Chip>{t.review.from(u.effective_from)}</Chip>}
              {u.effective_to && <Chip>{t.review.to(u.effective_to)}</Chip>}
              {u.review_status === "verified" && <Chip tone="ok">{t.review.verified}</Chip>}
              {u.retrieved_at && <Chip>{t.review.retrieved(u.retrieved_at.slice(0, 10))}</Chip>}
            </div>
            <blockquote className="doc-text whitespace-pre-wrap border-l-2 border-accent pl-3" lang={u.jurisdiction === "VN" ? "vi" : undefined}>
              {u.text}
            </blockquote>
            {!u.is_fixture && u.issuing_body && (
              <p className="text-xs text-muted" data-testid="source-attribution">
                {t.review.sourceBy} {u.issuing_body}
              </p>
            )}
            {u.official_url?.startsWith("https://") && (
              <a className="text-sm text-accent hover:underline" href={u.official_url} target="_blank" rel="noreferrer">
                {t.review.officialSource}
              </a>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
