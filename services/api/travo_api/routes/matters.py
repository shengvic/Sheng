from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select

from travo_api.audit import audit
from travo_api.auth import Actor, get_actor
from travo_api.models import Matter, MatterMember, User
from travo_api.schemas import MatterCreate, MatterOut, MembersPut
from travo_api.walls import require_matter, visible_matter_ids

router = APIRouter(prefix="/v1/matters", tags=["matters"])


@router.post("", response_model=MatterOut, status_code=status.HTTP_201_CREATED)
def create_matter(body: MatterCreate, actor: Actor = Depends(get_actor)) -> Matter:
    matter = Matter(
        tenant_id=uuid.UUID(actor.tenant_id),
        number=body.number,
        name=body.name,
        jurisdictions=list(body.jurisdictions),
        residency=body.residency,
        deny_providers=sorted(set(body.deny_providers)),
        allow_providers=body.allow_providers,
        budget_usd=Decimal(str(body.budget_usd)) if body.budget_usd is not None else None,
        created_by=actor.user_id,
    )
    actor.session.add(matter)
    actor.session.flush()
    actor.session.add(
        MatterMember(
            tenant_id=matter.tenant_id,
            matter_id=matter.id,
            user_id=actor.user_id,
            access="member",
        )
    )
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="matter.created",
        resource_type="matter",
        resource_id=matter.id,
        matter_id=matter.id,
        details={"deny_providers": matter.deny_providers, "residency": matter.residency},
    )
    actor.session.flush()
    actor.session.refresh(matter)
    return matter


@router.get("", response_model=list[MatterOut])
def list_matters(actor: Actor = Depends(get_actor)) -> list[Matter]:
    ids = visible_matter_ids(actor)
    if not ids:
        return []
    return list(
        actor.session.scalars(
            select(Matter).where(Matter.id.in_(ids)).order_by(Matter.created_at.desc())
        )
    )


@router.get("/{matter_id}", response_model=MatterOut)
def get_matter(matter_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> Matter:
    return require_matter(actor, matter_id)


@router.put("/{matter_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def put_members(matter_id: uuid.UUID, body: MembersPut, actor: Actor = Depends(get_actor)) -> None:
    """Replace the ethical-wall membership. Only partners/admins inside the wall may do this."""
    require_matter(actor, matter_id)
    if actor.user.role not in ("partner", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only partners or admins manage walls")
    user_ids = {m.user_id for m in body.members}
    found = set(actor.session.scalars(select(User.id).where(User.id.in_(user_ids))))
    if found != user_ids:
        raise HTTPException(422, "unknown user id(s)")
    if not any(m.user_id == actor.user_id and m.access == "member" for m in body.members):
        raise HTTPException(422, "cannot remove yourself")
    actor.session.execute(delete(MatterMember).where(MatterMember.matter_id == matter_id))
    for m in body.members:
        actor.session.add(
            MatterMember(
                tenant_id=uuid.UUID(actor.tenant_id),
                matter_id=matter_id,
                user_id=m.user_id,
                access=m.access,
            )
        )
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="matter.wall_updated",
        resource_type="matter",
        resource_id=matter_id,
        matter_id=matter_id,
        details={
            "members": [{"user_id": str(m.user_id), "access": m.access} for m in body.members]
        },
    )
