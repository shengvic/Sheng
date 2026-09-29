"""Request/response models for the public API (docs/09 §2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MatterCreate(BaseModel):
    number: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    jurisdictions: list[Literal["SG", "MY", "VN", "ID"]] = Field(default_factory=list)
    residency: Literal["SG", "MY", "VN", "ID"] | None = None
    deny_providers: list[str] = Field(default_factory=list)
    allow_providers: list[str] | None = None
    budget_usd: float | None = Field(default=None, ge=0)


class MatterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    number: str
    name: str
    jurisdictions: list[str]
    residency: str | None
    deny_providers: list[str]
    allow_providers: list[str] | None
    status: str
    created_at: datetime


class MemberIn(BaseModel):
    user_id: uuid.UUID
    access: Literal["member", "screened"] = "member"


class MembersPut(BaseModel):
    members: list[MemberIn]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    matter_id: uuid.UUID
    filename: str
    mime: str
    size_bytes: int
    sha256: str
    languages: list[str]
    contract_type: str | None
    contract_type_confidence: float | None
    governing_law: str | None
    parties: list[str]
    parse_status: str
    error: str | None
    created_at: datetime


class ClauseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    idx: int
    number: str | None
    heading: str
    text: str
    taxonomy_key: str
    confidence: float


class PolicyIn(BaseModel):
    yaml: str = Field(max_length=100_000)


class PolicyOut(BaseModel):
    version: int
    yaml: str
    source: Literal["tenant", "default"]


class DryRunIn(BaseModel):
    task_type: str
    matter_id: uuid.UUID | None = None
    est_input_tokens: int = 10_000
    est_output_tokens: int = 1_000
    sensitivity: Literal["standard", "high", "restricted"] = "standard"
    escalation_reason: str | None = None
    yaml: str | None = None  # test an unsaved policy


class CredentialIn(BaseModel):
    provider: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_-]+$")
    api_key: str = Field(min_length=8, max_length=512)


class CredentialOut(BaseModel):
    provider: str
    last4: str
    status: str


class RoutingDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    matter_id: uuid.UUID | None
    document_id: uuid.UUID | None
    task_type: str
    chosen_endpoint: str | None
    chosen_tier: str | None
    outcome: str
    candidates: list[Any]
    filtered: list[Any]
    attempts: list[Any]
    cost_usd: float
    latency_ms: int
    created_at: datetime


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    matter_id: uuid.UUID | None
    result: str
    details: dict[str, Any]
    created_at: datetime


class ReviewStart(BaseModel):
    playbook_key: str | None = Field(default=None, max_length=80)


class ReviewStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    idx: int
    name: str
    status: str
    attempts: int
    error: str | None
    output: dict[str, Any]


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    matter_id: uuid.UUID
    document_id: uuid.UUID
    playbook_key: str
    playbook_version: int
    playbook_source: str
    status: str
    attempts: int
    error: str | None
    cost_usd: float
    summary: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None
    steps: list[ReviewStepOut] = Field(default_factory=list)


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    claim_text: str
    source_unit_id: str | None
    pinpoint: str | None
    status: str
    score: float
    checker: str
    override_reason: str | None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    clause_id: uuid.UUID | None
    clause_key: str
    rule_key: str
    kind: str
    classification: str
    severity: str
    summary: str
    rationale: str
    suggested_redline: str | None
    confidence: float
    model_tier: str | None
    escalated: bool
    status: str
    disposition: str | None
    edited_text: str | None
    reason_code: str | None
    note: str | None
    citations: list[CitationOut] = Field(default_factory=list)


REASON_CODES = (
    "wrong_clause_type",
    "playbook_misapplied",
    "law_incorrect",
    "law_outdated",
    "too_aggressive",
    "too_lenient",
    "drafting_style",
    "missing_issue",
    "not_relevant_to_client",
    "other",
)


class DispositionIn(BaseModel):
    action: Literal["accept", "edit", "reject", "defer"]
    edited_text: str | None = Field(default=None, max_length=20_000)
    reason_code: Literal[REASON_CODES] | None = None  # type: ignore[valid-type]
    note: str | None = Field(default=None, max_length=4000)


class OverrideIn(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class ExportIn(BaseModel):
    format: Literal["redline_docx", "memo_docx"]


class ExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    format: str
    filename: str
    sha256: str
    created_at: datetime


class PlaybookIn(BaseModel):
    yaml: str | None = Field(default=None, max_length=200_000)
    from_starter: str | None = Field(default=None, max_length=80)
    key: str | None = Field(default=None, pattern=r"^[a-z0-9_]{2,80}$")


class PlaybookOut(BaseModel):
    key: str
    version: int
    name: str
    source: Literal["tenant", "starter"]
    contract_types: list[str]
    governing_laws: list[str]
    rules: int
    spec: dict[str, Any] | None = None
