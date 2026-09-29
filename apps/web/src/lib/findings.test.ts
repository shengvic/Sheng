import { describe, expect, it } from "vitest";

import {
  DEFAULT_FILTER,
  applyFilter,
  counts,
  hasUnsupportedCitation,
  humanize,
  isOpen,
  sortFindings,
  splitCites,
} from "./findings";
import type { Finding } from "./types";

function f(p: Partial<Finding>): Finding {
  return {
    id: p.id ?? "x",
    clause_id: null,
    clause_key: "term_and_termination",
    rule_key: "term_length",
    kind: "playbook",
    classification: "non_standard",
    severity: "medium",
    summary: "",
    rationale: "",
    suggested_redline: null,
    confidence: 0.8,
    model_tier: "T0",
    escalated: false,
    status: "needs_review",
    disposition: null,
    edited_text: null,
    reason_code: null,
    note: null,
    citations: [],
    ...p,
  };
}

describe("findings logic", () => {
  it("open = blocks export (ADR-016)", () => {
    expect(isOpen(f({}))).toBe(true);
    expect(isOpen(f({ disposition: "deferred" }))).toBe(true);
    expect(isOpen(f({ disposition: "accepted" }))).toBe(false);
    expect(isOpen(f({ severity: "info" }))).toBe(false);
  });

  it("unsupported citations only matter on non-rejected findings", () => {
    const cite = { id: "c", claim_text: "", source_unit_id: null, pinpoint: null, score: 0, checker: "x", override_reason: null };
    expect(hasUnsupportedCitation(f({ citations: [{ ...cite, status: "not_found" }] }))).toBe(true);
    expect(hasUnsupportedCitation(f({ disposition: "rejected", citations: [{ ...cite, status: "not_found" }] }))).toBe(false);
    expect(hasUnsupportedCitation(f({ citations: [{ ...cite, status: "not_found", override_reason: "ok by me" }] }))).toBe(false);
    expect(hasUnsupportedCitation(f({ citations: [{ ...cite, status: "supported" }] }))).toBe(false);
  });

  it("filters: default hides standard findings", () => {
    const list = [f({ id: "a", severity: "info" }), f({ id: "b", kind: "law" }), f({ id: "c", disposition: "accepted" })];
    expect(applyFilter(list, DEFAULT_FILTER).map((x) => x.id)).toEqual(["b", "c"]);
    expect(applyFilter(list, { ...DEFAULT_FILTER, kind: "law" }).map((x) => x.id)).toEqual(["b"]);
    expect(applyFilter(list, { ...DEFAULT_FILTER, state: "open" }).map((x) => x.id)).toEqual(["b"]);
    expect(applyFilter(list, { severity: "all", kind: "all", state: "done" }).map((x) => x.id)).toEqual(["a", "c"]);
  });

  it("sorts by severity, then document position, missing clauses last", () => {
    const order = new Map([["c1", 1], ["c2", 2]]);
    const list = [
      f({ id: "missing", severity: "high", clause_id: null }),
      f({ id: "late", severity: "high", clause_id: "c2" }),
      f({ id: "early", severity: "high", clause_id: "c1" }),
      f({ id: "low", severity: "low", clause_id: "c1" }),
    ];
    expect(sortFindings(list, order).map((x) => x.id)).toEqual(["early", "late", "missing", "low"]);
  });

  it("counts", () => {
    const c = counts([f({ severity: "high" }), f({ severity: "info" }), f({ status: "needs_human", disposition: "accepted" })]);
    expect(c).toMatchObject({ total: 3, issues: 2, open: 1, needsHuman: 1 });
  });

  it("splits cite markers and humanizes rule keys", () => {
    expect(splitCites('Check this: "x" [[src:SG/A#s 3]].')).toEqual([
      { text: 'Check this: "x" ' },
      { text: "", cite: "SG/A#s 3" },
      { text: "." },
    ]);
    expect(humanize("law:SG:agreed_damages")).toBe("Agreed damages");
    expect(humanize("liability_cap_floor")).toBe("Liability cap floor");
  });
});
