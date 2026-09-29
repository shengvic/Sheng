from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from travo_api.auth import Actor, get_actor
from travo_api.config import get_settings
from travo_api.db import after_commit
from travo_api.exports import blocking_items, create_export, read_export
from travo_api.models import Citation, Export, Finding, ReviewRun, ReviewStep
from travo_api.reviews import runner, start_review
from travo_api.schemas import (
    CitationOut,
    ExportIn,
    ExportOut,
    FindingOut,
    ReviewOut,
    ReviewStart,
    ReviewStepOut,
)
from travo_api.walls import require_document, require_matter
from travo_api.workflows import worker_id

router = APIRouter(tags=["reviews"])


def _run_inline() -> None:
    runner().drain(worker_id(), limit=5)


def require_run(actor: Actor, run_id: uuid.UUID) -> ReviewRun:
    run = actor.session.get(ReviewRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    require_matter(actor, run.matter_id)
    return run


def _review_out(actor: Actor, run: ReviewRun) -> ReviewOut:
    out = ReviewOut.model_validate(run)
    steps = actor.session.scalars(
        select(ReviewStep).where(ReviewStep.run_id == run.id).order_by(ReviewStep.idx)
    )
    out.steps = [ReviewStepOut.model_validate(s) for s in steps]
    return out


@router.post(
    "/v1/documents/{document_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_review(
    document_id: uuid.UUID,
    body: ReviewStart | None = None,
    actor: Actor = Depends(get_actor),
) -> ReviewOut:
    doc = require_document(actor, document_id)
    matter = require_matter(actor, doc.matter_id)
    run = start_review(actor, matter, doc, body.playbook_key if body else None)
    if get_settings().inline_reviews:
        after_commit(actor.session, _run_inline)
    return _review_out(actor, run)


@router.get("/v1/matters/{matter_id}/reviews", response_model=list[ReviewOut])
def list_reviews(matter_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> list[ReviewOut]:
    require_matter(actor, matter_id)
    runs = actor.session.scalars(
        select(ReviewRun)
        .where(ReviewRun.matter_id == matter_id)
        .order_by(ReviewRun.created_at.desc())
    )
    return [_review_out(actor, r) for r in runs]


@router.get("/v1/reviews/{run_id}", response_model=ReviewOut)
def get_review(run_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> ReviewOut:
    return _review_out(actor, require_run(actor, run_id))


@router.get("/v1/reviews/{run_id}/findings", response_model=list[FindingOut])
def list_findings(
    run_id: uuid.UUID, kind: str | None = None, actor: Actor = Depends(get_actor)
) -> list[FindingOut]:
    require_run(actor, run_id)
    q = select(Finding).where(Finding.run_id == run_id).order_by(Finding.created_at)
    if kind:
        q = q.where(Finding.kind == kind)
    findings = list(actor.session.scalars(q))
    cits: dict[uuid.UUID, list[Citation]] = {}
    if findings:
        for c in actor.session.scalars(
            select(Citation).where(Citation.finding_id.in_([f.id for f in findings]))
        ):
            cits.setdefault(c.finding_id, []).append(c)
    out = []
    for f in findings:
        fo = FindingOut.model_validate(f)
        fo.citations = [CitationOut.model_validate(c) for c in cits.get(f.id, [])]
        out.append(fo)
    return out


@router.get("/v1/reviews/{run_id}/export-gate")
def export_gate(run_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> dict[str, object]:
    run = require_run(actor, run_id)
    blocks = (
        blocking_items(actor, run)
        if run.status == "completed"
        else [{"type": "review_not_completed", "status": run.status}]
    )
    return {"open": not blocks, "blocking": blocks}


@router.post(
    "/v1/reviews/{run_id}/exports", response_model=ExportOut, status_code=status.HTTP_201_CREATED
)
def export_review(run_id: uuid.UUID, body: ExportIn, actor: Actor = Depends(get_actor)) -> Export:
    run = require_run(actor, run_id)
    if run.status != "completed":
        raise HTTPException(
            409, {"blocking": [{"type": "review_not_completed", "status": run.status}]}
        )
    blocks = blocking_items(actor, run)
    if blocks:
        raise HTTPException(409, {"blocking": blocks})
    return create_export(actor, run, body.format)


@router.get("/v1/exports/{export_id}")
def download_export(export_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> Response:
    export = actor.session.get(Export, export_id)
    if export is None:
        raise HTTPException(404, "not found")
    require_matter(actor, export.matter_id)
    data = read_export(actor, export)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )
