"""Memo writer: executive summary + negotiation points from findings (docs/05 §6)."""

from __future__ import annotations

from typing import Any

from travo_agents.base import AgentContext, call_json
from travo_agents.prompts import load_prompt


def write_memo(ctx: AgentContext, findings: list[dict[str, Any]]) -> dict[str, Any]:
    res = call_json(ctx, "memo", load_prompt("memo"), {"findings": findings}, 800)
    points = res.data.get("negotiation_points") or []
    return {
        "executive_summary": str(res.data.get("executive_summary", ""))[:4000],
        "negotiation_points": [str(p)[:500] for p in points if p][:20],
        "model_endpoint": res.endpoint,
    }
