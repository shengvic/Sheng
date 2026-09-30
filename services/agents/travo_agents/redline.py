"""Redline drafter (docs/05 §2): replacement text from firm wording, then playbook template."""

from __future__ import annotations

from typing import Any

from travo_agents.base import AgentContext, call_json
from travo_agents.compare import FindingDraft
from travo_agents.prompts import load_prompt

NEEDS_REDLINE = {"non_standard", "missing"}


LANG_NAME = {"vi": "Vietnamese", "en": "English"}


def draft_redlines(
    ctx: AgentContext,
    drafts: list[FindingDraft],
    clauses_by_index: dict[int, dict[str, Any]],
    examples: dict[str, list[str]],
    standards: dict[str, str],
    *,
    language: str = "en",
    alt: bool = False,
) -> None:
    """Fills `suggested_redline` (or `suggested_redline_alt` when `alt`) in place, in
    `language`. `examples` are the firm's previously accepted or edited redlines per clause
    key, already filtered to what the initiator may see."""
    system = load_prompt("redline")
    for d in drafts:
        if d.kind != "playbook" or d.classification not in NEEDS_REDLINE:
            continue
        template = (
            (d.redline_template_vi or d.redline_template)
            if language == "vi"
            else (d.redline_template)
        )
        ex = examples.get(d.clause_key, [])
        if not template and not ex:
            continue
        clause = clauses_by_index.get(d.clause_index) if d.clause_index is not None else None
        text = (clause or {}).get("text", "")
        if clause and clause.get("lang") not in (None, language) and clause.get("text_alt"):
            text = clause["text_alt"]
        payload = {
            "clause_key": d.clause_key,
            "language": LANG_NAME.get(language, language),
            "clause_text": text,
            "standard": standards.get(d.rule_key, ""),
            "template": template or "",
            "examples": ex[:3],
        }
        res = call_json(ctx, "redline", system, payload, 400)
        out = str(res.data.get("redline", "")).strip()[:5000]
        if out and alt:
            d.suggested_redline_alt = out
        elif out:
            d.suggested_redline = out
