"""Bilingual discrepancy checks for VI–EN contracts (docs/14 §4, ADR-023).

Two layers:
- Deterministic checks, always run locally: amounts, figures vs words, percentages, durations,
  dates, standalone numbers, tax codes, negation, and a missing counterpart. They cannot
  hallucinate, so they work with no model at all.
- A semantic check through the router (`bilingual_check`, T1). The offline rules model returns
  no semantic differences; model output is kept only if its quoted spans really occur in the
  clause texts.
Plus a document-level check of the prevailing-language clause.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from travo_agents.base import AgentContext, AgentOutputError, call_json
from travo_agents.compare import FindingDraft
from travo_agents.numbers import (
    figures_with_words,
    parse_amounts,
    parse_dates,
    parse_durations,
    percents,
)
from travo_agents.prompts import load_prompt

SYSTEM = load_prompt("bilingual_check")
BATCH = 8
MAX_CHARS = 2000
SEVERITIES = {"high", "medium", "low"}
LANG_NAME = {"vi": "Vietnamese", "en": "English"}

_NEG = {
    "vi": re.compile(r"\b(không|chưa|cấm|nghiêm cấm)\b(?!\s+(?:trăm|gian))", re.I),
    "en": re.compile(r"\b(not|no|never|neither|nor|without|prohibited)\b", re.I),
}
_TAX_CODE = re.compile(r"\b\d{10}(?:-\d{3})?\b")
_NUMBER = re.compile(r"(?<![\d.,])\d{1,9}(?:[.,]\d+)?(?![\d.,])")


@dataclass
class Difference:
    kind: str  # amount | figure_words | percent | duration | date | number | tax_code |
    # negation | missing_counterpart | semantic
    severity: str
    summary: str
    primary_span: str = ""
    other_span: str = ""
    confidence: float = 0.9


@dataclass
class ClausePair:
    index: int
    clause_key: str
    heading: str
    primary: str
    other: str
    extra: dict[str, Any] = field(default_factory=dict)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _nfc(s)).strip().lower()


def _fmt(n: float) -> str:
    return f"{n:,.0f}" if n == int(n) else f"{n:,.2f}"


def _set_diff(
    kind: str, severity: str, label: str, a: list[Any], b: list[Any], langs: tuple[str, str]
) -> Difference | None:
    ca, cb = Counter(a), Counter(b)
    if ca == cb:
        return None
    only_a = sorted((ca - cb).elements(), key=str)
    only_b = sorted((cb - ca).elements(), key=str)
    pa, pb = LANG_NAME.get(langs[0], langs[0]), LANG_NAME.get(langs[1], langs[1])
    parts = []
    if only_a:
        parts.append(f"{pa} only: {', '.join(map(str, only_a))}")
    if only_b:
        parts.append(f"{pb} only: {', '.join(map(str, only_b))}")
    return Difference(kind, severity, f"{label} differ between versions ({'; '.join(parts)}).")


def deterministic_diffs(pair: ClausePair, langs: tuple[str, str]) -> list[Difference]:
    p, o = _nfc(pair.primary), _nfc(pair.other)
    out: list[Difference] = []
    if not o.strip():
        if p.strip() and pair.clause_key not in ("parties", "signatures"):
            other = LANG_NAME.get(langs[1], langs[1])
            out.append(
                Difference(
                    "missing_counterpart",
                    "medium",
                    f"No {other} text found for this clause.",
                    confidence=0.7,
                )
            )
        return out

    for side, text in ((langs[0], p), (langs[1], o)):
        for fw in figures_with_words(text):
            if fw.words_value is not None and fw.words_value != int(fw.figure):
                out.append(
                    Difference(
                        "figure_words",
                        "high",
                        f"Amount in figures ({_fmt(fw.figure)}) does not match the amount in "
                        f"words ({_fmt(fw.words_value)}) in the {LANG_NAME.get(side, side)} text.",
                        fw.span if side == langs[0] else "",
                        fw.span if side == langs[1] else "",
                        0.95,
                    )
                )

    am_p, am_o = parse_amounts(p), parse_amounts(o)
    d = _set_diff(
        "amount", "high", "Amounts", [_fmt(a.value) for a in am_p],
        [_fmt(a.value) for a in am_o], langs,
    )  # fmt: skip
    if d:
        d.primary_span = "; ".join(a.span for a in am_p)
        d.other_span = "; ".join(a.span for a in am_o)
        out.append(d)
    for kind, label, fn in (
        ("percent", "Percentages", percents),
        ("duration", "Durations (months)", lambda t: [x.months for x in parse_durations(t)]),
        ("date", "Dates", lambda t: [x.value.isoformat() for x in parse_dates(t)]),
    ):
        d = _set_diff(kind, "high", label, fn(p), fn(o), langs)
        if d:
            out.append(d)
    d = _set_diff(
        "tax_code", "high", "Tax codes", _TAX_CODE.findall(p), _TAX_CODE.findall(o), langs
    )
    if d:
        out.append(d)

    # Standalone numbers not already covered (e.g. "30 ngày" vs "45 days").
    def rest(text: str) -> list[str]:
        spans = [a.span for a in parse_amounts(text)]
        spans += [x.span for x in parse_durations(text)] + [x.span for x in parse_dates(text)]
        spans += [fw.span for fw in figures_with_words(text)]
        for s in spans:
            text = text.replace(s, " ")
        text = re.sub(r"\d{1,3}(?:[.,]\d{1,2})?\s*(?:%|phần trăm|per ?cent)", " ", text, flags=re.I)
        text = _TAX_CODE.sub(" ", text)
        text = re.sub(r"^(?:điều|article|khoản|clause)\s+\d+", " ", text, flags=re.I | re.M)
        text = re.sub(r"\(\s*[a-zđ]\s*\)|^\s*\d{1,2}[.)]\s", " ", text, flags=re.I | re.M)
        return [str(int(float(n.replace(",", ".")))) for n in _NUMBER.findall(text)]

    d = _set_diff("number", "medium", "Numbers", rest(p), rest(o), langs)
    if d:
        d.confidence = 0.75
        out.append(d)

    neg_p = bool(_NEG.get(langs[0], _NEG["en"]).search(p))
    neg_o = bool(_NEG.get(langs[1], _NEG["en"]).search(o))
    if neg_p != neg_o:
        which = LANG_NAME.get(langs[0] if neg_p else langs[1])
        out.append(
            Difference(
                "negation",
                "medium",
                f"Only the {which} text contains a negation — check that both versions state "
                "the same obligation.",
                confidence=0.6,
            )
        )
    return out


# ---------------------------------------------------------------- prevailing language

_PREVAIL = [
    (
        re.compile(r"(bản|văn bản)\s+tiếng\s+việt\s+(sẽ\s+|được\s+)*(ưu tiên|có giá trị)", re.I),
        "vi",
    ),
    (re.compile(r"(bản|văn bản)\s+tiếng\s+anh\s+(sẽ\s+|được\s+)*(ưu tiên|có giá trị)", re.I), "en"),
    (re.compile(r"vietnamese\s+(version|text|language)\s+(shall\s+|will\s+)?prevail", re.I), "vi"),
    (re.compile(r"english\s+(version|text|language)\s+(shall\s+|will\s+)?prevail", re.I), "en"),
]


def prevailing_language(pairs: list[ClausePair]) -> tuple[str | None, str | None, int | None]:
    """(prevailing per primary text, prevailing per other text, clause index)."""
    said: dict[str, str | None] = {"primary": None, "other": None}
    where = None
    for pair in pairs:
        for side, text in (("primary", pair.primary), ("other", pair.other)):
            for pattern, lang in _PREVAIL:
                if pattern.search(_nfc(text)):
                    said[side] = said[side] or lang
                    where = pair.index if where is None else where
    return said["primary"], said["other"], where


# ---------------------------------------------------------------- semantic (router)


def _semantic(
    ctx: AgentContext, pairs: list[ClausePair], langs: tuple[str, str]
) -> tuple[list[tuple[int, Difference]], str | None]:
    found: list[tuple[int, Difference]] = []
    tier = None
    usable = [p for p in pairs if p.primary.strip() and p.other.strip()]
    for start in range(0, len(usable), BATCH):
        batch = usable[start : start + BATCH]
        payload = {
            "languages": list(langs),
            "pairs": [
                {"i": p.index, "clause_key": p.clause_key, "a": p.primary[:MAX_CHARS],
                 "b": p.other[:MAX_CHARS]}
                for p in batch
            ],
        }  # fmt: skip
        res = call_json(ctx, "bilingual_check", SYSTEM, payload, est_output=150 * len(batch))
        tier = res.tier
        items = res.data.get("differences")
        if not isinstance(items, list):
            raise AgentOutputError("bilingual_check output missing 'differences' list")
        by_index = {p.index: p for p in batch}
        for item in items:
            try:
                pair = by_index[int(item["i"])]
                a, b = str(item.get("a_span", "")), str(item.get("b_span", ""))
                severity = str(item.get("severity", "medium"))
                summary = str(item["summary"])[:600]
            except (KeyError, TypeError, ValueError):
                continue
            # Grounding: both quoted spans must exist in the clause texts.
            if (
                not a
                or not b
                or _norm(a) not in _norm(pair.primary)
                or _norm(b) not in _norm(pair.other)
            ):
                continue
            found.append(
                (
                    pair.index,
                    Difference(
                        "semantic",
                        severity if severity in SEVERITIES else "medium",
                        summary,
                        a[:500],
                        b[:500],
                        float(item.get("confidence", 0.6) or 0.6),
                    ),
                )
            )
    return found, tier


# ---------------------------------------------------------------- entry point


def check_bilingual(
    ctx: AgentContext, pairs: list[ClausePair], langs: tuple[str, str]
) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    by_index = {p.index: p for p in pairs}
    prev_p, prev_o, where = prevailing_language(pairs)
    prevailing = prev_p or prev_o

    def draft(index: int | None, d: Difference, tier: str | None) -> FindingDraft:
        pair = by_index.get(index) if index is not None else None
        return FindingDraft(
            rule_key=f"bilingual:{d.kind}",
            clause_key=pair.clause_key if pair else "language",
            clause_index=index,
            kind="bilingual",
            classification="discrepancy",
            severity=d.severity,
            summary=d.summary,
            rationale=(
                f"The {LANG_NAME.get(prevailing, prevailing)} version prevails under the "
                "contract's language clause; the other version should be aligned to it."
                if prevailing
                else "The contract does not say which language version prevails."
            ),
            confidence=d.confidence,
            tier=tier,
            evidence={
                "type": d.kind,
                "languages": list(langs),
                "primary_span": d.primary_span,
                "other_span": d.other_span,
                "prevailing": prevailing,
            },
        )

    for pair in pairs:
        for d in deterministic_diffs(pair, langs):
            drafts.append(draft(pair.index, d, "T0"))
    if prev_p and prev_o and prev_p != prev_o:
        drafts.append(
            draft(
                where,
                Difference(
                    "prevailing_language",
                    "high",
                    "The language clauses contradict each other: the "
                    f"{LANG_NAME.get(langs[0])} text says the {LANG_NAME.get(prev_p)} version "
                    f"prevails, the {LANG_NAME.get(langs[1])} text says the "
                    f"{LANG_NAME.get(prev_o)} version prevails.",
                ),
                "T0",
            )
        )
    elif not prevailing:
        drafts.append(
            draft(
                None,
                Difference(
                    "prevailing_language",
                    "medium",
                    "No clause says which language version prevails if the two versions differ.",
                    confidence=0.8,
                ),
                "T0",
            )
        )
    semantic, tier = _semantic(ctx, pairs, langs)
    seen = {(d.clause_index, d.summary) for d in drafts}
    for index, d in semantic:
        if (index, d.summary) not in seen:
            drafts.append(draft(index, d, tier))
    return drafts
