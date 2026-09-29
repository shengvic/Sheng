import type { Disposition, Finding, Severity } from "./types";

export const SEVERITY_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2, info: 3 };

export interface FindingFilter {
  severity: Severity | "all" | "issues";
  kind: Finding["kind"] | "all";
  state: "all" | "open" | "done" | "needs_human";
}

export const DEFAULT_FILTER: FindingFilter = { severity: "issues", kind: "all", state: "all" };

/** A finding is "open" when it still blocks export (docs/05 §7, ADR-016). */
export function isOpen(f: Finding): boolean {
  return f.severity !== "info" && (f.disposition === null || f.disposition === "deferred");
}

export function hasUnsupportedCitation(f: Finding): boolean {
  return (
    f.disposition !== "rejected" &&
    f.citations.some((c) => c.status !== "supported" && !c.override_reason)
  );
}

export function applyFilter(findings: Finding[], filter: FindingFilter): Finding[] {
  return findings.filter((f) => {
    if (filter.severity === "issues" && f.severity === "info") return false;
    if (filter.severity !== "all" && filter.severity !== "issues" && f.severity !== filter.severity)
      return false;
    if (filter.kind !== "all" && f.kind !== filter.kind) return false;
    if (filter.state === "open" && !isOpen(f)) return false;
    if (filter.state === "done" && isOpen(f)) return false;
    if (filter.state === "needs_human" && f.status !== "needs_human") return false;
    return true;
  });
}

/** Stable review order: severity, then document position (missing clauses last), then rule. */
export function sortFindings(findings: Finding[], clauseOrder: Map<string, number>): Finding[] {
  return [...findings].sort((a, b) => {
    const s = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
    if (s) return s;
    const pa = a.clause_id ? (clauseOrder.get(a.clause_id) ?? 9999) : 10_000;
    const pb = b.clause_id ? (clauseOrder.get(b.clause_id) ?? 9999) : 10_000;
    if (pa !== pb) return pa - pb;
    return a.rule_key.localeCompare(b.rule_key);
  });
}

export function counts(findings: Finding[]) {
  const issues = findings.filter((f) => f.severity !== "info");
  return {
    total: findings.length,
    issues: issues.length,
    open: issues.filter(isOpen).length,
    needsHuman: findings.filter((f) => f.status === "needs_human").length,
    bySeverity: {
      high: issues.filter((f) => f.severity === "high").length,
      medium: issues.filter((f) => f.severity === "medium").length,
      low: issues.filter((f) => f.severity === "low").length,
    },
  };
}

export const DISPOSITION_LABEL: Record<Disposition, string> = {
  accepted: "Accepted",
  edited: "Edited",
  rejected: "Rejected",
  deferred: "Deferred",
};

/** Split law notes into readable text and cite markers ([[src:ID]]). */
export function splitCites(text: string): { text: string; cite?: string }[] {
  const out: { text: string; cite?: string }[] = [];
  const re = /\[\[src:([^\]]+)\]\]/g;
  let last = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) });
    out.push({ text: "", cite: m[1] });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

export function humanize(key: string): string {
  const s = key.replace(/^law:[A-Z]{2}:/, "").replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
