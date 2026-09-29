"""Bearer-token auth. Travo tokens are HS256, issued by the API itself: session tokens after
SSO sign-in (carry `sid`, checked against `auth_sessions`), or dev tokens (no `sid`, only when
`allow_dev_tokens`). The browser never holds either — the web BFF keeps it in an httpOnly
cookie (ADR-018)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from travo_api.config import get_settings
from travo_api.db import tenant_session
from travo_api.models import User
from travo_api.sessions import session_is_live

_bearer = HTTPBearer(auto_error=False)


@dataclass
class Actor:
    user: User
    tenant_id: str
    session: Session
    session_id: uuid.UUID | None = None

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"


def decode_token(token: str) -> dict[str, object]:
    s = get_settings()
    if not s.jwt_secret:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "auth not configured")
    opts: Any = {"require": ["exp", "sub", "tid"]}
    return jwt.decode(
        token,
        s.jwt_secret,
        algorithms=["HS256"],
        audience=s.jwt_audience,
        issuer=s.jwt_issuer,
        options=opts,
    )


def mint_dev_token(user_id: str, tenant_id: str, ttl_s: int = 3600) -> str:
    s = get_settings()
    now = int(time.time())
    claims = {
        "sub": user_id,
        "tid": tenant_id,
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "iat": now,
        "exp": now + ttl_s,
    }
    return jwt.encode(claims, s.jwt_secret, algorithm="HS256")


def get_actor(
    request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)
) -> Iterator[Actor]:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = decode_token(creds.credentials)
        tenant_id = str(uuid.UUID(str(claims["tid"])))
        user_id = uuid.UUID(str(claims["sub"]))
        sid = uuid.UUID(str(claims["sid"])) if "sid" in claims else None
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from None
    if sid is None and not get_settings().allow_dev_tokens:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "dev tokens are disabled")
    with tenant_session(tenant_id) as session:
        user = session.get(User, user_id)  # RLS: only visible within its own tenant
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
        if sid is not None and not session_is_live(session, sid, user_id):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired or revoked")
        actor = Actor(user=user, tenant_id=tenant_id, session=session, session_id=sid)
        request.state.actor = actor
        yield actor


def require_admin(actor: Actor = Depends(get_actor)) -> Actor:
    if not actor.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return actor
