"""Append-only audit trail (docs/06 §4). DB triggers reject UPDATE/DELETE."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from travo_api.models import AuditEvent


def audit(
    session: Session,
    *,
    tenant_id: str,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: object | None = None,
    matter_id: uuid.UUID | None = None,
    result: str = "ok",
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            tenant_id=uuid.UUID(tenant_id),
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            matter_id=matter_id,
            result=result,
            details=details or {},
        )
    )
