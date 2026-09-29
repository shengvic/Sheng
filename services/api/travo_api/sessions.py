"""Server-side sessions behind Travo session tokens (ADR-018)."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy.orm import Session

from travo_api.config import get_settings
from travo_api.models import AuthSession


def create_session(
    session: Session, tenant_id: str, user_id: uuid.UUID, method: str, user_agent: str | None
) -> tuple[AuthSession, str]:
    s = get_settings()
    ttl = s.session_ttl_seconds
    row = AuthSession(
        tenant_id=uuid.UUID(tenant_id),
        user_id=user_id,
        method=method,
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
        user_agent=(user_agent or "")[:300] or None,
    )
    session.add(row)
    session.flush()
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": str(user_id),
            "tid": tenant_id,
            "sid": str(row.id),
            "iss": s.jwt_issuer,
            "aud": s.jwt_audience,
            "iat": now,
            "exp": now + ttl,
        },
        s.jwt_secret,
        algorithm="HS256",
    )
    return row, token


def session_is_live(session: Session, sid: uuid.UUID, user_id: uuid.UUID) -> bool:
    row = session.get(AuthSession, sid)
    return (
        row is not None
        and row.user_id == user_id
        and row.revoked_at is None
        and row.expires_at > datetime.now(UTC)
    )


def revoke(session: Session, sid: uuid.UUID) -> bool:
    row = session.get(AuthSession, sid)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    return True
