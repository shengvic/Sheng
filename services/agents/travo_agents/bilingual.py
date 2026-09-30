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

# Summaries in the review's output language (ADR-023).
TEXT: dict[str, dict[str, Any]] = {
    "en": {
        "lang": {"vi": "Vietnamese", "en": "English"},
        "labels": {
            "amount": "Amounts", "percent": "Percentages", "duration": "Durations (months)",
            "date": "Dates", "tax_code": "Tax codes", "number": "Numbers",
        },
        "only": "{lang} only: {values}",
        "differ": "{label} differ between versions ({parts}).",
        "missing": "No {lang} text found for this clause.",
        "figure_words": "Amount in figures ({fig}) does not match the amount in words ({words}) "
        "in the {lang} text.",
        "negation": "Only the {lang} text contains a negation — check that both versions state "
        "the same obligation.",
        "contradict": "The language clauses contradict each other: the {a} text says the {pa} "
        "version prevails, the {b} text says the {pb} version prevails.",
        "no_prevailing": "No clause says which language version prevails if the two versions "
        "differ.",
        "prevails": "The {lang} version prevails under the contract's language clause; the other "
        "version should be aligned to it.",
        "no_prevailing_rationale": "The contract does not say which language version prevails.",
    },
    "vi": {
        "lang": {"vi": "tiếng Việt", "en": "tiếng Anh"},
        "labels": {
            "amount": "Số tiền", "percent": "Tỷ lệ", "duration": "Thời hạn (tháng)",
            "date": "Ngày", "tax_code": "Mã số thuế", "number": "Con số",
        },
        "only": "chỉ bản {lang}: {values}",
        "differ": "{label} khác nhau giữa hai bản ({parts}).",
        "missing": "Không tìm thấy bản {lang} của điều khoản này.",
        "figure_words": "Số tiền bằng số ({fig}) không khớp với số tiền bằng chữ ({words}) "
        "trong bản {lang}.",
        "negation": "Chỉ bản {lang} có ý phủ định — kiểm tra để hai bản quy định cùng một "
        "nghĩa vụ.",
        "contradict": "Các điều khoản ngôn ngữ mâu thuẫn: bản {a} quy định ưu tiên bản {pa}, "
        "bản {b} quy định ưu tiên bản {pb}.",
        "no_prevailing": "Không có điều khoản quy định bản ngôn ngữ nào được ưu tiên khi hai bản "
        "khác nhau.",
        "prevails": "Theo điều khoản ngôn ngữ, bản {lang} được ưu tiên áp dụng; bản còn lại cần "
        "được chỉnh cho thống nhất.",
        "no_prevailing_rationale": "Hợp đồng không quy định bản ngôn ngữ nào được ưu tiên.",
    },
}  # fmt: skip

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
    kind: str,
    severity: str,
    a: list[Any],
    b: list[Any],
    langs: tuple[str, str],
    tx: dict[str, Any],
) -> Difference | None:
    ca, cb = Counter(a), Counter(b)
    if ca == cb:
        return None
    only_a = sorted((ca - cb).elements(), key=str)
    only_b = sorted((cb - ca).elements(), key=str)
    parts = []
    for lang, only in ((langs[0], only_a), (langs[1], only_b)):
        if only:
            name = tx["lang"].get(lang, lang)
            parts.append(tx["only"].format(lang=name, values=", ".join(map(str, only))))
    summary = tx["differ"].format(label=tx["labels"][kind], parts="; ".join(parts))
    return Difference(kind, severity, summary)


def deterministic_diffs(
    pair: ClausePair, langs: tuple[str, str], language: str = "en"
) -> list[Difference]:
    tx = TEXT.get(language, TEXT["en"])
    p, o = _nfc(pair.primary), _nfc(pair.other)
    out: list[Difference] = []
    if not o.strip():
        if p.strip() and pair.clause_key not in ("parties", "signatures"):
            other = tx["lang"].get(langs[1], langs[1])
            out.append(
                Difference(
                    "missing_counterpart",
                    "medium",
                    tx["missing"].format(lang=other),
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
                        tx["figure_words"].format(
                            fig=_fmt(fw.figure),
                            words=_fmt(fw.words_value),
                            lang=tx["lang"].get(side, side),
                        ),
                        fw.span if side == langs[0] else "",
                        fw.span if side == langs[1] else "",
                        0.95,
                    )
                )

    am_p, am_o = parse_amounts(p), parse_amounts(o)
    d = _set_diff(
        "amount", "high", [_fmt(a.value) for a in am_p], [_fmt(a.value) for a in am_o], langs, tx
    )
    if d:
        d.primary_span = "; ".join(a.span for a in am_p)
        d.other_span = "; ".join(a.span for a in am_o)
        out.append(d)
    for kind, fn in (
        ("percent", percents),
        ("duration", lambda t: [x.months for x in parse_durations(t)]),
        ("date", lambda t: [x.value.isoformat() for x in parse_dates(t)]),
    ):
        d = _set_diff(kind, "high", fn(p), fn(o), langs, tx)
        if d:
            out.append(d)
    d = _set_diff("tax_code", "high", _TAX_CODE.findall(p), _TAX_CODE.findall(o), langs, tx)
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

    d = _set_diff("number", "medium", rest(p), rest(o), langs, tx)
    if d:
        d.confidence = 0.75
        out.append(d)

    neg_p = bool(_NEG.get(langs[0], _NEG["en"]).search(p))
    neg_o = bool(_NEG.get(langs[1], _NEG["en"]).search(o))
    if neg_p != neg_o:
        which = tx["lang"].get(langs[0] if neg_p else langs[1])
        out.append(
            Difference("negation", "medium", tx["negation"].format(lang=which), confidence=0.6)
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
    ctx: AgentContext, pairs: list[ClausePair], langs: tuple[str, str], language: str = "en"
) -> list[FindingDraft]:
    tx = TEXT.get(language, TEXT["en"])
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
                tx["prevails"].format(lang=tx["lang"].get(prevailing, prevailing))
                if prevailing
                else tx["no_prevailing_rationale"]
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
        for d in deterministic_diffs(pair, langs, language):
            drafts.append(draft(pair.index, d, "T0"))
    if prev_p and prev_o and prev_p != prev_o:
        drafts.append(
            draft(
                where,
                Difference(
                    "prevailing_language",
                    "high",
                    tx["contradict"].format(
                        a=tx["lang"].get(langs[0]),
                        pa=tx["lang"].get(prev_p),
                        b=tx["lang"].get(langs[1]),
                        pb=tx["lang"].get(prev_o),
                    ),
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
                    tx["no_prevailing"],
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
