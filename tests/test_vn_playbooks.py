"""Vietnamese starter playbooks and jurisdiction pack (R3). Drafts pending lawyer review."""

from __future__ import annotations

from pathlib import Path

import pytest
from travo_agents.checks import evaluate_rule
from travo_agents.lawcheck import load_packs
from travo_agents.playbooks import ClauseRule, load_starter_playbooks, select_playbook

ROOT = Path(__file__).resolve().parents[1]
BOOKS = load_starter_playbooks(ROOT / "config/playbooks")


@pytest.mark.parametrize(
    ("ctype", "key"),
    [("NDA", "nda_vn"), ("SALE", "commercial_vn"), ("MSA", "services_vn"), ("DPA", "dpa_vn")],
)
def test_vietnamese_playbook_selected_by_type_and_law(ctype, key):
    chosen = select_playbook(ctype, "VN", [], list(BOOKS.values()))
    assert chosen is not None and chosen[0].key == key
    pb = chosen[0]
    assert all(r.rationale for r in pb.rules)
    # Every redline has both language versions.
    assert all(bool(r.redline_template) == bool(r.redline_template_vi) for r in pb.rules)


def test_penalty_cap_percent_check():
    rule = ClauseRule(key="cap", clause_key="penalty", max_percent=8)
    over = [{"i": 3, "key": "penalty", "heading": "Phạt vi phạm", "text": "mức phạt 12% giá trị"}]
    ok = [{"i": 3, "key": "penalty", "heading": "Penalty", "text": "a penalty of 8% of the value"}]
    assert evaluate_rule(rule, over)["classification"] == "non_standard"
    assert evaluate_rule(rule, ok)["classification"] == "standard"


def test_vnd_currency_rule_is_not_fooled_by_hop_dong():
    rule = BOOKS["commercial_vn"].rules[1]
    assert rule.key == "price_currency_vnd"
    usd = [
        {"i": 1, "key": "price_payment", "heading": "Giá", "text": "Giá hợp đồng là 10.000 USD."}
    ]
    vnd = [{"i": 1, "key": "price_payment", "heading": "Giá", "text": "Giá là 100.000.000 VND."}]
    assert evaluate_rule(rule, usd)["classification"] == "non_standard"
    assert evaluate_rule(rule, vnd)["classification"] == "standard"


def test_vn_pack_has_vietnamese_queries_and_no_statute_text():
    pack = load_packs(ROOT / "config/jurisdiction_packs")["VN"]
    assert len(pack.rules) >= 8
    for r in pack.rules:
        assert r.issue and r.issue_vi and r.query
        assert len(r.query) < 120  # search terms, not quoted law


def test_vn_review_runs_law_checks_without_sources_as_needs_lawyer(client, make_tenant):
    from evals import vn_fixtures as vn
    from tests.conftest import DOCX_MIME, create_matter, run_reviews

    t = make_tenant()
    matter = create_matter(client, t, jurisdictions=["VN"])
    doc = client.post(
        f"/v1/matters/{matter['id']}/documents",
        files={"file": ("nda.docx", vn.table_docx(), DOCX_MIME)},
        headers=t.headers(),
    ).json()
    run = client.post(f"/v1/documents/{doc['id']}/reviews", json={}, headers=t.headers()).json()
    run_reviews()
    findings = client.get(f"/v1/reviews/{run['id']}/findings", headers=t.headers()).json()
    law = [f for f in findings if f["kind"] == "law"]
    assert law and all(f["rule_key"].startswith("law:VN:") for f in law)
    assert all(f["status"] == "needs_human" for f in law)  # no verified VN sources yet
    playbook = {f["rule_key"]: f for f in findings if f["kind"] == "playbook"}
    assert playbook["governing_law_vn"]["classification"] == "standard"
    assert playbook["language_prevailing"]["classification"] == "standard"
    assert playbook["exclusions_present"]["classification"] == "missing"
