"""Ethical walls: matter access is membership-based for everyone, admins included (docs/06 §3)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select

from travo_api.audit import audit
from travo_api.auth import Actor
from travo_api.models import Document, Matter, MatterMember


def _not_found() -> HTTPException:
    # 404, not 403: do not reveal that a walled matter exists.
    return HTTPException(status.HTTP_404_NOT_FOUND, "not found")


def member_access(actor: Actor, matter_id: uuid.UUID) -> str | None:
    return actor.session.scalar(
        select(MatterMember.access).where(
            MatterMember.matter_id == matter_id, MatterMember.user_id == actor.user_id
        )
    )


def require_matter(actor: Actor, matter_id: uuid.UUID) -> Matter:
    matter = actor.session.get(Matter, matter_id)
    if matter is None:
        raise _not_found()
    if member_access(actor, matter_id) != "member":
        _deny(actor, matter_id)
    return matter


def require_document(actor: Actor, document_id: uuid.UUID) -> Document:
    doc = actor.session.get(Document, document_id)
    if doc is None:
        raise _not_found()
    require_matter(actor, doc.matter_id)
    return doc


def visible_matter_ids(actor: Actor) -> list[uuid.UUID]:
    return list(
        actor.session.scalars(
            select(MatterMember.matter_id).where(
                MatterMember.user_id == actor.user_id, MatterMember.access == "member"
            )
        )
    )


def _deny(actor: Actor, matter_id: uuid.UUID) -> None:
    # Record the denial in its own transaction so it survives the request's rollback.
    from travo_api.db import tenant_session

    with tenant_session(actor.tenant_id) as s:
        audit(
            s,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="matter.access_denied",
            resource_type="matter",
            resource_id=matter_id,
            matter_id=matter_id,
            result="denied",
        )
    raise _not_found()
