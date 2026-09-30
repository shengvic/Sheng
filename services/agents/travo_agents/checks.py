"""Deterministic playbook checks: durations, amounts, keywords (used by travo_rules)."""

from __future__ import annotations

from typing import Any

from travo_agents.numbers import amounts, durations_months, percents
from travo_agents.playbooks import ClauseRule
from travo_agents.taxonomy import CLAUSE_NAMES_VI

# Finding summaries in the review's output language (ADR-023).
MSG: dict[str, dict[str, str]] = {
    "en": {
        "missing": "No {clause} clause found.",
        "bad": "Contains disallowed wording: {words}.",
        "expected": "Expected one of: {words}.",
        "percent": "Rate of {p:g}% exceeds the playbook maximum of {max:g}%.",
        "max_months": "Duration is {m} months; playbook maximum is {max}.",
        "fallback": "Duration is {m} months: acceptable fallback (standard {std}, floor {fb}).",
        "min_months": "Duration is {m} months; playbook minimum is {min}.",
        "no_duration": "No duration stated; playbook requires one.",
        "max_amount": "Amount {a:,.0f} exceeds playbook maximum {max:,.0f}.",
        "min_amount": "Amount {a:,.0f} is below playbook minimum {min:,.0f}.",
        "standard": "Consistent with playbook.",
    },
    "vi": {
        "missing": "Không có điều khoản {clause}.",
        "bad": "Có câu chữ không được chấp nhận: {words}.",
        "expected": "Cần có một trong các nội dung: {words}.",
        "percent": "Tỷ lệ {p:g}% vượt mức tối đa {max:g}% của bộ quy tắc.",
        "max_months": "Thời hạn {m} tháng; tối đa theo bộ quy tắc là {max} tháng.",
        "fallback": "Thời hạn {m} tháng: phương án dự phòng chấp nhận được (chuẩn {std}, "
        "tối thiểu {fb} tháng).",
        "min_months": "Thời hạn {m} tháng; tối thiểu theo bộ quy tắc là {min} tháng.",
        "no_duration": "Không nêu thời hạn; bộ quy tắc yêu cầu có thời hạn.",
        "max_amount": "Số tiền {a:,.0f} vượt mức tối đa {max:,.0f} của bộ quy tắc.",
        "min_amount": "Số tiền {a:,.0f} thấp hơn mức tối thiểu {min:,.0f} của bộ quy tắc.",
        "standard": "Phù hợp với bộ quy tắc.",
    },
}

# Figures, words and units in English and Vietnamese live in `numbers.py` (shared with the
# bilingual checks). Re-exported here for existing callers.
__all__ = ["amounts", "durations_months", "evaluate_rule"]


def evaluate_rule(
    rule: ClauseRule, clauses: list[dict[str, Any]], language: str = "en"
) -> dict[str, Any] | None:
    """Return a finding dict for one rule, or None when the rule does not apply."""
    msg = MSG.get(language, MSG["en"])
    matching = [c for c in clauses if c.get("key") == rule.clause_key]
    if not matching:
        if not rule.required:
            return None
        name = (
            CLAUSE_NAMES_VI.get(rule.clause_key, rule.clause_key)
            if language == "vi"
            else rule.clause_key.replace("_", " ")
        )
        return _f(rule, None, "missing", msg["missing"].format(clause=name), 0.85)
    clause = matching[0]
    body = f"{clause.get('heading', '')} {clause.get('text', '')}"
    low = body.lower()
    idx = clause.get("i")

    bad = [w for w in rule.must_not_include_any if w.lower() in low]
    if bad:
        return _f(rule, idx, "non_standard", msg["bad"].format(words=", ".join(bad)), 0.8)
    if rule.must_include_any and not any(w.lower() in low for w in rule.must_include_any):
        words = ", ".join(rule.must_include_any)
        return _f(rule, idx, "non_standard", msg["expected"].format(words=words), 0.7)

    if rule.max_percent is not None:
        over = [p for p in percents(body) if p > rule.max_percent]
        if over:
            return _f(
                rule,
                idx,
                "non_standard",
                msg["percent"].format(p=over[0], max=rule.max_percent),
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
                msg["max_months"].format(m=m, max=rule.max_duration_months),
                0.9,
            )
        if rule.min_duration_months and m < rule.min_duration_months:
            fb = rule.fallback_min_duration_months
            if fb and m >= fb:
                return _f(
                    rule,
                    idx,
                    "fallback",
                    msg["fallback"].format(m=m, std=rule.min_duration_months, fb=fb),
                    0.9,
                )
            return _f(
                rule,
                idx,
                "non_standard",
                msg["min_months"].format(m=m, min=rule.min_duration_months),
                0.9,
            )
    elif rule.min_duration_months and not months:
        return _f(rule, idx, "non_standard", msg["no_duration"], 0.6)

    money = amounts(body)
    if money:
        a = money[0]
        if rule.max_amount is not None and a > rule.max_amount:
            return _f(
                rule,
                idx,
                "non_standard",
                msg["max_amount"].format(a=a, max=rule.max_amount),
                0.9,
            )
        if rule.min_amount is not None and a < rule.min_amount:
            return _f(
                rule,
                idx,
                "non_standard",
                msg["min_amount"].format(a=a, min=rule.min_amount),
                0.9,
            )
    return _f(rule, idx, "standard", msg["standard"], 0.8)


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
