"""Document intake + P0 review pipeline (docs/05). Runs inline; Temporal in P1."""

from __future__ import annotations

import hashlib
import uuid
from functools import lru_cache

from sqlalchemy import delete
from travo_agents.base import AgentContext, AgentOutputError
from travo_agents.pipeline import run_pipeline
from travo_rag.parsing import UnsupportedDocument, parse
from travo_router.client import NoEligibleModel

from travo_api.audit import audit
from travo_api.auth import Actor
from travo_api.config import get_settings
from travo_api.keys import tenant_dek
from travo_api.models import Clause, Document, Matter
from travo_api.routing import DbRouterContext, get_router
from travo_api.storage import LocalEncryptedStore, ObjectStore


@lru_cache
def get_store() -> ObjectStore:
    return LocalEncryptedStore(get_settings().storage_dir)


def store_document(actor: Actor, matter: Matter, filename: str, mime: str, data: bytes) -> Document:
    dek = tenant_dek(actor.session, actor.tenant_id)
    ref = get_store().put(actor.tenant_id, dek, data)
    doc = Document(
        tenant_id=uuid.UUID(actor.tenant_id),
        matter_id=matter.id,
        filename=filename[:300],
        mime=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_ref=ref,
        created_by=actor.user_id,
        parties=[],
        languages=[],
    )
    actor.session.add(doc)
    actor.session.flush()
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="document.uploaded",
        resource_type="document",
        resource_id=doc.id,
        matter_id=matter.id,
        details={"sha256": doc.sha256, "size": doc.size_bytes},
    )
    return doc


def process_document(actor: Actor, matter: Matter, doc: Document) -> None:
    session = actor.session
    dek = tenant_dek(session, actor.tenant_id)
    data = get_store().get(actor.tenant_id, dek, doc.storage_ref)
    router_ctx = DbRouterContext(session, actor.tenant_id, document_id=doc.id)
    ctx = AgentContext(
        router=get_router(),
        router_ctx=router_ctx,
        tenant_id=actor.tenant_id,
        matter_id=str(matter.id),
        jurisdictions=list(matter.jurisdictions or []),
    )
    try:
        blocks = parse(data, doc.mime)
        result = run_pipeline(ctx, blocks)
    except UnsupportedDocument as exc:
        _fail(actor, doc, "unsupported", str(exc))
        return
    except NoEligibleModel as exc:
        _fail(actor, doc, "needs_model", f"no eligible model: {exc.record.outcome}")
        return
    except AgentOutputError as exc:
        _fail(actor, doc, "failed", str(exc))
        return

    c = result.classification
    doc.languages = result.languages
    doc.contract_type = c.contract_type
    doc.contract_type_confidence = c.contract_type_confidence
    doc.governing_law = c.governing_law
    doc.parties = c.parties
    doc.primary_language = result.primary_language
    doc.bilingual_layout = result.layout
    doc.parse_status = "classified"
    doc.error = None
    session.execute(delete(Clause).where(Clause.document_id == doc.id))
    for lc in result.clauses:
        session.add(
            Clause(
                tenant_id=doc.tenant_id,
                matter_id=doc.matter_id,
                document_id=doc.id,
                idx=lc.index,
                number=lc.number,
                heading=lc.heading,
                text=lc.text,
                taxonomy_key=lc.key,
                confidence=lc.confidence,
                lang=result.primary_language,
                heading_alt=lc.heading_alt,
                text_alt=lc.text_alt,
                lang_alt=result.other_language if (lc.text_alt or lc.heading_alt) else None,
            )
        )
    audit(
        session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="document.classified",
        resource_type="document",
        resource_id=doc.id,
        matter_id=doc.matter_id,
        details={
            "contract_type": c.contract_type,
            "governing_law": c.governing_law,
            "clauses": len(result.clauses),
            "routing_decisions": [str(i) for i in router_ctx.decision_ids],
        },
    )


def _fail(actor: Actor, doc: Document, status: str, message: str) -> None:
    doc.parse_status = status
    doc.error = message[:1000]
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="document.processing_failed",
        resource_type="document",
        resource_id=doc.id,
        matter_id=doc.matter_id,
        result="error",
        details={"status": status},
    )
