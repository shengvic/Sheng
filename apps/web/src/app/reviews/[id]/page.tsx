"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ExportBar } from "@/components/ExportBar";
import { FindingCard, type Mode } from "@/components/FindingCard";
import { RedlineDiff } from "@/components/RedlineDiff";
import { ShortcutsHelp } from "@/components/ShortcutsHelp";
import { SourcesDrawer } from "@/components/SourcesDrawer";
import { StepProgress } from "@/components/StepProgress";
import { Button, Card, Chip, ErrorNote, SeverityBadge, Spinner, cx } from "@/components/ui";
import { t } from "@/i18n/en";
import { api } from "@/lib/api";
import {
  DEFAULT_FILTER,
  applyFilter,
  counts,
  humanize,
  isOpen,
  sortFindings,
  type FindingFilter,
} from "@/lib/findings";
import { saveBlob, usd } from "@/lib/format";
import { keyToAction, moveIndex } from "@/lib/keyboard";
import type { Clause, DispositionAction, Finding, ReasonCode } from "@/lib/types";

type Extra = { edited_text?: string; reason_code?: ReasonCode; note?: string };
type Undo = { findingId: string; label: string; restore: { action: DispositionAction } & Extra };

const TERMINAL = new Set(["completed", "failed"]);

function restoreFor(f: Finding): Undo["restore"] {
  switch (f.disposition) {
    case "accepted":
      return { action: "accept" };
    case "edited":
      return { action: "edit", edited_text: f.edited_text ?? "" };
    case "rejected":
      return { action: "reject", reason_code: (f.reason_code as ReasonCode) ?? "other", note: f.note ?? undefined };
    case "deferred":
      return { action: "defer" };
    default:
      return { action: "reset" };
  }
}

function DocumentPane({
  clauses,
  findings,
  selected,
  onSelectClause,
}: {
  clauses: Clause[];
  findings: Finding[];
  selected: Finding | undefined;
  onSelectClause: (clauseId: string) => void;
}) {
  const byClause = useMemo(() => {
    const m = new Map<string, Finding[]>();
    for (const f of findings) if (f.clause_id) m.set(f.clause_id, [...(m.get(f.clause_id) ?? []), f]);
    return m;
  }, [findings]);
  const missing = findings.filter((f) => f.classification === "missing");
  useEffect(() => {
    const id = selected?.clause_id ? `clause-${selected.clause_id}` : selected ? `missing-${selected.id}` : null;
    if (id) document.getElementById(id)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [selected]);

  return (
    <div className="space-y-1">
      {clauses.map((c) => {
        const fs = (byClause.get(c.id) ?? []).filter((f) => f.severity !== "info");
        const active = selected?.clause_id === c.id;
        const applied = fs.find(
          (f) => f.kind === "playbook" && (f.disposition === "accepted" || f.disposition === "edited"),
        );
        const newText = applied ? (applied.edited_text ?? applied.suggested_redline) : null;
        return (
          <section
            key={c.id}
            id={`clause-${c.id}`}
            onClick={() => fs[0] && onSelectClause(c.id)}
            className={cx(
              "rounded-md border-l-2 px-3 py-2",
              active ? "border-accent bg-accent-soft/60" : fs.length ? "border-medium/60" : "border-transparent",
              fs.length > 0 && "cursor-pointer hover:bg-surface-2",
            )}
          >
            {(c.number || c.heading) && (
              <h3 className="mb-0.5 flex items-center gap-2 text-sm font-semibold">
                <span>
                  {c.number ? `${c.number} ` : ""}
                  {c.heading}
                </span>
                {fs.map((f) => (
                  <SeverityBadge key={f.id} severity={f.severity} />
                ))}
              </h3>
            )}
            {newText ? (
              <RedlineDiff before={c.text} after={newText} />
            ) : (
              <p className="doc-text whitespace-pre-wrap">{c.text}</p>
            )}
          </section>
        );
      })}
      {missing.map((f) => {
        const text = f.disposition === "edited" ? f.edited_text : f.suggested_redline;
        return (
          <section
            key={f.id}
            id={`missing-${f.id}`}
            className={cx(
              "rounded-md border border-dashed px-3 py-2",
              selected?.id === f.id ? "border-accent bg-accent-soft/60" : "border-border",
            )}
          >
            <h3 className="mb-0.5 flex items-center gap-2 text-sm font-semibold text-muted">
              {t.review.missingClause}: {humanize(f.clause_key)} <SeverityBadge severity={f.severity} />
            </h3>
            {text && (f.disposition === "accepted" || f.disposition === "edited") ? (
              <RedlineDiff before="" after={text} />
            ) : (
              <p className="text-xs text-muted">Not in the contract.</p>
            )}
          </section>
        );
      })}
    </div>
  );
}

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const review = useQuery({
    queryKey: ["review", id],
    queryFn: () => api.review(id),
    refetchInterval: (q) => (q.state.data && TERMINAL.has(q.state.data.status) ? false : 2000),
  });
  const done = review.data?.status === "completed";
  const docId = review.data?.document_id;
  const doc = useQuery({ queryKey: ["document", docId], queryFn: () => api.document(docId!), enabled: !!docId });
  const clauses = useQuery({ queryKey: ["clauses", docId], queryFn: () => api.clauses(docId!), enabled: !!docId });
  const findings = useQuery({ queryKey: ["findings", id], queryFn: () => api.findings(id), enabled: done });
  const routing = useQuery({ queryKey: ["routing", id], queryFn: () => api.routing(id), enabled: done });
  const gate = useQuery({ queryKey: ["gate", id], queryFn: () => api.gate(id), enabled: done });
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });

  const [filter, setFilter] = useState<FindingFilter>(DEFAULT_FILTER);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("view");
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [help, setHelp] = useState(false);
  const [undo, setUndo] = useState<Undo | null>(null);
  const [lastExport, setLastExport] = useState<string | null>(null);
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clauseOrder = useMemo(
    () => new Map((clauses.data ?? []).map((c) => [c.id, c.idx] as const)),
    [clauses.data],
  );
  const all = useMemo(() => findings.data ?? [], [findings.data]);
  const visible = useMemo(
    () => sortFindings(applyFilter(all, filter), clauseOrder),
    [all, filter, clauseOrder],
  );
  const selectedIdx = visible.findIndex((f) => f.id === selectedId);
  const selected = selectedIdx >= 0 ? visible[selectedIdx] : undefined;
  const c = counts(all);

  useEffect(() => {
    if (!selectedId && visible.length) setSelectedId((visible.find(isOpen) ?? visible[0])!.id);
  }, [visible, selectedId]);

  const refreshGate = () => qc.invalidateQueries({ queryKey: ["gate", id] });

  const act = useMutation({
    mutationFn: ({ f, action, extra }: { f: Finding; action: DispositionAction; extra?: Extra; isUndo?: boolean }) =>
      api.disposition(f.id, { action, ...extra }),
    onSuccess: (updated, vars) => {
      qc.setQueryData<Finding[]>(["findings", id], (old) => old?.map((x) => (x.id === updated.id ? updated : x)));
      refreshGate();
      setMode("view");
      if (vars.isUndo) {
        setUndo(null);
        setSelectedId(updated.id);
        return;
      }
      if (undoTimer.current) clearTimeout(undoTimer.current);
      setUndo({ findingId: vars.f.id, label: `${humanize(vars.f.rule_key)}: ${vars.action}`, restore: restoreFor(vars.f) });
      undoTimer.current = setTimeout(() => setUndo(null), 10_000);
      // Advance to the next open finding in the current view.
      const after = visible.slice(selectedIdx + 1).find((x) => isOpen(x) && x.id !== vars.f.id);
      if (after) setSelectedId(after.id);
    },
  });

  const override = useMutation({
    mutationFn: ({ citationId, reason }: { citationId: string; reason: string }) =>
      api.overrideCitation(citationId, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["findings", id] });
      refreshGate();
    },
  });

  const exporter = useMutation({
    mutationFn: async (format: "redline_docx" | "memo_docx") => {
      const row = await api.createExport(id, format);
      saveBlob(await api.downloadExport(row.id), row.filename);
      return row.filename;
    },
    onSuccess: (name) => setLastExport(name),
    onError: () => refreshGate(),
  });

  const perform = useCallback(
    (f: Finding, action: DispositionAction, extra?: Extra) => act.mutate({ f, action, extra }),
    [act],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const a = keyToAction({
        key: e.key,
        ctrlKey: e.ctrlKey,
        metaKey: e.metaKey,
        altKey: e.altKey,
        targetTag: target?.tagName,
        targetEditable: target?.isContentEditable,
      });
      if (!a) return;
      if (a.type === "escape") {
        if (sourceId) setSourceId(null);
        else if (help) setHelp(false);
        else setMode("view");
        return;
      }
      if (a.type === "help") {
        setHelp((v) => !v);
        return;
      }
      if (help || mode !== "view") return;
      e.preventDefault();
      if (a.type === "move") {
        const next = moveIndex(selectedIdx, a.delta, visible.length);
        if (next >= 0) setSelectedId(visible[next]!.id);
        return;
      }
      if (!selected || act.isPending) return;
      if (a.type === "accept") perform(selected, "accept");
      if (a.type === "defer") perform(selected, "defer");
      if (a.type === "edit") setMode("edit");
      if (a.type === "reject") setMode("reject");
      if (a.type === "sources") {
        const first = selected.citations.find((x) => x.source_unit_id);
        if (first?.source_unit_id) setSourceId(first.source_unit_id);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible, selectedIdx, selected, mode, help, sourceId, act.isPending, perform]);

  if (review.isLoading) return <Spinner />;
  if (review.error) return <ErrorNote error={review.error} />;
  const r = review.data!;
  const canOverride = !!me.data && ["partner", "km", "admin"].includes(me.data.role);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0">
          <Link href={`/matters/${r.matter_id}`} className="text-sm text-muted hover:text-text">
            ← Matter
          </Link>
          <h1 className="mt-0.5 truncate text-lg font-semibold">{doc.data?.filename ?? "Review"}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
            <Chip>
              {r.playbook_key} v{r.playbook_version} · {r.playbook_source === "tenant" ? "firm playbook" : "starter"}
            </Chip>
            {doc.data?.contract_type && <Chip>{doc.data.contract_type}</Chip>}
            {doc.data?.governing_law && <Chip>{doc.data.governing_law} law</Chip>}
            <span>Model cost {usd(r.cost_usd)}</span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <StepProgress review={r} />
          <Button variant="ghost" size="sm" onClick={() => setHelp(true)} aria-label={t.review.shortcuts}>
            ?
          </Button>
        </div>
      </div>

      {r.status === "failed" && <ErrorNote error={`Review failed: ${r.error ?? "unknown error"}`} />}
      {!done && r.status !== "failed" && (
        <Card className="p-6">
          <Spinner label="Travo is reviewing the contract" />
        </Card>
      )}

      {done && (
        <>
          {r.summary.executive_summary && (
            <Card className="p-3 text-sm">
              <span className="font-medium">Summary. </span>
              {r.summary.executive_summary}
            </Card>
          )}
          <ExportBar
            gate={gate.data}
            findings={all}
            busy={exporter.isPending}
            onExport={(fmt) => exporter.mutate(fmt)}
            onJump={(fid) => {
              setFilter({ ...DEFAULT_FILTER, severity: "all" });
              setSelectedId(fid);
            }}
            lastExport={lastExport}
          />
          <ErrorNote error={exporter.error ?? act.error ?? override.error} />

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(380px,0.85fr)]">
            <Card className="max-h-[calc(100vh-15rem)] overflow-y-auto p-3">
              <h2 className="sr-only">{t.review.document}</h2>
              {clauses.data ? (
                <DocumentPane
                  clauses={clauses.data}
                  findings={all}
                  selected={selected}
                  onSelectClause={(cid) => {
                    const f = visible.find((x) => x.clause_id === cid) ?? all.find((x) => x.clause_id === cid);
                    if (f) setSelectedId(f.id);
                  }}
                />
              ) : (
                <Spinner />
              )}
            </Card>

            <section aria-label={t.review.findings} className="flex max-h-[calc(100vh-15rem)] flex-col gap-2">
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="font-semibold">
                  {c.open} open / {c.issues} issues
                </span>
                <Chip tone="bad">{c.bySeverity.high} high</Chip>
                <Chip tone="warn">{c.bySeverity.medium} medium</Chip>
                <Chip>{c.bySeverity.low} low</Chip>
                {c.needsHuman > 0 && <Chip tone="bad">{c.needsHuman} need lawyer</Chip>}
                <select
                  className="ml-auto h-7 rounded border border-border bg-surface px-1.5"
                  value={filter.severity}
                  onChange={(e) => setFilter({ ...filter, severity: e.target.value as FindingFilter["severity"] })}
                  aria-label="Severity filter"
                >
                  <option value="issues">Issues only</option>
                  <option value="all">All incl. standard</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <select
                  className="h-7 rounded border border-border bg-surface px-1.5"
                  value={filter.kind}
                  onChange={(e) => setFilter({ ...filter, kind: e.target.value as FindingFilter["kind"] })}
                  aria-label="Kind filter"
                >
                  <option value="all">Playbook + law</option>
                  <option value="playbook">Playbook</option>
                  <option value="law">Law</option>
                </select>
                <select
                  className="h-7 rounded border border-border bg-surface px-1.5"
                  value={filter.state}
                  onChange={(e) => setFilter({ ...filter, state: e.target.value as FindingFilter["state"] })}
                  aria-label="State filter"
                >
                  <option value="all">Any state</option>
                  <option value="open">Open</option>
                  <option value="done">Resolved</option>
                  <option value="needs_human">Needs lawyer</option>
                </select>
              </div>
              <div className="flex-1 space-y-2 overflow-y-auto pr-1" role="listbox" aria-label="Findings list">
                {findings.isLoading && <Spinner />}
                {visible.length === 0 && findings.data && (
                  <p className="p-3 text-sm text-muted">No findings match these filters.</p>
                )}
                {visible.map((f) => (
                  <FindingCard
                    key={f.id}
                    finding={f}
                    clause={clauses.data?.find((x) => x.id === f.clause_id)}
                    selected={f.id === selected?.id}
                    mode={f.id === selected?.id ? mode : "view"}
                    busy={act.isPending}
                    canOverride={canOverride}
                    routing={routing.data ?? []}
                    onSelect={() => {
                      setSelectedId(f.id);
                      setMode("view");
                    }}
                    onMode={(m) => {
                      setSelectedId(f.id);
                      setMode(m);
                    }}
                    onAct={(action, extra) => perform(f, action, extra)}
                    onOpenSource={setSourceId}
                    onOverride={(citationId, reason) => override.mutate({ citationId, reason })}
                  />
                ))}
              </div>
            </section>
          </div>
        </>
      )}

      {sourceId && <SourcesDrawer unitId={sourceId} onClose={() => setSourceId(null)} />}
      {help && <ShortcutsHelp onClose={() => setHelp(false)} />}
      {undo && (
        <div
          role="status"
          className="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-lg border border-border bg-surface px-4 py-2 text-sm shadow-lg"
        >
          <span>{undo.label}</span>
          <Button
            size="sm"
            onClick={() => {
              const f = all.find((x) => x.id === undo.findingId);
              if (f) {
                const { action, ...extra } = undo.restore;
                act.mutate({ f, action, extra, isUndo: true });
              }
            }}
          >
            {t.review.undo}
          </Button>
        </div>
      )}
    </div>
  );
}
