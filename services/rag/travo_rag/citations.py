"""Per-claim citation validation (docs/04 §5).

Generated legal text carries inline markers `[[src:<unit_id>]]`. Each sentence is a claim.
Checks: existence → in force at as-of date → quote fidelity → entailment (pluggable judge).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from travo_rag.retrieval import LegalUnitHit, is_in_force, terms

CITE = re.compile(r"\[\[src:([^\]]+)\]\]")
QUOTE = re.compile(r"[\"“]([^\"”]{8,})[\"”]")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“(])")

PASSING = {"supported"}


@dataclass
class Claim:
    text: str
    cites: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)

    @property
    def plain(self) -> str:
        return CITE.sub("", self.text).strip()


@dataclass
class CitationResult:
    claim: str
    source_unit_id: str | None
    pinpoint: str | None
    status: str
    score: float
    checker: str

    @property
    def passed(self) -> bool:
        return self.status in PASSING


# (claim_text, unit) -> (status, score); status in supported|partial|contradicted|not_found
Judge = Callable[[list[tuple[str, LegalUnitHit]]], list[tuple[str, float]]]


def split_claims(generated: str) -> list[Claim]:
    claims = []
    for sentence in _SENT.split(generated.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        claims.append(
            Claim(text=sentence, cites=CITE.findall(sentence), quotes=QUOTE.findall(sentence))
        )
    return claims


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def lexical_support(claim: str, source_heading: str, source_text: str) -> tuple[str, float]:
    """Deterministic entailment proxy (T0). T1/T2 verifiers replace it via the router."""
    source = _norm(source_text)
    quotes = QUOTE.findall(claim)
    if quotes and all(_norm(q) in source for q in quotes):
        return "supported", 0.9
    claim_terms = set(terms(QUOTE.sub("", CITE.sub("", claim))))
    if not claim_terms:
        return "not_found", 0.0
    unit_terms = set(terms(source_heading + " " + source_text))
    score = len(claim_terms & unit_terms) / len(claim_terms)
    status = "supported" if score >= 0.6 else "partial" if score >= 0.3 else "not_found"
    return status, round(score, 3)


def lexical_judge(pairs: list[tuple[str, LegalUnitHit]]) -> list[tuple[str, float]]:
    return [lexical_support(claim, u.heading, u.text) for claim, u in pairs]


def validate(
    generated: str,
    *,
    lookup: Callable[[str], LegalUnitHit | None],
    as_of: date,
    judge: Judge = lexical_judge,
    checker: str = "travo-lexical-v0",
    require_cites: bool = True,
) -> list[CitationResult]:
    results: list[CitationResult] = []
    pending: list[tuple[int, str, LegalUnitHit]] = []
    for claim in split_claims(generated):
        if not claim.cites:
            if require_cites:
                results.append(CitationResult(claim.plain, None, None, "uncited", 0.0, checker))
            continue
        for uid in claim.cites:
            unit = lookup(uid)
            if unit is None:
                results.append(CitationResult(claim.plain, uid, None, "invalid_source", 0, checker))
                continue
            if not is_in_force(unit, as_of):
                results.append(
                    CitationResult(claim.plain, uid, unit.pinpoint, "not_in_force", 0, checker)
                )
                continue
            source = _norm(unit.text)
            if any(_norm(q) not in source for q in claim.quotes):
                results.append(
                    CitationResult(claim.plain, uid, unit.pinpoint, "misquoted", 0, checker)
                )
                continue
            results.append(CitationResult(claim.plain, uid, unit.pinpoint, "pending", 0, checker))
            pending.append((len(results) - 1, claim.plain, unit))
    if pending:
        verdicts = judge([(c, u) for _, c, u in pending])
        for (idx, _, _), (status, score) in zip(pending, verdicts, strict=True):
            results[idx].status = status
            results[idx].score = score
    return results
