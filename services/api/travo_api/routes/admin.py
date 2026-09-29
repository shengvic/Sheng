from __future__ import annotations

import uuid

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, select, update
from travo_router import ModelPolicy, RoutingPlan, TaskDescriptor

from travo_api.audit import audit
from travo_api.auth import Actor, require_admin
from travo_api.keys import store_credential
from travo_api.models import AuditEvent, ModelPolicyRow, ProviderCredential, RoutingDecision
from travo_api.routing import DbRouterContext, default_policy_yaml, get_router
from travo_api.schemas import (
    AuditOut,
    CredentialIn,
    CredentialOut,
    DryRunIn,
    PolicyIn,
    PolicyOut,
    RoutingDecisionOut,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _parse_policy(text: str) -> ModelPolicy:
    try:
        return ModelPolicy.from_yaml(text)
    except (yaml.YAMLError, ValidationError) as exc:
        raise HTTPException(422, f"invalid policy: {exc}") from None


@router.get("/model-policy", response_model=PolicyOut)
def get_policy(actor: Actor = Depends(require_admin)) -> PolicyOut:
    row = actor.session.scalar(select(ModelPolicyRow).where(ModelPolicyRow.active.is_(True)))
    if row is None:
        return PolicyOut(version=0, yaml=default_policy_yaml(), source="default")
    return PolicyOut(version=row.version, yaml=row.yaml, source="tenant")


@router.put("/model-policy", response_model=PolicyOut)
def put_policy(body: PolicyIn, actor: Actor = Depends(require_admin)) -> PolicyOut:
    _parse_policy(body.yaml)
    s = actor.session
    version = (s.scalar(select(func.max(ModelPolicyRow.version))) or 0) + 1
    s.execute(update(ModelPolicyRow).where(ModelPolicyRow.active.is_(True)).values(active=False))
    s.add(
        ModelPolicyRow(
            tenant_id=uuid.UUID(actor.tenant_id),
            version=version,
            yaml=body.yaml,
            active=True,
            created_by=actor.user_id,
        )
    )
    audit(
        s,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="model_policy.updated",
        resource_type="model_policy",
        resource_id=version,
    )
    return PolicyOut(version=version, yaml=body.yaml, source="tenant")


@router.post("/model-policy/dry-run", response_model=RoutingPlan)
def dry_run(body: DryRunIn, actor: Actor = Depends(require_admin)) -> RoutingPlan:
    ctx = DbRouterContext(actor.session, actor.tenant_id)
    if body.yaml is not None:
        override = _parse_policy(body.yaml)
        ctx.policy = lambda: override  # type: ignore[method-assign]
    try:
        descriptor = TaskDescriptor(
            task_type=body.task_type,  # type: ignore[arg-type]
            tenant_id=actor.tenant_id,
            matter_id=str(body.matter_id) if body.matter_id else None,
            est_input_tokens=body.est_input_tokens,
            est_output_tokens=body.est_output_tokens,
            sensitivity=body.sensitivity,
            escalation_reason=body.escalation_reason,
        )
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from None
    return get_router().plan(descriptor, ctx)


@router.post("/provider-credentials", response_model=CredentialOut, status_code=201)
def put_credential(body: CredentialIn, actor: Actor = Depends(require_admin)) -> CredentialOut:
    store_credential(actor.session, actor.tenant_id, body.provider, body.api_key)
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="provider_credential.stored",
        resource_type="provider_credential",
        resource_id=body.provider,
    )
    return CredentialOut(provider=body.provider, last4=body.api_key[-4:], status="active")


@router.get("/provider-credentials", response_model=list[CredentialOut])
def list_credentials(actor: Actor = Depends(require_admin)) -> list[CredentialOut]:
    rows = actor.session.scalars(select(ProviderCredential).order_by(ProviderCredential.provider))
    return [CredentialOut(provider=r.provider, last4=r.last4, status=r.status) for r in rows]


@router.get("/routing-decisions", response_model=list[RoutingDecisionOut])
def list_routing_decisions(
    matter_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=500),
    actor: Actor = Depends(require_admin),
) -> list[RoutingDecision]:
    q = select(RoutingDecision).order_by(RoutingDecision.created_at.desc()).limit(limit)
    if matter_id:
        q = q.where(RoutingDecision.matter_id == matter_id)
    return list(actor.session.scalars(q))


@router.get("/audit", response_model=list[AuditOut])
def list_audit(
    action: str | None = None,
    matter_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=1000),
    actor: Actor = Depends(require_admin),
) -> list[AuditEvent]:
    q = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if action:
        q = q.where(AuditEvent.action == action)
    if matter_id:
        q = q.where(AuditEvent.matter_id == matter_id)
    return list(actor.session.scalars(q))


@router.get("/spend")
def spend(actor: Actor = Depends(require_admin)) -> dict[str, object]:
    """Cost per matter, per task type and tier share (docs/08 §3.5)."""
    s = actor.session

    def grouped(col):  # type: ignore[no-untyped-def]
        rows = s.execute(
            select(
                col, func.coalesce(func.sum(RoutingDecision.cost_usd), 0), func.count()
            ).group_by(col)
        ).all()
        return [
            {"key": str(k) if k is not None else None, "cost_usd": float(c), "calls": int(n)}
            for k, c, n in rows
        ]

    return {
        "by_matter": grouped(RoutingDecision.matter_id),
        "by_task": grouped(RoutingDecision.task_type),
        "by_tier": grouped(RoutingDecision.chosen_tier),
    }
