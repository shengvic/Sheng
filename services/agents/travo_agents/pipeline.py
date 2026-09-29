"""P0 review pipeline: ingest → classify → extract (synchronous; Temporal in P1)."""

from __future__ import annotations

from dataclasses import dataclass

from travo_rag.parsing import Block, detect_languages
from travo_rag.segmentation import segment

from travo_agents.base import AgentContext
from travo_agents.classify import Classification, classify
from travo_agents.extract import LabeledClause, extract


@dataclass
class PipelineResult:
    languages: list[str]
    classification: Classification
    clauses: list[LabeledClause]


def run_pipeline(ctx: AgentContext, blocks: list[Block]) -> PipelineResult:
    full_text = "\n".join(b.text for b in blocks)
    languages = detect_languages(full_text)
    ctx.languages = languages
    classification = classify(ctx, full_text)
    if classification.governing_law and classification.governing_law not in ctx.jurisdictions:
        ctx.jurisdictions = [*ctx.jurisdictions, classification.governing_law]
    clauses = extract(ctx, segment(blocks))
    return PipelineResult(languages=languages, classification=classification, clauses=clauses)
