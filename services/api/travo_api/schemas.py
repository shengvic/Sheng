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
