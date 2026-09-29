"""Agent base: vendor-free; every model call goes through the router."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from travo_router import Router, TaskDescriptor
from travo_router.client import RouterContext
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


def call_json(
    ctx: AgentContext, task_type: str, system: str, payload: dict[str, Any], est_output: int = 800
) -> dict[str, Any]:
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
    )
    result = ctx.router.complete(
        descriptor,
        [Message(role="system", content=system), Message(role="user", content=body)],
        ctx.router_ctx,
    )
    if result.completion is None:  # Router raises when nothing succeeds; defensive only.
        raise AgentOutputError("router returned no completion")
    return parse_json_object(result.completion.text)
