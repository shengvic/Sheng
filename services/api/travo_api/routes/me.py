from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from travo_api.auth import Actor, get_actor
from travo_api.models import LegalSource, LegalUnit, Tenant
from travo_api.schemas import LegalUnitOut, MeOut

router = APIRouter(tags=["me"])


@router.get("/v1/me", response_model=MeOut)
def me(actor: Actor = Depends(get_actor)) -> MeOut:
    tenant = actor.session.get(Tenant, actor.user.tenant_id)
    return MeOut(
        id=actor.user.id,
        email=actor.user.email,
        name=actor.user.name,
        role=actor.user.role,
        tenant_id=actor.user.tenant_id,
        tenant_name=tenant.name if tenant else "",
    )


@router.get("/v1/legal-units/{unit_id:path}", response_model=LegalUnitOut)
def legal_unit(unit_id: str, actor: Actor = Depends(get_actor)) -> LegalUnitOut:
    """Public-law unit for the sources panel. The legal index holds no tenant data."""
    row = actor.session.execute(
        select(LegalUnit, LegalSource)
        .join(LegalSource, LegalSource.id == LegalUnit.source_id)
        .where(LegalUnit.id == unit_id)
    ).first()
    if row is None:
        raise HTTPException(404, "not found")
    unit, source = row
    return LegalUnitOut(
        id=unit.id,
        source_id=source.id,
        source_title=source.title,
        jurisdiction=source.jurisdiction,
        unit_path=unit.unit_path,
        pinpoint=f"{source.title}, {unit.unit_path}",
        heading=unit.heading,
        text=unit.text,
        status=unit.status,
        effective_from=unit.effective_from,
        effective_to=unit.effective_to,
        official_url=source.official_url,
        issuing_body=source.issuing_body,
        is_fixture=source.is_fixture,
        review_status=source.review_status,
        verified_at=source.verified_at,
        retrieved_at=source.retrieved_at,
        snapshot_sha256=source.snapshot_sha256,
    )
