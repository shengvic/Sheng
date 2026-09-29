"""Offline eval: run the P0 pipeline on gold NDAs, report classification and clause-key P/R/F1.

    uv run python -m evals.harness            # routes through travo_rules (no keys needed)

Uses the same router + agents as production with an in-memory RouterContext.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from travo_agents.base import AgentContext
from travo_agents.compare import compare
from travo_agents.pipeline import run_pipeline
from travo_agents.playbooks import load_starter_playbooks
from travo_agents.rules_model import RulesProvider
from travo_rag.parsing import DOCX_MIME, parse
from travo_router import EndpointRegistry, ModelPolicy, Router
from travo_router.client import RoutingRecord
from travo_router.policy import MatterContext

ROOT = Path(__file__).resolve().parents[1]
GOLD = Path(__file__).parent / "gold" / "nda"


class EvalContext:
    def __init__(self, policy: ModelPolicy):
        self._policy = policy
        self.records: list[RoutingRecord] = []

    def policy(self) -> ModelPolicy:
        return self._policy

    def matter(self, matter_id: str | None) -> MatterContext | None:
        return None

    def byo_providers(self) -> set[str]:
        return set()

    def api_key(self, provider: str, billing: str, api_key_env: str | None) -> str | None:
        return None

    def spend(self, matter_id: str | None) -> tuple[float, float]:
        return 0.0, 0.0

    def record(self, record: RoutingRecord) -> str | None:
        self.records.append(record)
        return None


def evaluate() -> dict[str, float]:
    registry = EndpointRegistry.from_yaml(ROOT / "config" / "endpoints.yaml")
    for ep in registry.all():
        if ep.api_key_env:
            ep.enabled = False
    router = Router(registry, {"travo_rules": RulesProvider()})
    policy = ModelPolicy.from_yaml((ROOT / "config" / "default_policy.yaml").read_text())
    tp: Counter[str] = Counter()
    fp: Counter[str] = Counter()
    fn: Counter[str] = Counter()
    meta_ok = meta_total = 0
    books = load_starter_playbooks(ROOT / "config" / "playbooks")
    finding_ok = finding_total = 0
    for gold_path in sorted(GOLD.glob("*.json")):
        gold = json.loads(gold_path.read_text())
        blocks = parse(gold_path.with_suffix(".docx").read_bytes(), DOCX_MIME)
        ctx = AgentContext(
            router=router, router_ctx=EvalContext(policy), tenant_id="eval", matter_id=None
        )
        result = run_pipeline(ctx, blocks)
        for field, got in (
            ("contract_type", result.classification.contract_type),
            ("governing_law", result.classification.governing_law),
        ):
            meta_total += 1
            meta_ok += int(got == gold[field])
        predicted = [c.key for c in result.clauses]
        expected = [c["key"] for c in gold["clauses"]]
        if len(predicted) != len(expected):
            print(f"  ! {gold_path.stem}: {len(predicted)} segments vs {len(expected)} gold")
        for p, e in zip(predicted, expected, strict=False):
            if p == e:
                tp[e] += 1
            else:
                fp[p] += 1
                fn[e] += 1
        for e in expected[len(predicted) :]:
            fn[e] += 1
        print(
            f"  {gold_path.stem}: {sum(p == e for p, e in zip(predicted, expected, strict=False))}"
            f"/{len(expected)} clauses correct"
        )
        expected_findings = gold.get("expected_findings") or {}
        if gold.get("playbook") and expected_findings:
            clauses = [
                {"i": c.index, "key": c.key, "heading": c.heading, "text": c.text}
                for c in result.clauses
            ]
            got = {
                d.rule_key: d.classification for d in compare(ctx, books[gold["playbook"]], clauses)
            }
            for rule_key, cls in expected_findings.items():
                finding_total += 1
                if got.get(rule_key) == cls:
                    finding_ok += 1
                else:
                    print(
                        f"  ! {gold_path.stem}: {rule_key} expected {cls}, got {got.get(rule_key)}"
                    )
    t, f_p, f_n = sum(tp.values()), sum(fp.values()), sum(fn.values())
    precision = t / (t + f_p) if t + f_p else 0.0
    recall = t / (t + f_n) if t + f_n else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    scores = {
        "clause_precision": precision,
        "clause_recall": recall,
        "clause_f1": f1,
        "classification_accuracy": meta_ok / meta_total if meta_total else 0.0,
        "finding_accuracy": finding_ok / finding_total if finding_total else 0.0,
    }
    for k, v in scores.items():
        print(f"{k:>24}: {v:.3f}")
    return scores


if __name__ == "__main__":
    evaluate()
