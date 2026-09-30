"""Clause extractor agent: map segments to the clause taxonomy (docs/05 §2)."""

from __future__ import annotations

from pydantic import BaseModel
from travo_rag.segmentation import Segment

from travo_agents.base import AgentContext, AgentOutputError, call_json
from travo_agents.prompts import load_prompt
from travo_agents.taxonomy import CLAUSE_KEYS, CLAUSE_TAXONOMY

SYSTEM = load_prompt("clause_extraction").replace(
    "{taxonomy}", "; ".join(f"{k} = {d}" for k, (d, _) in CLAUSE_TAXONOMY.items())
)
BATCH = 25


class LabeledClause(BaseModel):
    index: int
    number: str | None
    heading: str
    text: str
    key: str
    confidence: float
    heading_alt: str = ""  # the clause's other-language version (bilingual contracts)
    text_alt: str = ""


def extract(ctx: AgentContext, segments: list[Segment]) -> list[LabeledClause]:
    labels: dict[int, tuple[str, float]] = {}
    for start in range(0, len(segments), BATCH):
        batch = segments[start : start + BATCH]
        # Both language versions help labelling (hints exist in en and vi).
        payload = {
            "clauses": [
                {
                    "i": s.index,
                    "heading": " / ".join(h for h in (s.heading, s.heading_alt) if h),
                    "text": "\n".join(t for t in (s.text, s.text_alt) if t)[:1500],
                }
                for s in batch
            ]
        }
        out = call_json(ctx, "clause_extraction", SYSTEM, payload, est_output=30 * len(batch)).data
        items = out.get("clauses")
        if not isinstance(items, list):
            raise AgentOutputError("clause_extraction output missing 'clauses' list")
        for item in items:
            try:
                i, key, conf = int(item["i"]), str(item["key"]), float(item.get("confidence", 0))
            except (KeyError, TypeError, ValueError):
                continue
            labels[i] = (key if key in CLAUSE_KEYS else "other", max(0.0, min(conf, 1.0)))
    return [
        LabeledClause(
            index=s.index,
            number=s.number,
            heading=s.heading,
            text=s.text,
            key=labels.get(s.index, ("other", 0.0))[0],
            confidence=labels.get(s.index, ("other", 0.0))[1],
            heading_alt=s.heading_alt,
            text_alt=s.text_alt,
        )
        for s in segments
    ]
