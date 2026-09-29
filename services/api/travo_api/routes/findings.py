from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from travo_api.audit import audit
from travo_api.auth import Actor, get_actor
from travo_api.models import Citation, Finding
from travo_api.schemas import CitationOut, DispositionIn, FindingOut, OverrideIn
from travo_api.telemetry import emit
from travo_api.walls import require_matter

router = APIRouter(tags=["findings"])

ACTION_TO_DISPOSITION: dict[str, str | None] = {
    "accept": "accepted",
    "edit": "edited",
    "reject": "rejected",
    "defer": "deferred",
    "reset": None,  # undo: back to undispositioned (still recorded in telemetry + audit)
}


def require_finding(actor: Actor, finding_id: uuid.UUID) -> Finding:
    f = actor.session.get(Finding, finding_id)
    if f is None:
        raise HTTPException(404, "not found")
    require_matter(actor, f.matter_id)
    return f


@router.patch("/v1/findings/{finding_id}", response_model=FindingOut)
def disposition(
    finding_id: uuid.UUID, body: DispositionIn, actor: Actor = Depends(get_actor)
) -> FindingOut:
    f = require_finding(actor, finding_id)
    if body.action == "edit" and not (body.edited_text or "").strip():
        raise HTTPException(422, "edited_text is required for edit")
    if body.action == "reject" and not body.reason_code:
        raise HTTPException(422, "reason_code is required for reject")
    previous = f.disposition
    f.disposition = ACTION_TO_DISPOSITION[body.action]
    f.edited_text = body.edited_text if body.action == "edit" else None
    f.reason_code = body.reason_code
    f.note = body.note
    f.disposition_by = actor.user_id if body.action != "reset" else None
    f.disposition_at = datetime.now(UTC) if body.action != "reset" else None
    payload = {
        "action": body.action,
        "previous": previous,
        "reason_code": body.reason_code,
        "classification": f.classification,
        "severity": f.severity,
        "kind": f.kind,
        "clause_key": f.clause_key,
        "rule_key": f.rule_key,
        "model_tier": f.model_tier,
        "confidence": f.confidence,
        "reviewer_role": actor.user.role,
    }
    emit(
        actor.session,
        tenant_id=actor.tenant_id,
        event_type="finding.dispositioned",
        matter_id=f.matter_id,
        actor_id=actor.user_id,
        subject_id=f.id,
        payload=payload,
    )
    if body.action == "edit" and f.kind == "playbook":
        # Firm-private learning signal: the model's suggestion vs the lawyer's wording.
        emit(
            actor.session,
            tenant_id=actor.tenant_id,
            event_type="redline.edited",
            matter_id=f.matter_id,
            actor_id=actor.user_id,
            subject_id=f.id,
            payload={
                "clause_key": f.clause_key,
                "suggested": f.suggested_redline,
                "final": f.edited_text,
                "reviewer_role": actor.user.role,
            },
        )
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="finding.dispositioned",
        resource_type="finding",
        resource_id=f.id,
        matter_id=f.matter_id,
        details={"action": body.action, "previous": previous},
    )
    actor.session.flush()
    out = FindingOut.model_validate(f)
    out.citations = [
        CitationOut.model_validate(c)
        for c in actor.session.scalars(select(Citation).where(Citation.finding_id == f.id))
    ]
    return out


@router.post("/v1/citations/{citation_id}/override", response_model=CitationOut)
def override_citation(
    citation_id: uuid.UUID, body: OverrideIn, actor: Actor = Depends(get_actor)
) -> Citation:
    c = actor.session.get(Citation, citation_id)
    if c is None:
        raise HTTPException(404, "not found")
    require_matter(actor, c.matter_id)
    if actor.user.role not in ("partner", "admin", "km"):
        raise HTTPException(403, "only partners or KM lawyers may override citation checks")
    c.override_reason = body.reason
    c.overridden_by = actor.user_id
    emit(
        actor.session,
        tenant_id=actor.tenant_id,
        event_type="citation.overridden",
        matter_id=c.matter_id,
        actor_id=actor.user_id,
        subject_id=c.id,
        payload={"status": c.status, "source_unit_id": c.source_unit_id},
    )
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="citation.overridden",
        resource_type="citation",
        resource_id=c.id,
        matter_id=c.matter_id,
        details={"status": c.status, "reason": body.reason},
    )
    return c
