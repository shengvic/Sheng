"""Playbook comparator agent (docs/05 §2): one finding per applicable playbook rule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from travo_agents.base import AgentContext, AgentOutputError, call_with_escalation
from travo_agents.playbooks import Playbook
from travo_agents.prompts import load_prompt

CLASSES = {"standard", "fallback", "non_standard", "missing"}


@dataclass
class FindingDraft:
    rule_key: str
    clause_key: str
    clause_index: int | None
    kind: str
    classification: str
    severity: str
    summary: str
    rationale: str
    confidence: float
    tier: str | None
    escalated: bool = False
    needs_human: bool = False
    redline_template: str | None = None
    redline_template_vi: str | None = None
    suggested_redline: str | None = None
    suggested_redline_alt: str | None = None
    note: str | None = None  # law notes: generated text with [[src:…]] markers
    evidence: dict[str, Any] | None = None  # bilingual findings: both spans, prevailing language


def clause_payload(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"i": c["i"], "key": c["key"], "heading": c.get("heading", ""), "text": c["text"][:1500]}
        for c in clauses
    ]


def compare(
    ctx: AgentContext, playbook: Playbook, clauses: list[dict[str, Any]], threshold: float = 0.5
) -> list[FindingDraft]:
    rules = {r.key: r for r in playbook.rules}
    present = {c["key"] for c in clauses}
    must_answer = {r.key for r in playbook.rules if r.required or r.clause_key in present}
    payload = {
        "rules": [r.model_dump(exclude_none=True) for r in playbook.rules],
        "clauses": clause_payload(clauses),
    }

    def acceptable(data: dict[str, Any]) -> bool:
        items = data.get("findings")
        if not isinstance(items, list):
            return False
        seen = {i.get("rule_key") for i in items if isinstance(i, dict)}
        confident = all(float(i.get("confidence", 0)) >= threshold for i in items)
        return must_answer <= seen and confident

    result = call_with_escalation(
        ctx,
        "playbook_compare",
        load_prompt("playbook_compare"),
        payload,
        acceptable=acceptable,
        est_output=120 * len(rules),
    )
    items = result.data.get("findings")
    if not isinstance(items, list):
        raise AgentOutputError("playbook_compare output missing 'findings'")
    index_ok = {c["i"] for c in clauses}
    drafts: list[FindingDraft] = []
    for item in items:
        rule = rules.get(str(item.get("rule_key")))
        cls = item.get("classification")
        if rule is None or cls not in CLASSES:
            continue
        idx = item.get("clause_index")
        drafts.append(
            FindingDraft(
                rule_key=rule.key,
                clause_key=rule.clause_key,
                clause_index=idx if idx in index_ok else None,
                kind="playbook",
                classification=cls,
                severity="info" if cls == "standard" else rule.severity,
                summary=str(item.get("summary", ""))[:2000],
                rationale=rule.rationale,
                confidence=max(0.0, min(float(item.get("confidence", 0)), 1.0)),
                tier=result.tier,
                escalated=result.escalated,
                needs_human=result.needs_human,
                redline_template=rule.redline_template,
                redline_template_vi=rule.redline_template_vi,
            )
        )
    return drafts
