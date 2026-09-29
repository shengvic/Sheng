"""Flywheel telemetry (docs/07 §2). Append-only; carries ids and structured fields, not
document text, except the lawyer's own edited wording (needed for firm-private learning)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from travo_api.models import TelemetryEvent


def emit(
    session: Session,
    *,
    tenant_id: str | uuid.UUID,
    event_type: str,
    matter_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    subject_id: object | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        TelemetryEvent(
            tenant_id=uuid.UUID(str(tenant_id)),
            matter_id=matter_id,
            event_type=event_type,
            actor_id=actor_id,
            subject_id=str(subject_id) if subject_id is not None else None,
            payload=payload or {},
        )
    )
