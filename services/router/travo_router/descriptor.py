"""Task Descriptor: the router's input contract (docs/03 §3)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal[
    "classify",
    "clause_extraction",
    "playbook_compare",
    "law_check",
    "redline",
    "memo",
    "embed",
    "rerank",
    "validate_claim",
    "bilingual_check",
]
Tier = Literal["T0", "T1", "T2"]
Capability = Literal["tool_use", "long_context", "vision", "json_output"]


class TaskDescriptor(BaseModel):
    task_type: TaskType
    tenant_id: str
    matter_id: str | None = None
    jurisdictions: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    est_input_tokens: int = 0
    est_output_tokens: int = 0
    sensitivity: Literal["standard", "high", "restricted"] = "standard"
    latency_class: Literal["interactive", "batch"] = "batch"
    quality_floor: Literal["standard", "high"] = "standard"
    requires: list[Capability] = Field(default_factory=list)
    attempt: int = 1
    escalation_reason: str | None = None
