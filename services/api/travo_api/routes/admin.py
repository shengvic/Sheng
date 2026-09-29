from __future__ import annotations

import uuid

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from travo_router import ModelPolicy, RoutingPlan, TaskDescriptor

from travo_api.audit import audit
from travo_api.auth import Actor, require_admin
from travo_api.keys import encrypt_idp_secret, store_credential
from travo_api.models import (
    AuditEvent,
    AuthSession,
    IdpDomain,
    ModelPolicyRow,
    ProviderCredential,
    RoutingDecision,
    TenantIdp,
    User,
)
from travo_api.routing import DbRouterContext, default_policy_yaml, get_router
from travo_api.schemas import (
    AuditOut,
    AuthSessionOut,
    CredentialIn,
    CredentialOut,
    DryRunIn,
    EndpointOut,
    IdpIn,
    IdpOut,
    PolicyIn,
    PolicyOut,
    RoutingDecisionOut,
)
from travo_api.sessions import revoke

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


@router.delete("/provider-credentials/{provider}", status_code=204)
def revoke_credential(provider: str, actor: Actor = Depends(require_admin)) -> None:
    row = actor.session.scalar(
        select(ProviderCredential).where(ProviderCredential.provider == provider)
    )
    if row is None:
        raise HTTPException(404, "not found")
    row.status = "revoked"
    row.ciphertext = b""  # destroy the key material, keep the audit trail
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="provider_credential.revoked",
        resource_type="provider_credential",
        resource_id=provider,
    )


@router.get("/endpoints", response_model=list[EndpointOut])
def endpoints(actor: Actor = Depends(require_admin)) -> list[EndpointOut]:
    return [
        EndpointOut(
            id=e.id,
            provider=e.provider,
            via=e.via,
            model=e.model,
            tier=e.tier,
            billing=e.billing,
            regions=e.regions,
            enabled=e.enabled,
        )
        for e in get_router().registry.all()
    ]


def _idp_out(actor: Actor, row: TenantIdp) -> IdpOut:
    domains = list(
        actor.session.scalars(
            select(IdpDomain.domain).where(IdpDomain.idp_id == row.id).order_by(IdpDomain.domain)
        )
    )
    return IdpOut(
        id=row.id,
        issuer=row.issuer,
        client_id=row.client_id,
        has_client_secret=bool(row.client_secret_ciphertext),
        email_domains=domains,
        enabled=row.enabled,
        updated_at=row.updated_at,
    )


@router.get("/idp", response_model=IdpOut | None)
def get_idp(actor: Actor = Depends(require_admin)) -> IdpOut | None:
    row = actor.session.scalar(select(TenantIdp))
    return _idp_out(actor, row) if row else None


@router.put("/idp", response_model=IdpOut)
def put_idp(body: IdpIn, actor: Actor = Depends(require_admin)) -> IdpOut:
    domains = sorted({d.strip().lower().lstrip("@") for d in body.email_domains if d.strip()})
    if not domains or any("." not in d or "/" in d or "@" in d for d in domains):
        raise HTTPException(422, "email_domains must be domains like firm.com.sg")
    s = actor.session
    row = s.scalar(select(TenantIdp))
    if row is None:
        row = TenantIdp(
            tenant_id=uuid.UUID(actor.tenant_id), issuer=body.issuer, client_id=body.client_id
        )
        s.add(row)
        s.flush()
    row.issuer, row.client_id, row.enabled = body.issuer.rstrip("/"), body.client_id, body.enabled
    if body.client_secret:
        row.client_secret_ciphertext = encrypt_idp_secret(
            s, actor.tenant_id, row.id, body.client_secret
        )
    row.updated_at = func.now()
    s.execute(delete(IdpDomain).where(IdpDomain.idp_id == row.id))
    try:
        with s.begin_nested():  # savepoint: a clash must not poison the request transaction
            for d in domains:
                s.add(IdpDomain(domain=d, idp_id=row.id, tenant_id=row.tenant_id))
            s.flush()
    except IntegrityError:
        raise HTTPException(409, "an email domain is already registered to another firm") from None
    s.refresh(row)
    audit(
        s,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="idp.updated",
        resource_type="idp",
        resource_id=row.id,
        details={
            "issuer": row.issuer,
            "domains": domains,
            "enabled": row.enabled,
            "secret_changed": bool(body.client_secret),
        },
    )
    return _idp_out(actor, row)


@router.get("/sessions", response_model=list[AuthSessionOut])
def list_sessions(actor: Actor = Depends(require_admin)) -> list[AuthSessionOut]:
    rows = actor.session.execute(
        select(AuthSession, User.email)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > func.now())
        .order_by(AuthSession.created_at.desc())
        .limit(200)
    ).all()
    out = []
    for sess, email in rows:
        o = AuthSessionOut.model_validate(sess)
        o.user_email, o.current = email, sess.id == actor.session_id
        out.append(o)
    return out


@router.post("/sessions/{session_id}/revoke", status_code=204)
def revoke_session(session_id: uuid.UUID, actor: Actor = Depends(require_admin)) -> None:
    if not revoke(actor.session, session_id):
        raise HTTPException(404, "not found")
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="auth.session_revoked",
        resource_type="session",
        resource_id=session_id,
    )
