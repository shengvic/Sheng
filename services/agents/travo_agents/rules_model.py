"""travo_rules: Travo's deterministic local "model" (tier T0, self-hosted).

Registered with the router like any other provider, so it is subject to the same
policy, logging and conflict rules. It keeps the pipeline usable offline and is
the floor that T1 domain models must beat on evals.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from travo_rag.citations import lexical_support
from travo_router.descriptor import TaskDescriptor
from travo_router.providers import Completion, Message, ProviderError, json_payload
from travo_router.registry import Endpoint

from travo_agents.checks import evaluate_rule
from travo_agents.playbooks import ClauseRule
from travo_agents.taxonomy import CLAUSE_TAXONOMY, CONTRACT_TYPES, GOVERNING_LAW_HINTS


class RulesProvider:
    def complete(
        self,
        endpoint: Endpoint,
        descriptor: TaskDescriptor,
        messages: list[Message],
        api_key: str | None,
    ) -> Completion:
        payload = json_payload(messages)
        handler = _HANDLERS.get(descriptor.task_type)
        if handler is None:
            raise ProviderError(f"travo_rules cannot handle {descriptor.task_type}")
        out: dict[str, Any] = handler(payload)
        text = json.dumps(out, ensure_ascii=False)
        return Completion(text=text, tokens_in=0, tokens_out=0)


def classify_rules(text: str) -> dict[str, Any]:
    low = text.lower()
    head = low[:3000]
    contract_type, type_conf = "OTHER", 0.3
    for ctype, hints in CONTRACT_TYPES.items():
        if any(h in head for h in hints):
            contract_type, type_conf = ctype, 0.8
            break
    governing_law, law_conf = None, 0.0
    for code, hints in GOVERNING_LAW_HINTS.items():
        if any(h in low for h in hints):
            governing_law, law_conf = code, 0.75
            break
    parties = _PARTY.findall(text[:4000])
    seen: list[str] = []
    for p in parties:
        p = p.strip(" ,")
        if p not in seen:
            seen.append(p)
    return {
        "contract_type": contract_type,
        "contract_type_confidence": type_conf,
        "governing_law": governing_law,
        "governing_law_confidence": law_conf,
        "parties": seen[:4],
    }


_PARTY = re.compile(
    r"\b((?:[A-Z][\w&.,'-]*\s+){1,6}?"
    r"(?:Pte\.?\s+Ltd\.?|Sdn\.?\s+Bhd\.?|Berhad|JSC|Co\.,?\s+Ltd\.?|Limited|LLC|Inc\.?)"
    r"|PT\s+(?:[A-Z][\w&.-]*\s?){1,5})"
)


def extract_rule(clause: dict[str, Any]) -> dict[str, Any]:
    heading = (clause.get("heading") or "").lower()
    body = (clause.get("text") or "")[:600].lower()
    best, best_score = "other", 0.0
    for key, (_desc, hints) in CLAUSE_TAXONOMY.items():
        score = 0.0
        for h in hints:
            if _contains(heading, h):
                score = max(score, 0.9 if len(h) > 4 else 0.6)
            elif _contains(body, h):
                score = max(score, 0.45 if len(h) > 6 else 0.25)
        if score > best_score:
            best, best_score = key, score
    if clause.get("heading", "").lower() == "preamble":
        best, best_score = "parties", 0.7
    return {"i": clause["i"], "key": best, "confidence": round(best_score, 2)}


def _contains(haystack: str, needle: str) -> bool:
    if len(needle) <= 4:  # short hints must match whole words ("am", "term", "nda")
        return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None
    return needle in haystack


def _compare(payload: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for raw in payload["rules"]:
        f = evaluate_rule(ClauseRule.model_validate(raw), payload["clauses"])
        if f is not None:
            findings.append(f)
    return {"findings": findings}


def _first_sentence(text: str, limit: int = 300) -> str:
    m = re.match(r"(.{20,}?[.;])(\s|$)", text.strip(), re.DOTALL)
    s = (m.group(1) if m else text.strip())[:limit]
    return s.rstrip(".;").replace('"', "'")


def _law_check(payload: dict[str, Any]) -> dict[str, Any]:
    evidence = payload.get("evidence") or []
    if not evidence:
        return {"note": "", "confidence": 0.0}
    top = evidence[0]
    issue = str(payload.get("issue", "")).rstrip(". ")
    note = f'{issue}: the provision states "{_first_sentence(top["text"])}" [[src:{top["id"]}]].'
    return {"note": note, "confidence": 0.6}


def _validate(payload: dict[str, Any]) -> dict[str, Any]:
    results = []
    for c in payload["claims"]:
        status, score = lexical_support(c["claim"], c.get("source_heading", ""), c["source_text"])
        results.append({"i": c["i"], "status": status, "score": score})
    return {"results": results}


def _redline(payload: dict[str, Any]) -> dict[str, Any]:
    examples = [e for e in payload.get("examples") or [] if e]
    if examples:  # the firm's own accepted wording beats the template
        return {"redline": examples[0], "confidence": 0.75}
    return {"redline": payload.get("template") or "", "confidence": 0.65}


def _memo(payload: dict[str, Any]) -> dict[str, Any]:
    fs = payload["findings"]
    issues = [f for f in fs if f.get("severity") != "info"]
    by_sev = {
        s: sum(1 for f in issues if f.get("severity") == s) for s in ("high", "medium", "low")
    }
    missing = [
        f["clause_key"].replace("_", " ") for f in issues if f.get("classification") == "missing"
    ]
    summary = (
        f"{len(issues)} issue(s) identified ({by_sev['high']} high, {by_sev['medium']} medium, "
        f"{by_sev['low']} low) across {len(fs)} playbook and legal checks."
    )
    if missing:
        summary += f" Missing clauses: {', '.join(missing)}."
    points = [f["summary"] for f in issues if f.get("severity") in ("high", "medium")]
    return {"executive_summary": summary, "negotiation_points": points}


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "classify": lambda p: classify_rules(p["text"]),
    "clause_extraction": lambda p: {"clauses": [extract_rule(c) for c in p["clauses"]]},
    "playbook_compare": _compare,
    "law_check": _law_check,
    "validate_claim": _validate,
    "redline": _redline,
    "memo": _memo,
}
