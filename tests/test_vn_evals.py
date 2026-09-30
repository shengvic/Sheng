"""Vietnam pilot release gate on the synthetic bilingual set (evals/vn_gold.py, docs/11)."""

from __future__ import annotations

from evals.harness import VN_GATES, evaluate_vn


def test_vn_eval_meets_release_gates():
    scores = evaluate_vn(verbose=False)
    failed = {k: round(v, 3) for k, v in scores.items() if v < VN_GATES[k]}
    assert not failed, failed
