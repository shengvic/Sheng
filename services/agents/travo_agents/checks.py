"""Deterministic playbook checks: durations, amounts, keywords (used by travo_rules)."""

from __future__ import annotations

import re
from typing import Any

from travo_agents.playbooks import ClauseRule

_NUM_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "eighteen": 18,
    "twenty-four": 24,
}
_DURATION = re.compile(
    r"\b(\d{1,3}|"
    + "|".join(_NUM_WORDS)
    + r")(?:\s*\(\d{1,3}\))?\s+(years?|months?|năm|tháng|tahun|bulan)\b",
    re.IGNORECASE,
)
_AMOUNT = re.compile(
    r"(?:RM|MYR|S\$|SGD|US\$|USD|\$|VND|IDR|Rp\.?)\s?(\d{1,3}(?:[,.]\d{3})+|\d+)(?:\.\d+)?",
    re.IGNORECASE,
)


def durations_months(text: str) -> list[int]:
    out = []
    for num, unit in _DURATION.findall(text):
        n = int(num) if num.isdigit() else _NUM_WORDS[num.lower()]
        out.append(n * 12 if unit.lower().startswith(("year", "năm", "tahun")) else n)
    return out


def amounts(text: str) -> list[float]:
    return [float(re.sub(r"[,.]", "", a)) for a in _AMOUNT.findall(text)]


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
