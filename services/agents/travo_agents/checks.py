"""Deterministic playbook checks: durations, amounts, keywords (used by travo_rules)."""

from __future__ import annotations

from typing import Any

from travo_agents.numbers import amounts, durations_months, percents
from travo_agents.playbooks import ClauseRule

# Figures, words and units in English and Vietnamese live in `numbers.py` (shared with the
# bilingual checks). Re-exported here for existing callers.
__all__ = ["amounts", "durations_months", "evaluate_rule"]


def evaluate_rule(rule: ClauseRule, clauses: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return a finding dict for one rule, or None when the rule does not apply."""
    matching = [c for c in clauses if c.get("key") == rule.clause_key]
    if not matching:
        if not rule.required:
            return None
        return _f(
            rule, None, "missing", f"No {rule.clause_key.replace('_', ' ')} clause found.", 0.85
        )
    clause = matching[0]
    body = f"{clause.get('heading', '')} {clause.get('text', '')}"
    low = body.lower()
    idx = clause.get("i")

    bad = [w for w in rule.must_not_include_any if w.lower() in low]
    if bad:
        return _f(rule, idx, "non_standard", f"Contains disallowed wording: {', '.join(bad)}.", 0.8)
    if rule.must_include_any and not any(w.lower() in low for w in rule.must_include_any):
        return _f(
            rule, idx, "non_standard", f"Expected one of: {', '.join(rule.must_include_any)}.", 0.7
        )

    if rule.max_percent is not None:
        over = [p for p in percents(body) if p > rule.max_percent]
        if over:
            return _f(
                rule,
                idx,
                "non_standard",
                f"Rate of {over[0]:g}% exceeds the playbook maximum of {rule.max_percent:g}%.",
                0.9,
            )

    months = durations_months(body)
    if months and (rule.min_duration_months or rule.max_duration_months):
        m = months[0]
        if rule.max_duration_months and m > rule.max_duration_months:
            return _f(
                rule,
                idx,
                "non_standard",
                f"Duration is {m} months; playbook maximum is {rule.max_duration_months}.",
                0.9,
            )
        if rule.min_duration_months and m < rule.min_duration_months:
            fb = rule.fallback_min_duration_months
            if fb and m >= fb:
                return _f(
                    rule,
                    idx,
                    "fallback",
                    f"Duration is {m} months: acceptable fallback (standard "
                    f"{rule.min_duration_months}, floor {fb}).",
                    0.9,
                )
            return _f(
                rule,
                idx,
                "non_standard",
                f"Duration is {m} months; playbook minimum is {rule.min_duration_months}.",
                0.9,
            )
    elif rule.min_duration_months and not months:
        return _f(rule, idx, "non_standard", "No duration stated; playbook requires one.", 0.6)

    money = amounts(body)
    if money:
        a = money[0]
        if rule.max_amount is not None and a > rule.max_amount:
            return _f(
                rule,
                idx,
                "non_standard",
                f"Amount {a:,.0f} exceeds playbook maximum {rule.max_amount:,.0f}.",
                0.9,
            )
        if rule.min_amount is not None and a < rule.min_amount:
            return _f(
                rule,
                idx,
                "non_standard",
                f"Amount {a:,.0f} is below playbook minimum {rule.min_amount:,.0f}.",
                0.9,
            )
    return _f(rule, idx, "standard", "Consistent with playbook.", 0.8)


def _f(
    rule: ClauseRule, idx: Any, classification: str, summary: str, conf: float
) -> dict[str, Any]:
    return {
        "rule_key": rule.key,
        "clause_index": idx,
        "classification": classification,
        "summary": summary,
        "confidence": conf,
    }
