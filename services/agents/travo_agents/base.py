"""Agent base: vendor-free; every model call goes through the router."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from travo_router import Router, TaskDescriptor
from travo_router.client import NoEligibleModel, RouterContext
from travo_router.providers import Message


@dataclass
class AgentContext:
    router: Router
    router_ctx: RouterContext
    tenant_id: str
    matter_id: str | None
    jurisdictions: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    sensitivity: str = "standard"


class AgentOutputError(ValueError):
    pass


def parse_json_object(text: str) -> dict[str, Any]:
    """Models sometimes wrap JSON in prose or fences; take the outermost object."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise AgentOutputError("model output contained no JSON object")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise AgentOutputError(f"invalid JSON from model: {exc.msg}") from None
    if not isinstance(obj, dict):
        raise AgentOutputError("model output is not a JSON object")
    return obj


@dataclass
class JsonResult:
    data: dict[str, Any]
    endpoint: str | None
    tier: str | None
    escalated: bool = False
    needs_human: bool = False


def call_json(
    ctx: AgentContext,
    task_type: str,
    system: str,
    payload: dict[str, Any],
    est_output: int = 800,
    escalation_reason: str | None = None,
) -> JsonResult:
    body = json.dumps(payload, ensure_ascii=False)
    descriptor = TaskDescriptor(
        task_type=task_type,  # type: ignore[arg-type]
        tenant_id=ctx.tenant_id,
        matter_id=ctx.matter_id,
        jurisdictions=ctx.jurisdictions,
        languages=ctx.languages,
        est_input_tokens=(len(system) + len(body)) // 4,
        est_output_tokens=est_output,
        sensitivity=ctx.sensitivity,  # type: ignore[arg-type]
        requires=["json_output"],
        escalation_reason=escalation_reason,
        attempt=2 if escalation_reason else 1,
    )
    result = ctx.router.complete(
        descriptor,
        [Message(role="system", content=system), Message(role="user", content=body)],
        ctx.router_ctx,
    )
    if result.completion is None:  # Router raises when nothing succeeds; defensive only.
        raise AgentOutputError("router returned no completion")
    return JsonResult(
        data=parse_json_object(result.completion.text),
        endpoint=result.record.chosen_endpoint,
        tier=result.record.chosen_tier,
        escalated=escalation_reason is not None,
    )


def call_with_escalation(
    ctx: AgentContext,
    task_type: str,
    system: str,
    payload: dict[str, Any],
    *,
    acceptable: Callable[[dict[str, Any]], bool],
    est_output: int = 800,
    reason: str = "low_confidence",
) -> JsonResult:
    """Agent-in-the-loop escalation (docs/03 §5): ask a higher tier only when the first
    answer is not acceptable; if no higher tier is allowed, flag for a human (ADR-012)."""
    first = call_json(ctx, task_type, system, payload, est_output)
    if acceptable(first.data):
        return first
    try:
        second = call_json(ctx, task_type, system, payload, est_output, escalation_reason=reason)
    except NoEligibleModel:
        first.needs_human = True
        return first
    if not acceptable(second.data):
        second.needs_human = True
    return second
