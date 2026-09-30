"""SSO sign-in (OIDC auth code + PKCE) and sessions (ADR-018).

The web BFF drives the browser redirects; the API does discovery, the code exchange (client
secrets never leave the API), id_token validation and user mapping, then issues a session token
the BFF keeps in an httpOnly cookie. No JIT provisioning: the user must already exist.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, text

from travo_api import oidc
from travo_api.audit import audit
from travo_api.auth import Actor, get_actor
from travo_api.db import get_engine, tenant_session
from travo_api.keys import decrypt_idp_secret
from travo_api.models import Tenant, TenantIdp, User
from travo_api.ratelimit import auth_rate_limit
from travo_api.schemas import MeOut, OidcCallbackIn, OidcStartIn, OidcStartOut, SessionOut
from travo_api.sessions import create_session, revoke

router = APIRouter(prefix="/v1/auth", tags=["auth"])
GENERIC = "sign-in failed"


def _lookup(sql: str, **params: object) -> tuple[uuid.UUID, str, str, str] | None:
    with get_engine().begin() as conn:  # no tenant context: only the lookup functions work
        row = conn.execute(text(sql), params).first()
    return (row[0], str(row[1]), row[2], row[3]) if row else None


@router.post("/oidc/start", response_model=OidcStartOut, dependencies=[Depends(auth_rate_limit)])
def oidc_start(body: OidcStartIn) -> OidcStartOut:
    domain = body.email.rsplit("@", 1)[1].lower()
    idp = _lookup("SELECT * FROM idp_for_email_domain(:d)", d=domain)
    if idp is None:
        raise HTTPException(404, "single sign-on is not set up for this email domain")
    idp_id, _tenant, issuer, client_id = idp
    try:
        doc = oidc.discovery(issuer)
    except oidc.OidcError:
        raise HTTPException(502, "identity provider unavailable") from None
    return OidcStartOut(
        idp_id=idp_id, authorization_endpoint=doc["authorization_endpoint"], client_id=client_id
    )


@router.post("/oidc/callback", response_model=SessionOut, dependencies=[Depends(auth_rate_limit)])
def oidc_callback(body: OidcCallbackIn, request: Request) -> SessionOut:
    idp = _lookup("SELECT * FROM idp_by_id(:i)", i=body.idp_id)
    if idp is None:
        raise HTTPException(401, GENERIC)
    idp_id, tenant_id, issuer, client_id = idp
    ua = request.headers.get("user-agent")
    with tenant_session(tenant_id) as s:
        row = s.get(TenantIdp, idp_id)
        assert row is not None
        secret = (
            decrypt_idp_secret(s, tenant_id, idp_id, row.client_secret_ciphertext)
            if row.client_secret_ciphertext
            else None
        )
    try:
        doc = oidc.discovery(issuer)
        tokens = oidc.exchange_code(
            doc, client_id, secret, body.code, body.code_verifier, body.redirect_uri
        )
        ident = oidc.verify_id_token(doc, tokens["id_token"], client_id, body.nonce)
    except oidc.OidcError as exc:
        _fail(tenant_id, str(exc), None)
        raise HTTPException(401, GENERIC) from None

    with tenant_session(tenant_id) as s:
        user = s.scalar(select(User).where(User.idp_subject == ident.subject))
        if user is None and ident.email:
            user = s.scalar(select(User).where(func.lower(User.email) == ident.email))
            if user is not None and user.idp_subject not in (None, ident.subject):
                user = None  # email re-assigned to a different IdP identity: refuse
            if user is not None:
                user.idp_subject = ident.subject  # bind on first SSO sign-in
        if user is None:
            reason = "no Travo user for this identity"
        else:
            sess, token = create_session(s, tenant_id, user.id, "oidc", ua)
            tenant = s.get(Tenant, user.tenant_id)
            audit(
                s,
                tenant_id=tenant_id,
                actor_id=user.id,
                action="auth.login",
                resource_type="session",
                resource_id=sess.id,
                details={"method": "oidc"},
            )
            return SessionOut(
                token=token,
                expires_at=sess.expires_at,
                user=MeOut(
                    id=user.id,
                    email=user.email,
                    name=user.name,
                    role=user.role,
                    tenant_id=user.tenant_id,
                    tenant_name=tenant.name if tenant else "",
                ),
            )
    _fail(tenant_id, reason, ident.email)
    raise HTTPException(401, GENERIC)


def _fail(tenant_id: str, reason: str, email: str | None) -> None:
    with tenant_session(tenant_id) as s:
        audit(
            s,
            tenant_id=tenant_id,
            actor_id=None,
            action="auth.login_failed",
            resource_type="session",
            result="denied",
            details={"reason": reason, "email": email},
        )


@router.post("/logout", status_code=204)
def logout(actor: Actor = Depends(get_actor)) -> None:
    if actor.session_id is not None and revoke(actor.session, actor.session_id):
        audit(
            actor.session,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="auth.logout",
            resource_type="session",
            resource_id=actor.session_id,
        )
