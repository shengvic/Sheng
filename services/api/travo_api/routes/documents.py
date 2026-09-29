from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from travo_rag.parsing import UnsupportedDocument, sniff_mime

from travo_api.auth import Actor, get_actor
from travo_api.config import get_settings
from travo_api.ingest import process_document, store_document
from travo_api.models import Clause, Document
from travo_api.schemas import ClauseOut, DocumentOut
from travo_api.walls import require_document, require_matter

router = APIRouter(tags=["documents"])


@router.post(
    "/v1/matters/{matter_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    matter_id: uuid.UUID, file: UploadFile = File(...), actor: Actor = Depends(get_actor)
) -> Document:
    matter = require_matter(actor, matter_id)
    limit = get_settings().max_upload_bytes
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")
    if not data:
        raise HTTPException(422, "empty file")
    filename = file.filename or "upload"
    try:
        mime = sniff_mime(filename, file.content_type, data[:8])
    except UnsupportedDocument as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from None
    doc = store_document(actor, matter, filename, mime, data)
    process_document(actor, matter, doc)
    actor.session.flush()
    actor.session.refresh(doc)
    return doc


@router.get("/v1/matters/{matter_id}/documents", response_model=list[DocumentOut])
def list_documents(matter_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> list[Document]:
    require_matter(actor, matter_id)
    return list(
        actor.session.scalars(
            select(Document).where(Document.matter_id == matter_id).order_by(Document.created_at)
        )
    )


@router.get("/v1/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> Document:
    return require_document(actor, document_id)


@router.get("/v1/documents/{document_id}/clauses", response_model=list[ClauseOut])
def get_clauses(document_id: uuid.UUID, actor: Actor = Depends(get_actor)) -> list[Clause]:
    require_document(actor, document_id)
    return list(
        actor.session.scalars(
            select(Clause).where(Clause.document_id == document_id).order_by(Clause.idx)
        )
    )
