"""Law-check agent (docs/05 §4): local-law notes grounded in retrieved legal units.

Jurisdiction packs hold triggers and retrieval queries — never legal text. The note must cite
retrieved units; the citation validator decides whether it can stand (docs/04 §5).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from travo_rag.citations import CitationResult
from travo_rag.retrieval import LegalUnitHit
from travo_router.client import NoEligibleModel

from travo_agents.base import AgentContext, call_json
from travo_agents.compare import FindingDraft
from travo_agents.prompts import load_prompt


class LawRule(BaseModel):
    key: str
    clause_keys: list[str]
    triggers: list[str] = Field(default_factory=list)  # empty = always
    query: str
    issue: str
    severity: Literal["high", "medium", "low"] = "medium"


class JurisdictionPack(BaseModel):
    jurisdiction: str
    rules: list[LawRule]


def load_packs(directory: str | Path) -> dict[str, JurisdictionPack]:
    packs = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        pack = JurisdictionPack.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        packs[pack.jurisdiction] = pack
    return packs


Retrieve = Callable[[str, str], list[LegalUnitHit]]  # (query, clause text) -> hits
Validate = Callable[[str], list[CitationResult]]


def lawcheck(
    ctx: AgentContext,
    pack: JurisdictionPack,
    clauses: list[dict[str, Any]],
    retrieve: Retrieve,
    validate: Validate,
) -> list[tuple[FindingDraft, list[CitationResult]]]:
    out: list[tuple[FindingDraft, list[CitationResult]]] = []
    for rule in pack.rules:
        for clause in clauses:
            if clause["key"] not in rule.clause_keys:
                continue
            body = f"{clause.get('heading', '')} {clause['text']}".lower()
            if rule.triggers and not any(t.lower() in body for t in rule.triggers):
                continue
            out.append(_check(ctx, pack, rule, clause, retrieve, validate))
    return out


def _check(
    ctx: AgentContext,
    pack: JurisdictionPack,
    rule: LawRule,
    clause: dict[str, Any],
    retrieve: Retrieve,
    validate: Validate,
) -> tuple[FindingDraft, list[CitationResult]]:
    draft = FindingDraft(
        rule_key=f"law:{pack.jurisdiction}:{rule.key}",
        clause_key=clause["key"],
        clause_index=clause["i"],
        kind="law",
        classification="legal_note",
        severity=rule.severity,
        summary=rule.issue,
        rationale="",
        confidence=0.0,
        tier=None,
    )
    hits = retrieve(rule.query, clause["text"])
    if not hits:
        draft.needs_human = True
        draft.rationale = "No legal sources in the index address this issue (no_sources)."
        return draft, []
    payload = {
        "issue": rule.issue,
        "jurisdiction": pack.jurisdiction,
        "clause": {"heading": clause.get("heading", ""), "text": clause["text"][:2000]},
        "evidence": [{"id": h.id, "pinpoint": h.pinpoint, "text": h.text[:2500]} for h in hits],
    }
    system = load_prompt("law_check")
    attempts: list[tuple[str | None, str | None]] = [
        (None, None),
        (None, "retry"),
        ("citation_validation_failed", None),
    ]
    results: list[CitationResult] = []
    for escalation, retry in attempts:
        if retry:
            payload["feedback"] = [f"{r.status}: {r.claim}" for r in results if not r.passed]
        try:
            res = call_json(ctx, "law_check", system, payload, 600, escalation_reason=escalation)
        except NoEligibleModel:
            if escalation is None:
                raise
            break  # no higher tier allowed → human review (ADR-012)
        note = str(res.data.get("note", "")).strip()
        results = validate(note) if note else []
        draft.note, draft.tier, draft.escalated = note, res.tier, escalation is not None
        draft.confidence = max(0.0, min(float(res.data.get("confidence", 0)), 1.0))
        if results and all(r.passed for r in results):
            return draft, results
    draft.needs_human = True
    draft.rationale = "Citation validation failed; lawyer must verify or override."
    return draft, results
