"use client";

import { useEffect, useRef, useState } from "react";

import { findingTitle, useT } from "@/i18n/context";
import { splitCites } from "@/lib/findings";
import { pct } from "@/lib/format";
import type { Clause, DispositionAction, Finding, ReasonCode, RoutingRow } from "@/lib/types";

import { CitationChip } from "./CitationChip";
import { ReasonMenu } from "./ReasonMenu";
import { RedlineDiff } from "./RedlineDiff";
import { WhyModel } from "./WhyModel";
import { Button, Chip, SeverityBadge, cx, inputClass } from "./ui";

export type Mode = "view" | "edit" | "reject";

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
  const t = useT();
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
            {t.review.sourceLink}
          </button>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </p>
  );
}

/** Both language versions of a VI/EN discrepancy, with the prevailing language. */
function BilingualEvidence({ finding: f }: { finding: Finding }) {
  const t = useT();
  const ev = f.evidence;
  if (!ev) return null;
  const [a, b] = ev.languages;
  const name = (l: string | undefined) => (l ? (t.languageName[l] ?? l) : "");
  return (
    <div className="space-y-1.5" data-testid="bilingual-evidence">
      {(ev.primary_span || ev.other_span) && (
        <div className="grid gap-1.5 sm:grid-cols-2">
          {[
            [a, ev.primary_span],
            [b, ev.other_span],
          ].map(([lang, span]) => (
            <div key={lang} lang={lang} className="rounded-md border border-border bg-surface-2 p-2">
              <div className="mb-0.5 text-[11px] font-medium uppercase tracking-wide text-muted">
                {t.review.versionOf(name(lang))}
              </div>
              <p className="doc-text text-sm">{span || "—"}</p>
            </div>
          ))}
        </div>
      )}
      <Chip tone={ev.prevailing ? "neutral" : "warn"}>
        {ev.prevailing ? t.review.prevails(name(ev.prevailing)) : t.review.noPrevailing}
      </Chip>
    </div>
  );
}

export function FindingCard(props: FindingCardProps) {
  const t = useT();
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
        <span className="font-medium">{findingTitle(t, f)}</span>
        <Chip>{t.classes[f.classification] ?? f.classification}</Chip>
        {f.kind === "law" && <Chip tone="accent">{t.review.lawChip}</Chip>}
        {f.kind === "bilingual" && <Chip tone="accent">{t.review.bilingualChip}</Chip>}
        {f.status === "needs_human" && (
          <Chip tone="bad" title={t.review.needsLawyerTitle}>
            {t.review.needsLawyer}
          </Chip>
        )}
        {f.disposition && (
          <Chip tone={f.disposition === "rejected" ? "bad" : f.disposition === "deferred" ? "warn" : "ok"}>
            {t.dispositions[f.disposition]}
            {f.reason_code ? ` · ${t.reasons[f.reason_code] ?? f.reason_code}` : ""}
          </Chip>
        )}
      </header>

      <div className="mt-2 space-y-2">
        {f.kind === "law" ? <NoteText text={f.summary} onOpenSource={props.onOpenSource} /> : <p className="text-sm">{f.summary}</p>}
        {f.kind === "bilingual" && <BilingualEvidence finding={f} />}
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
                      {t.review.save}
                    </Button>
                  </form>
                )}
              </div>
            ))}
          </div>
        )}

        {f.kind === "playbook" && redline && mode !== "edit" && (
          <div className="rounded-md border border-border bg-surface-2 p-2" lang={clause?.lang ?? undefined}>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">
              {f.edited_text ? t.review.yourWording : t.review.suggestedRedline}
            </div>
            <RedlineDiff before={clause?.text ?? ""} after={redline} />
          </div>
        )}
        {f.kind === "playbook" && !f.edited_text && f.suggested_redline_alt && mode !== "edit" && (
          <div className="rounded-md border border-border bg-surface-2 p-2" lang={clause?.lang_alt ?? undefined}>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">
              {t.review.suggestedIn(t.languageName[clause?.lang_alt ?? "en"] ?? "")}
            </div>
            <RedlineDiff before={clause?.text_alt ?? ""} after={f.suggested_redline_alt} />
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
              aria-label={t.review.editWording}
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
          <span title={t.review.confidence}>{pct(f.confidence)}</span>
          {f.model_tier && <Chip>{f.model_tier}</Chip>}
          {f.escalated && <Chip tone="warn">{t.review.escalated}</Chip>}
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
