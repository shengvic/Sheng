"""Classifier agent: contract type, governing law, parties (docs/05 §2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from travo_agents.base import AgentContext, call_json
from travo_agents.prompts import load_prompt
from travo_agents.taxonomy import CONTRACT_TYPES, GOVERNING_LAW_HINTS

SYSTEM = (
    load_prompt("classify")
    .replace("{contract_types}", ", ".join([*CONTRACT_TYPES, "OTHER"]))
    .replace("{governing_laws}", ", ".join(GOVERNING_LAW_HINTS))
)


class Classification(BaseModel):
    contract_type: str = "OTHER"
    contract_type_confidence: float = Field(0.0, ge=0, le=1)
    governing_law: str | None = None
    governing_law_confidence: float = Field(0.0, ge=0, le=1)
    parties: list[str] = Field(default_factory=list)


def classify(ctx: AgentContext, text: str) -> Classification:
    raw: dict[str, Any] = call_json(ctx, "classify", SYSTEM, {"text": text[:12000]}, 300).data
    c = Classification.model_validate(raw)
    if c.contract_type not in CONTRACT_TYPES:
        c.contract_type = "OTHER"
    if c.governing_law not in GOVERNING_LAW_HINTS:
        c.governing_law = None
    return c
