"""Router-backed entailment judge for the citation validator (task validate_claim)."""

from __future__ import annotations

from travo_rag.citations import Judge
from travo_rag.retrieval import LegalUnitHit

from travo_agents.base import AgentContext, call_json
from travo_agents.prompts import load_prompt

STATUSES = {"supported", "partial", "contradicted", "not_found"}


def router_judge(ctx: AgentContext) -> tuple[Judge, list[str]]:
    """Returns the judge and a list that collects the endpoints used (for `checker`)."""
    used: list[str] = []

    def judge(pairs: list[tuple[str, LegalUnitHit]]) -> list[tuple[str, float]]:
        payload = {
            "claims": [
                {"i": i, "claim": claim, "source_heading": u.heading, "source_text": u.text[:3000]}
                for i, (claim, u) in enumerate(pairs)
            ]
        }
        res = call_json(
            ctx, "validate_claim", load_prompt("validate_claim"), payload, 60 * len(pairs)
        )
        used.append(res.endpoint or "unknown")
        by_i: dict[int, tuple[str, float]] = {}
        for item in res.data.get("results", []) or []:
            try:
                status = str(item["status"])
                by_i[int(item["i"])] = (
                    status if status in STATUSES else "not_found",
                    max(0.0, min(float(item.get("score", 0)), 1.0)),
                )
            except (KeyError, TypeError, ValueError):
                continue
        return [by_i.get(i, ("not_found", 0.0)) for i in range(len(pairs))]

    return judge, used
