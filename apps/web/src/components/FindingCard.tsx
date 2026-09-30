"use client";

import { useEffect, useRef, useState } from "react";

import { REASON_LABEL, t } from "@/i18n/en";
import { DISPOSITION_LABEL, humanize, splitCites } from "@/lib/findings";
import { pct } from "@/lib/format";
import type { Clause, DispositionAction, Finding, ReasonCode, RoutingRow } from "@/lib/types";

import { CitationChip } from "./CitationChip";
import { ReasonMenu } from "./ReasonMenu";
import { RedlineDiff } from "./RedlineDiff";
import { WhyModel } from "./WhyModel";
import { Button, Chip, SeverityBadge, cx, inputClass } from "./ui";

export type Mode = "view" | "edit" | "reject";

const CLASS_LABEL: Record<Finding["classification"], string> = {
  standard: "Standard",
  fallback: "Fallback",
  non_standard: "Non-standard",
  missing: "Missing",
  legal_note: "Legal note",
  discrepancy: "VI/EN mismatch",
};

export interface FindingCardProps {
  finding: Finding;
  clause: Clause | undefined;
  selected: boolean;
  mode: Mode;
  busy: boolean;
  canOverride: boolean;
  routing: RoutingRow[];
  onSelect: () => void;
  onMode: (m: Mode) => void;
  onAct: (action: DispositionAction, extra?: { edited_text?: string; reason_code?: ReasonCode; note?: string }) => void;
  onOpenSource: (unitId: string) => void;
  onOverride: (citationId: string, reason: string) => void;
}

function NoteText({ text, onOpenSource }: { text: string; onOpenSource: (id: string) => void }) {
  return (
    <p className="text-sm">
      {splitCites(text).map((p, i) =>
        p.cite ? (
          <button
            key={i}
            type="button"
            onClick={() => onOpenSource(p.cite!)}
            className="mx-0.5 rounded bg-accent-soft px-1 align-baseline text-[11px] font-medium text-accent hover:underline"
            title={p.cite}
          >
            [source]
          </button>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </p>
  );
}

export function FindingCard(props: FindingCardProps) {
  const { finding: f, clause, selected, mode, busy } = props;
  const ref = useRef<HTMLElement>(null);
  const redline = f.edited_text ?? f.suggested_redline ?? "";
  const [draft, setDraft] = useState(redline);
  const [whyOpen, setWhyOpen] = useState(false);
  const [overriding, setOverriding] = useState<string | null>(null);
  const [overrideText, setOverrideText] = useState("");

  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selected]);
  useEffect(() => {
    if (mode === "edit") setDraft(f.edited_text ?? f.suggested_redline ?? clause?.text ?? "");
  }, [mode, f.edited_text, f.suggested_redline, clause?.text]);

  const done = f.disposition && f.disposition !== "deferred";
  return (
    <article
      ref={ref}
      id={`finding-${f.id}`}
      data-testid="finding-card"
      data-rule={f.rule_key}
      data-disposition={f.disposition ?? ""}
      aria-selected={selected}
      onClick={props.onSelect}
      className={cx(
        "cursor-pointer rounded-lg border bg-surface p-3 transition-shadow",
        selected ? "border-accent shadow-[0_0_0_1px_var(--accent)]" : "border-border hover:border-muted",
        done && !selected && "opacity-70",
      )}
    >
      <header className="flex flex-wrap items-center gap-1.5">
        <SeverityBadge severity={f.severity} />
        <span className="font-medium">{humanize(f.rule_key)}</span>
        <Chip>{CLASS_LABEL[f.classification]}</Chip>
        {f.kind === "law" && <Chip tone="accent">Law</Chip>}
        {f.status === "needs_human" && (
          <Chip tone="bad" title="No permitted model produced a validated answer">
            Needs lawyer
          </Chip>
        )}
        {f.disposition && (
          <Chip tone={f.disposition === "rejected" ? "bad" : f.disposition === "deferred" ? "warn" : "ok"}>
            {DISPOSITION_LABEL[f.disposition]}
            {f.reason_code ? ` · ${REASON_LABEL[f.reason_code] ?? f.reason_code}` : ""}
          </Chip>
        )}
      </header>

      <div className="mt-2 space-y-2">
        {f.kind === "law" ? <NoteText text={f.summary} onOpenSource={props.onOpenSource} /> : <p className="text-sm">{f.summary}</p>}
        {f.rationale && <p className="text-xs text-muted">{f.rationale}</p>}

        {f.citations.length > 0 && (
          <div className="space-y-1">
            {f.citations.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center gap-1.5">
                <CitationChip citation={c} onOpen={props.onOpenSource} />
                {c.status !== "supported" && !c.override_reason && props.canOverride && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOverriding(c.id);
                    }}
                  >
                    {t.review.override}
                  </Button>
                )}
                {overriding === c.id && (
                  <form
                    className="flex w-full gap-1.5"
                    onClick={(e) => e.stopPropagation()}
                    onSubmit={(e) => {
                      e.preventDefault();
                      props.onOverride(c.id, overrideText);
                      setOverriding(null);
                      setOverrideText("");
                    }}
                  >
                    <input
                      className={`${inputClass} flex-1`}
                      value={overrideText}
                      minLength={10}
                      required
                      placeholder={t.review.overrideReason}
                      aria-label={t.review.overrideReason}
                      onChange={(e) => setOverrideText(e.target.value)}
                    />
                    <Button size="sm" type="submit">
                      Save
                    </Button>
                  </form>
                )}
              </div>
            ))}
          </div>
        )}

        {f.kind === "playbook" && redline && mode !== "edit" && (
          <div className="rounded-md border border-border bg-surface-2 p-2">
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">
              {f.edited_text ? "Your wording" : "Suggested redline"}
            </div>
            <RedlineDiff before={clause?.text ?? ""} after={redline} />
          </div>
        )}

        {mode === "edit" && (
          <form
            className="space-y-2"
            onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => {
              e.preventDefault();
              props.onAct("edit", { edited_text: draft });
            }}
          >
            <textarea
              className={`${inputClass} doc-text h-32 w-full py-2`}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="Edit wording"
              autoFocus
            />
            <div className="flex gap-2">
              <Button size="sm" variant="primary" type="submit" disabled={busy || !draft.trim()}>
                {t.review.save}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => props.onMode("view")}>
                {t.review.cancel}
              </Button>
            </div>
          </form>
        )}

        {mode === "reject" && (
          <div onClick={(e) => e.stopPropagation()}>
            <ReasonMenu
              onSubmit={(reason_code, note) => props.onAct("reject", { reason_code, note: note || undefined })}
              onCancel={() => props.onMode("view")}
            />
          </div>
        )}
      </div>

      <footer className="mt-3 flex flex-wrap items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
        {mode === "view" && (
          <>
            <Button size="sm" variant="primary" disabled={busy} onClick={() => props.onAct("accept")}>
              {t.review.accept} <kbd className="opacity-70">A</kbd>
            </Button>
            <Button size="sm" disabled={busy} onClick={() => props.onMode("edit")}>
              {t.review.edit} <kbd className="opacity-70">E</kbd>
            </Button>
            <Button size="sm" disabled={busy} onClick={() => props.onMode("reject")}>
              {t.review.reject} <kbd className="opacity-70">R</kbd>
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => props.onAct("defer")}>
              {t.review.defer} <kbd className="opacity-70">D</kbd>
            </Button>
          </>
        )}
        <span className="ml-auto flex items-center gap-1.5 text-[11px] text-muted">
          <span title="Model confidence">{pct(f.confidence)}</span>
          {f.model_tier && <Chip>{f.model_tier}</Chip>}
          {f.escalated && <Chip tone="warn">escalated</Chip>}
          <button
            type="button"
            className="text-accent hover:underline"
            aria-expanded={whyOpen}
            onClick={() => setWhyOpen((v) => !v)}
          >
            {t.review.why}
          </button>
        </span>
      </footer>
      {whyOpen && (
        <div className="mt-2" onClick={(e) => e.stopPropagation()}>
          <WhyModel finding={f} routing={props.routing} />
        </div>
      )}
    </article>
  );
}
