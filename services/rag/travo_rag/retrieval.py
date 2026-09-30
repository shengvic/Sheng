"""Legal retrieval: lexical full-text search + filters + rerank (docs/04 §4).

P1 slice: Postgres full-text (`simple` config, works across en/vi/id/ms without stemming).
Dense retrieval (pgvector) plugs in via `DenseRetriever` and is merged by reciprocal rank.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

# Vietnamese words are written as syllables, many of two letters ("bộ", "lý", "về"), so
# terms of two letters are kept and function words are stopped instead.
_WORD = re.compile(r"[^\W_]{2,}", re.UNICODE)
_STOP = {
    # English
    "the", "and", "for", "that", "this", "with", "shall", "any", "are", "not", "under", "such",
    "all", "may", "its", "which", "from", "been", "has", "have", "each", "other", "into", "of",
    "to", "in", "on", "or", "by", "be", "an", "as", "at", "is", "it", "if", "no",
    # Vietnamese function words
    "và", "của", "các", "có", "được", "cho", "là", "với", "theo", "trong", "này", "những",
    "một", "khi", "thì", "để", "đã", "sẽ", "tại", "về", "do", "từ", "đến", "hoặc", "nếu",
    "mà", "như", "trên", "bị", "vào", "ra", "phải", "không",
}  # fmt: skip


@dataclass(frozen=True)
class LegalUnitHit:
    id: str
    source_id: str
    source_title: str
    unit_path: str
    heading: str
    text: str
    status: str
    effective_from: date | None
    effective_to: date | None
    is_fixture: bool
    score: float = 0.0
    review_status: str = "unverified"

    @property
    def pinpoint(self) -> str:
        return format_pinpoint(self.source_title, self.unit_path)


def format_pinpoint(source_title: str, unit_path: str) -> str:
    """ "Contracts Act 1950, s 75"; Vietnamese style "Điều 301 Luật Thương mại 2005"."""
    if unit_path.startswith(("Điều", "Khoản", "Điểm")):
        return f"{unit_path} {source_title}"
    return f"{source_title}, {unit_path}"


class DenseRetriever(Protocol):
    def search(self, query: str, jurisdictions: list[str], k: int) -> list[str]: ...


def terms(textish: str) -> list[str]:
    seen: list[str] = []
    for w in _WORD.findall(unicodedata.normalize("NFC", textish).lower()):
        if w not in _STOP and w not in seen:
            seen.append(w)
    return seen


def _in_force(as_of: date) -> str:
    return (
        "u.status <> 'repealed' AND (u.effective_from IS NULL OR u.effective_from <= :as_of)"
        " AND (u.effective_to IS NULL OR u.effective_to > :as_of)"
    )


_SELECT = (
    "SELECT u.id, u.source_id, s.title, u.unit_path, u.heading, u.text, u.status,"
    " u.effective_from, u.effective_to, s.is_fixture, s.review_status"
)


def search(
    session: Session,
    query: str,
    *,
    jurisdictions: list[str],
    as_of: date,
    k: int = 5,
    rerank_with: str | None = None,
    dense: DenseRetriever | None = None,
    require_verified: bool = False,
) -> list[LegalUnitHit]:
    """`require_verified` limits results to sources a lawyer has checked (ADR-019); pilots
    run with it on."""
    words = terms(query)[:24]
    if not words or not jurisdictions:
        return []
    tsquery = " | ".join(words)
    # Match the text as written or without tone marks (tsv_plain, migration 0008).
    rows = session.execute(
        text(
            f"{_SELECT}, GREATEST(ts_rank_cd(u.tsv, to_tsquery('simple', :q)),"
            " ts_rank_cd(u.tsv_plain, to_tsquery('simple', f_unaccent(:q)))) AS rank"
            " FROM legal_units u JOIN legal_sources s ON s.id = u.source_id"
            " WHERE (u.tsv @@ to_tsquery('simple', :q)"
            " OR u.tsv_plain @@ to_tsquery('simple', f_unaccent(:q)))"
            " AND s.jurisdiction = ANY(:j)"
            f" AND {_in_force(as_of)}"
            + (" AND s.review_status = 'verified'" if require_verified else "")
            + " ORDER BY rank DESC LIMIT :n"
        ),
        {"q": tsquery, "j": jurisdictions, "as_of": as_of, "n": k * 4},
    ).all()
    hits = [_hit(r[:11], float(r[11])) for r in rows]
    if dense is not None:
        hits = _rrf(
            hits, dense.search(query, jurisdictions, k * 4), session, as_of, require_verified
        )
    if rerank_with:
        hits = rerank(rerank_with, hits)
    return hits[:k]


def rerank(context: str, hits: list[LegalUnitHit]) -> list[LegalUnitHit]:
    """Lexical-overlap reranker; replaced by a cross-encoder (T0) when available."""
    ctx = set(terms(context))
    if not ctx:
        return hits
    scored = []
    for h in hits:
        unit_terms = set(terms(h.heading + " " + h.text))
        overlap = len(ctx & unit_terms) / (len(ctx) ** 0.5 * max(len(unit_terms), 1) ** 0.5)
        scored.append((overlap + h.score, h))
    scored.sort(key=lambda t: -t[0])
    return [h for _, h in scored]


def get_unit(session: Session, unit_id: str) -> LegalUnitHit | None:
    row = session.execute(
        text(
            f"{_SELECT} FROM legal_units u JOIN legal_sources s ON s.id = u.source_id"
            " WHERE u.id = :id"
        ),
        {"id": unit_id},
    ).first()
    return _hit(row) if row else None


def _hit(r: Any, score: float = 0.0) -> LegalUnitHit:
    return LegalUnitHit(
        id=r[0],
        source_id=r[1],
        source_title=r[2],
        unit_path=r[3],
        heading=r[4],
        text=r[5],
        status=r[6],
        effective_from=r[7],
        effective_to=r[8],
        is_fixture=r[9],
        review_status=r[10],
        score=score,
    )


def is_in_force(unit: LegalUnitHit, as_of: date) -> bool:
    if unit.status == "repealed":
        return False
    if unit.effective_from and unit.effective_from > as_of:
        return False
    return not (unit.effective_to and unit.effective_to <= as_of)


def _rrf(
    lexical: list[LegalUnitHit],
    dense_ids: list[str],
    session: Session,
    as_of: date,
    require_verified: bool = False,
) -> list[LegalUnitHit]:
    scores: dict[str, float] = {}
    by_id = {h.id: h for h in lexical}
    for rank, h in enumerate(lexical):
        scores[h.id] = scores.get(h.id, 0) + 1 / (60 + rank)
    for rank, uid in enumerate(dense_ids):
        scores[uid] = scores.get(uid, 0) + 1 / (60 + rank)
        if uid not in by_id:
            unit = get_unit(session, uid)
            if (
                unit
                and is_in_force(unit, as_of)
                and (not require_verified or unit.review_status == "verified")
            ):
                by_id[uid] = unit
    return [by_id[i] for i in sorted(scores, key=lambda i: -scores[i]) if i in by_id]
