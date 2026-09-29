from __future__ import annotations

import uuid

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from travo_agents.playbooks import Playbook

from travo_api.audit import audit
from travo_api.auth import Actor, get_actor
from travo_api.models import PlaybookRow
from travo_api.reviews import starter_playbooks, tenant_playbooks
from travo_api.schemas import PlaybookIn, PlaybookOut

router = APIRouter(prefix="/v1/playbooks", tags=["playbooks"])
EDITORS = ("admin", "km", "partner")


def _out(pb: Playbook, source: str, full: bool = False) -> PlaybookOut:
    return PlaybookOut(
        key=pb.key,
        version=pb.version,
        name=pb.name,
        source=source,  # type: ignore[arg-type]
        contract_types=pb.applies_to.contract_types,
        governing_laws=pb.applies_to.governing_laws,
        rules=len(pb.rules),
        spec=pb.model_dump(mode="json") if full else None,
    )


@router.get("", response_model=list[PlaybookOut])
def list_playbooks(actor: Actor = Depends(get_actor)) -> list[PlaybookOut]:
    return [_out(pb, "tenant") for pb in tenant_playbooks(actor)] + [
        _out(pb, "starter") for pb in starter_playbooks().values()
    ]


@router.get("/{key}", response_model=PlaybookOut)
def get_playbook(key: str, actor: Actor = Depends(get_actor)) -> PlaybookOut:
    for pb in tenant_playbooks(actor):
        if pb.key == key:
            return _out(pb, "tenant", full=True)
    if key in starter_playbooks():
        return _out(starter_playbooks()[key], "starter", full=True)
    raise HTTPException(404, "not found")


@router.post("", response_model=PlaybookOut, status_code=201)
def save_playbook(body: PlaybookIn, actor: Actor = Depends(get_actor)) -> PlaybookOut:
    """Create a new version of a firm playbook, from YAML or by cloning a starter pack."""
    if actor.user.role not in EDITORS:
        raise HTTPException(403, "only KM lawyers, partners or admins edit playbooks")
    try:
        if body.yaml:
            pb = Playbook.from_yaml(body.yaml)
        elif body.from_starter and body.from_starter in starter_playbooks():
            pb = starter_playbooks()[body.from_starter].model_copy(deep=True)
        else:
            raise HTTPException(422, "provide yaml or a valid from_starter key")
    except (yaml.YAMLError, ValidationError) as exc:
        raise HTTPException(422, f"invalid playbook: {exc}") from None
    if body.key:
        pb.key = body.key
    version = (
        actor.session.scalar(select(func.max(PlaybookRow.version)).where(PlaybookRow.key == pb.key))
        or 0
    ) + 1
    pb.version = version
    actor.session.add(
        PlaybookRow(
            tenant_id=uuid.UUID(actor.tenant_id),
            key=pb.key,
            version=version,
            name=pb.name,
            contract_types=pb.applies_to.contract_types,
            governing_laws=pb.applies_to.governing_laws,
            spec=pb.model_dump(mode="json"),
            status="active",
            created_by=actor.user_id,
        )
    )
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="playbook.saved",
        resource_type="playbook",
        resource_id=f"{pb.key}@{version}",
    )
    return _out(pb, "tenant", full=True)
