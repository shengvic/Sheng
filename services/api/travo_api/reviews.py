"""Contract review workflow (docs/05): enqueue + the steps run by the durable runner."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from travo_agents.base import AgentContext
from travo_agents.bilingual import ClausePair, check_bilingual
from travo_agents.compare import FindingDraft, compare
from travo_agents.lawcheck import JurisdictionPack, lawcheck, load_packs
from travo_agents.memo import write_memo
from travo_agents.playbooks import Playbook, load_starter_playbooks, select_playbook
from travo_agents.redline import draft_redlines
from travo_agents.validate import router_judge
from travo_rag import citations as cite
from travo_rag import retrieval
from travo_rag.retrieval import LegalUnitHit

from travo_api.audit import audit
from travo_api.auth import Actor
from travo_api.config import get_settings
from travo_api.models import (
    Citation,
    Clause,
    Document,
    Finding,
    Matter,
    MatterMember,
    PlaybookRow,
    ReviewRun,
)
from travo_api.routing import DbRouterContext, cost_of, get_router
from travo_api.telemetry import emit
from travo_api.workflows import StepContext, StepFn, WorkflowRunner, get_review_config

# ---------------------------------------------------------------- playbooks


@lru_cache
def starter_playbooks() -> dict[str, Playbook]:
    return load_starter_playbooks(get_settings().playbooks_dir)


@lru_cache
def jurisdiction_packs() -> dict[str, JurisdictionPack]:
    return load_packs(get_settings().jurisdiction_packs_dir)


def tenant_playbooks(actor: Actor) -> list[Playbook]:
    """Latest active version of each tenant playbook key."""
    rows = actor.session.scalars(
        select(PlaybookRow)
        .where(PlaybookRow.status == "active")
        .order_by(PlaybookRow.key, PlaybookRow.version.desc())
    )
    latest: dict[str, Playbook] = {}
    for r in rows:
        latest.setdefault(r.key, Playbook.model_validate({**r.spec, "version": r.version}))
    return list(latest.values())


def resolve_playbook(actor: Actor, doc: Document, playbook_key: str | None) -> tuple[Playbook, str]:
    tenant = tenant_playbooks(actor)
    starter = list(starter_playbooks().values())
    if playbook_key:
        for source, books in (("tenant", tenant), ("starter", starter)):
            for pb in books:
                if pb.key == playbook_key:
                    return pb, source
        raise HTTPException(404, f"playbook {playbook_key} not found")
    chosen = select_playbook(doc.contract_type, doc.governing_law, tenant, starter)
    if chosen is None:
        raise HTTPException(
            422,
            f"no playbook for {doc.contract_type}/{doc.governing_law}; pass playbook_key",
        )
    return chosen


# ---------------------------------------------------------------- enqueue


def start_review(
    actor: Actor, matter: Matter, doc: Document, playbook_key: str | None
) -> ReviewRun:
    if doc.parse_status != "classified":
        raise HTTPException(409, f"document is {doc.parse_status}; cannot review")
    pb, source = resolve_playbook(actor, doc, playbook_key)
    run = ReviewRun(
        tenant_id=uuid.UUID(actor.tenant_id),
        matter_id=matter.id,
        document_id=doc.id,
        playbook_key=pb.key,
        playbook_version=pb.version,
        playbook_source=source,
        playbook_spec=pb.model_dump(mode="json"),
        initiated_by=actor.user_id,
        status="queued",
        summary={},
    )
    actor.session.add(run)
    actor.session.flush()
    audit(
        actor.session,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action="review.started",
        resource_type="review_run",
        resource_id=run.id,
        matter_id=matter.id,
        details={"playbook": f"{pb.key}@{pb.version}", "source": source},
    )
    emit(
        actor.session,
        tenant_id=actor.tenant_id,
        event_type="review.started",
        matter_id=matter.id,
        actor_id=actor.user_id,
        subject_id=run.id,
        payload={"playbook": pb.key, "version": pb.version, "source": source},
    )
    return run


# ---------------------------------------------------------------- steps


def _agent_ctx(sc: StepContext) -> tuple[AgentContext, DbRouterContext]:
    router_ctx = DbRouterContext(sc.session, sc.tenant_id, document_id=sc.run.document_id)
    matter = sc.session.get(Matter, sc.run.matter_id)
    doc = sc.session.get(Document, sc.run.document_id)
    jurisdictions = list(matter.jurisdictions or []) if matter else []
    if doc and doc.governing_law and doc.governing_law not in jurisdictions:
        jurisdictions.append(doc.governing_law)
    ctx = AgentContext(
        router=get_router(),
        router_ctx=router_ctx,
        tenant_id=sc.tenant_id,
        matter_id=str(sc.run.matter_id),
        jurisdictions=jurisdictions,
        languages=list(doc.languages or []) if doc else [],
    )
    return ctx, router_ctx


def _clauses(sc: StepContext) -> list[Clause]:
    return list(
        sc.session.scalars(
            select(Clause).where(Clause.document_id == sc.run.document_id).order_by(Clause.idx)
        )
    )


def _clause_dicts(clauses: list[Clause]) -> list[dict[str, Any]]:
    return [
        {"i": c.idx, "key": c.taxonomy_key, "heading": c.heading, "text": c.text} for c in clauses
    ]


def _add_finding(sc: StepContext, d: FindingDraft, clause_ids: dict[int, uuid.UUID]) -> Finding:
    f = Finding(
        tenant_id=sc.run.tenant_id,
        matter_id=sc.run.matter_id,
        run_id=sc.run.id,
        clause_id=clause_ids.get(d.clause_index) if d.clause_index is not None else None,
        clause_key=d.clause_key,
        rule_key=d.rule_key,
        kind=d.kind,
        classification=d.classification,
        severity=d.severity,
        summary=d.summary or "",
        rationale=d.rationale or "",
        suggested_redline=d.suggested_redline,
        confidence=d.confidence,
        model_tier=d.tier,
        escalated=d.escalated,
        status="needs_human" if d.needs_human else "needs_review",
        evidence=d.evidence,
    )
    sc.session.add(f)
    sc.session.flush()
    if d.escalated:
        emit(
            sc.session,
            tenant_id=sc.tenant_id,
            event_type="escalation.completed",
            matter_id=sc.run.matter_id,
            subject_id=f.id,
            payload={
                "task": {"law": "law_check", "bilingual": "bilingual_check"}.get(
                    d.kind, "playbook_compare"
                ),
                "tier": d.tier,
                "needs_human": d.needs_human,
            },
        )
    return f


def step_prepare(sc: StepContext) -> dict[str, Any]:
    doc = sc.session.get(Document, sc.run.document_id)
    clauses = _clauses(sc)
    if doc is None or not clauses:
        raise RuntimeError("document has no extracted clauses")
    return {
        "clauses": len(clauses),
        "contract_type": doc.contract_type,
        "governing_law": doc.governing_law,
        # Signing date extraction lands with the T1 classifier; review law as of today.
        "as_of": date.today().isoformat(),
    }


def step_bilingual(sc: StepContext) -> dict[str, Any]:
    """VI–EN discrepancies between the two language versions of each clause (ADR-023)."""
    doc = sc.session.get(Document, sc.run.document_id)
    clauses = _clauses(sc)
    other = next((c.lang_alt for c in clauses if c.lang_alt), None)
    if doc is None or doc.bilingual_layout == "single" or other is None:
        return {"skipped": "not a bilingual document", "findings": 0}
    ctx, rctx = _agent_ctx(sc)
    langs = (doc.primary_language or "vi", other)
    pairs = [
        ClausePair(c.idx, c.taxonomy_key, c.heading, c.text, c.text_alt)
        for c in clauses
        if c.heading != "Preamble"
    ]
    drafts = check_bilingual(ctx, pairs, langs)
    ids = {c.idx: c.id for c in clauses}
    for d in drafts:
        _add_finding(sc, d, ids)
    return {
        "findings": len(drafts),
        "layout": doc.bilingual_layout,
        "cost_usd": cost_of(sc.session, rctx.decision_ids),
    }


def step_compare(sc: StepContext) -> dict[str, Any]:
    ctx, rctx = _agent_ctx(sc)
    clauses = _clauses(sc)
    pb = Playbook.model_validate(sc.run.playbook_spec)
    threshold = get_review_config().thresholds.get("playbook_compare", 0.5)
    drafts = compare(ctx, pb, _clause_dicts(clauses), threshold)
    ids = {c.idx: c.id for c in clauses}
    for d in drafts:
        _add_finding(sc, d, ids)
    return {"findings": len(drafts), "cost_usd": cost_of(sc.session, rctx.decision_ids)}


def step_lawcheck(sc: StepContext) -> dict[str, Any]:
    doc = sc.session.get(Document, sc.run.document_id)
    law = (doc.governing_law if doc else None) or None
    pack = jurisdiction_packs().get(law or "")
    if pack is None:
        return {"skipped": f"no jurisdiction pack for {law}"}
    ctx, rctx = _agent_ctx(sc)
    as_of = date.fromisoformat(sc.outputs["prepare"]["as_of"])
    session = sc.session

    def retrieve(query: str, clause_text: str) -> list[LegalUnitHit]:
        return retrieval.search(
            session,
            query,
            jurisdictions=[pack.jurisdiction],
            as_of=as_of,
            k=3,
            rerank_with=clause_text,
            require_verified=get_settings().require_verified_sources,
        )

    judge, used = router_judge(ctx)

    def validate(note: str) -> list[cite.CitationResult]:
        results = cite.validate(
            note, lookup=lambda uid: retrieval.get_unit(session, uid), as_of=as_of, judge=judge
        )
        for r in results:
            r.checker = used[-1] if used else r.checker
        return results

    clauses = _clauses(sc)
    ids = {c.idx: c.id for c in clauses}
    notes = lawcheck(ctx, pack, _clause_dicts(clauses), retrieve, validate)
    for draft, results in notes:
        draft.summary = draft.note or draft.summary
        f = _add_finding(sc, draft, ids)
        for r in results:
            session.add(
                Citation(
                    tenant_id=sc.run.tenant_id,
                    matter_id=sc.run.matter_id,
                    finding_id=f.id,
                    claim_text=r.claim[:4000],
                    source_unit_id=r.source_unit_id,
                    pinpoint=r.pinpoint,
                    status=r.status,
                    score=r.score,
                    checker=r.checker[:128],
                )
            )
    return {"notes": len(notes), "cost_usd": cost_of(session, rctx.decision_ids)}


def few_shot_examples(sc: StepContext, clause_keys: set[str], n: int) -> dict[str, list[str]]:
    """Firm's accepted/edited redlines, only from matters the initiator is a member of, so
    walled matters never leak into another team's drafts (ADR-015)."""
    if not clause_keys:
        return {}
    visible = select(MatterMember.matter_id).where(
        MatterMember.user_id == sc.run.initiated_by, MatterMember.access == "member"
    )
    rows = sc.session.execute(
        select(
            Finding.clause_key, Finding.disposition, Finding.edited_text, Finding.suggested_redline
        )
        .where(
            Finding.clause_key.in_(clause_keys),
            Finding.disposition.in_(["accepted", "edited"]),
            Finding.kind == "playbook",
            Finding.matter_id.in_(visible),
        )
        .order_by(Finding.disposition_at.desc())
    ).all()
    out: dict[str, list[str]] = {}
    for key, disp, edited, suggested in rows:
        textv = edited if disp == "edited" else suggested
        if textv and len(out.setdefault(key, [])) < n and textv not in out[key]:
            out[key].append(textv)
    return out


def step_redline(sc: StepContext) -> dict[str, Any]:
    ctx, rctx = _agent_ctx(sc)
    pb = Playbook.model_validate(sc.run.playbook_spec)
    rules = {r.key: r for r in pb.rules}
    rows = list(
        sc.session.scalars(
            select(Finding).where(
                Finding.run_id == sc.run.id,
                Finding.kind == "playbook",
                Finding.classification.in_(["non_standard", "missing"]),
            )
        )
    )
    clauses = {c["i"]: c for c in _clause_dicts(_clauses(sc))}
    idx_by_clause = {c.id: c.idx for c in _clauses(sc)}
    drafts = []
    for f in rows:
        rule = rules.get(f.rule_key)
        drafts.append(
            FindingDraft(
                rule_key=f.rule_key,
                clause_key=f.clause_key,
                clause_index=idx_by_clause.get(f.clause_id) if f.clause_id else None,
                kind="playbook",
                classification=f.classification,
                severity=f.severity,
                summary=f.summary,
                rationale=f.rationale,
                confidence=f.confidence,
                tier=f.model_tier,
                redline_template=rule.redline_template if rule else None,
            )
        )
    examples = few_shot_examples(
        sc, {f.clause_key for f in rows}, get_review_config().few_shot_examples
    )
    draft_redlines(ctx, drafts, clauses, examples, {k: r.standard for k, r in rules.items()})
    written = 0
    for f, d in zip(rows, drafts, strict=True):
        if d.suggested_redline:
            f.suggested_redline = d.suggested_redline
            written += 1
    return {
        "redlines": written,
        "few_shot_keys": sorted(examples),
        "cost_usd": cost_of(sc.session, rctx.decision_ids),
    }


def step_memo(sc: StepContext) -> dict[str, Any]:
    ctx, rctx = _agent_ctx(sc)
    rows = list(sc.session.scalars(select(Finding).where(Finding.run_id == sc.run.id)))
    memo = write_memo(
        ctx,
        [
            {
                "clause_key": f.clause_key,
                "classification": f.classification,
                "severity": f.severity,
                "summary": f.summary,
            }
            for f in rows
        ],
    )
    sc.run.summary = {
        **memo,
        "findings": len(rows),
        "needs_human": sum(1 for f in rows if f.status == "needs_human"),
    }
    return {"cost_usd": cost_of(sc.session, rctx.decision_ids)}


STEPS: dict[str, StepFn] = {
    "prepare": step_prepare,
    "bilingual": step_bilingual,
    "compare": step_compare,
    "lawcheck": step_lawcheck,
    "redline": step_redline,
    "memo": step_memo,
}


def runner() -> WorkflowRunner:
    return WorkflowRunner(STEPS)


def review_counts(actor: Actor, run_id: uuid.UUID) -> dict[str, int]:
    rows = actor.session.execute(
        select(Finding.severity, func.count())
        .where(Finding.run_id == run_id)
        .group_by(Finding.severity)
    ).all()
    return {sev: int(n) for sev, n in rows}


def now() -> datetime:
    return datetime.now(UTC)
