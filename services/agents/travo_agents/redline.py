"""Redline drafter (docs/05 §2): replacement text from firm wording, then playbook template."""

from __future__ import annotations

from typing import Any

from travo_agents.base import AgentContext, call_json
from travo_agents.compare import FindingDraft
from travo_agents.prompts import load_prompt

NEEDS_REDLINE = {"non_standard", "missing"}


def draft_redlines(
    ctx: AgentContext,
    drafts: list[FindingDraft],
    clauses_by_index: dict[int, dict[str, Any]],
    examples: dict[str, list[str]],
    standards: dict[str, str],
) -> None:
    """Fills `suggested_redline` in place. `examples` are the firm's previously accepted or
    edited redlines per clause key, already filtered to what the initiator may see."""
    system = load_prompt("redline")
    for d in drafts:
        if d.kind != "playbook" or d.classification not in NEEDS_REDLINE:
            continue
        ex = examples.get(d.clause_key, [])
        if not d.redline_template and not ex:
            continue
        clause = clauses_by_index.get(d.clause_index) if d.clause_index is not None else None
        payload = {
            "clause_key": d.clause_key,
            "clause_text": (clause or {}).get("text", ""),
            "standard": standards.get(d.rule_key, ""),
            "template": d.redline_template or "",
            "examples": ex[:3],
        }
        res = call_json(ctx, "redline", system, payload, 400)
        text = str(res.data.get("redline", "")).strip()
        if text:
            d.suggested_redline = text[:5000]
