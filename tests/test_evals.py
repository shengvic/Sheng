from evals.harness import evaluate


def test_gold_nda_eval_gate():
    # Regression gate (docs/11). Synthetic gold set: keep ≥ 0.9 until real NDAs land.
    scores = evaluate()
    assert scores["classification_accuracy"] == 1.0
    assert scores["clause_f1"] >= 0.9
