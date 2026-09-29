import pytest
from travo_agents.checks import amounts, durations_months, evaluate_rule
from travo_agents.playbooks import ClauseRule, Playbook, select_playbook


@pytest.mark.parametrize(
    "text,months",
    [
        ("continues for three (3) years", [36]),
        ("for 18 months", [18]),
        ("trong thời hạn 2 năm", [24]),
        ("selama 6 bulan", [6]),
        ("no period", []),
    ],
)
def test_durations(text, months):
    assert durations_months(text) == months


def test_amounts():
    assert amounts("shall not exceed RM10,000 or S$ 2,500.50") == [10000.0, 2500.0]


def rule(**kw):
    return ClauseRule(key="r", clause_key="term_and_termination", **kw)


def clauses(text):
    return [{"i": 1, "key": "term_and_termination", "heading": "Term", "text": text}]


def test_rule_outcomes():
    r = rule(required=True, min_duration_months=36, fallback_min_duration_months=24)
    assert evaluate_rule(r, clauses("lasts 3 years"))["classification"] == "standard"
    assert evaluate_rule(r, clauses("lasts 2 years"))["classification"] == "fallback"
    assert evaluate_rule(r, clauses("lasts 6 months"))["classification"] == "non_standard"
    assert evaluate_rule(r, clauses("until terminated"))["classification"] == "non_standard"
    assert evaluate_rule(r, [])["classification"] == "missing"
    assert evaluate_rule(rule(), []) is None  # optional & absent → no finding
    assert (
        evaluate_rule(rule(must_not_include_any=["perpetual"]), clauses("perpetual term"))[
            "classification"
        ]
        == "non_standard"
    )
    assert (
        evaluate_rule(rule(max_amount=100), clauses("fee of $500"))["classification"]
        == "non_standard"
    )


def test_select_playbook_precedence():
    starter = Playbook(
        key="nda_sg",
        name="s",
        applies_to={"contract_types": ["NDA"], "governing_laws": ["SG"]},
        rules=[],
    )
    firm = starter.model_copy(update={"key": "firm_nda"})
    assert select_playbook("NDA", "SG", [firm], [starter])[1] == "tenant"
    assert select_playbook("NDA", "SG", [], [starter])[1] == "starter"
    assert select_playbook("NDA", "VN", [firm], [starter]) is None
