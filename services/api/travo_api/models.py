"""ORM models (docs/09). Schema, RLS and grants live in migrations/versions/0001_*.py."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def _tenant_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    region_cell: Mapped[str] = mapped_column(String(8))
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = _created()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    idp_subject: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created()


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    name: Mapped[str] = mapped_column(String(200))
    ai_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class Matter(Base):
    __tablename__ = "matters"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id")
    )
    number: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(300))
    jurisdictions: Mapped[list[str]] = mapped_column(ARRAY(String(8)), default=list)
    residency: Mapped[str | None] = mapped_column(String(8))
    deny_providers: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    allow_providers: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)))
    budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()


class MatterMember(Base):
    __tablename__ = "matter_members"
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matters.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    access: Mapped[str] = mapped_column(String(10))  # member | screened


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matters.id"))
    filename: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_ref: Mapped[str] = mapped_column(String(300))
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(8)), default=list)
    contract_type: Mapped[str | None] = mapped_column(String(32))
    contract_type_confidence: Mapped[float | None] = mapped_column(Float)
    governing_law: Mapped[str | None] = mapped_column(String(8))
    parties: Mapped[list[str]] = mapped_column(JSONB, default=list)
    parse_status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()


class Clause(Base):
    __tablename__ = "clauses"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matters.id"))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"))
    idx: Mapped[int] = mapped_column(Integer)
    number: Mapped[str | None] = mapped_column(String(32))
    heading: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    taxonomy_key: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)


class ModelPolicyRow(Base):
    __tablename__ = "model_policies"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    version: Mapped[int] = mapped_column(Integer)
    yaml: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    provider: Mapped[str] = mapped_column(String(64))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    last4: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = _created()


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    task_type: Mapped[str] = mapped_column(String(32))
    descriptor: Mapped[dict[str, Any]] = mapped_column(JSONB)
    candidates: Mapped[list[Any]] = mapped_column(JSONB)
    filtered: Mapped[list[Any]] = mapped_column(JSONB)
    attempts: Mapped[list[Any]] = mapped_column(JSONB)
    chosen_endpoint: Mapped[str | None] = mapped_column(String(128))
    chosen_tier: Mapped[str | None] = mapped_column(String(4))
    outcome: Mapped[str] = mapped_column(String(32))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _created()


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    matter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    result: Mapped[str] = mapped_column(String(16))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class LegalSource(Base):
    __tablename__ = "legal_sources"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    jurisdiction: Mapped[str] = mapped_column(String(8))
    instrument_type: Mapped[str] = mapped_column(String(40))
    number: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(Text)
    issuing_body: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="en")
    official_url: Mapped[str | None] = mapped_column(Text)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(12), default="unverified")
    verified_by: Mapped[str | None] = mapped_column(String(320))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_note: Mapped[str | None] = mapped_column(Text)
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LegalUnit(Base):
    __tablename__ = "legal_units"
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(160), ForeignKey("legal_sources.id"))
    unit_path: Mapped[str] = mapped_column(String(160))
    heading: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="in_force")
    version_hash: Mapped[str] = mapped_column(String(64))


class PlaybookRow(Base):
    __tablename__ = "playbooks"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    key: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    contract_types: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    governing_laws: Mapped[list[str]] = mapped_column(ARRAY(String(8)), default=list)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _created()


class ReviewRun(Base):
    __tablename__ = "review_runs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    playbook_key: Mapped[str] = mapped_column(String(80))
    playbook_version: Mapped[int] = mapped_column(Integer)
    playbook_source: Mapped[str] = mapped_column(String(10))
    playbook_spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    lease_owner: Mapped[str | None] = mapped_column(String(80))
    lease_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewStep(Base):
    __tablename__ = "review_steps"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    idx: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    clause_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    clause_key: Mapped[str] = mapped_column(String(64))
    rule_key: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10))
    classification: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(8))
    summary: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    suggested_redline: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    model_tier: Mapped[str | None] = mapped_column(String(4))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="needs_review")
    disposition: Mapped[str | None] = mapped_column(String(10))
    edited_text: Mapped[str | None] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text)
    disposition_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    disposition_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class Citation(Base):
    __tablename__ = "citations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    claim_text: Mapped[str] = mapped_column(Text)
    source_unit_id: Mapped[str | None] = mapped_column(String(240))
    pinpoint: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    checker: Mapped[str] = mapped_column(String(128))
    override_reason: Mapped[str | None] = mapped_column(Text)
    overridden_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _created()


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(48))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subject_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _created()


class Export(Base):
    __tablename__ = "exports"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    format: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(300))
    storage_ref: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _created()


class TenantIdp(Base):
    __tablename__ = "tenant_idps"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    issuer: Mapped[str] = mapped_column(Text)
    client_id: Mapped[str] = mapped_column(Text)
    client_secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdpDomain(Base):
    __tablename__ = "idp_domains"
    domain: Mapped[str] = mapped_column(String(253), primary_key=True)
    idp_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    method: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(300))
