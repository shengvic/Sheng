"""Agent-in-the-loop escalation (docs/03 §5) through the real review workflow."""

import json

import pytest
from travo_agents.rules_model import RulesProvider
from travo_router import EndpointRegistry, Router
from travo_router.providers import FakeProvider
from travo_router.registry import Endpoint

from tests.conftest import create_matter, review_document

RULES = RulesProvider()


def _rules_json(ep, desc, messages):
    return json.loads(RULES.complete(ep, desc, messages, None).text)


def make_router(t1_compare_conf=0.2, t1_bad_law=True):
    registry = EndpointRegistry(
        [
            Endpoint(
                id="fake-t1",
                provider="travo",
                via="fireworks",
                model="t1",
                tier="T1",
                billing="travo",
                adapter="fake_t1",
                regions=["*"],
                capabilities=["json_output", "long_context"],
                max_context=500_000,
            ),
            Endpoint(
                id="fake-t2-anthropic",
                provider="anthropic",
                model="t2",
                tier="T2",
                billing="byo",
                adapter="fake_t2",
                regions=["US"],
                capabilities=["json_output", "long_context"],
                max_context=500_000,
                price_in_per_mtok=3,
                price_out_per_mtok=15,
            ),
        ]
    )
    ep1, ep2 = registry.get("fake-t1"), registry.get("fake-t2-anthropic")

    def t1(desc, messages):
        out = _rules_json(ep1, desc, messages)
        if desc.task_type == "playbook_compare":
            for f in out["findings"]:
                f["confidence"] = t1_compare_conf
        if desc.task_type == "law_check" and t1_bad_law and out.get("note"):
            out["note"] = "Penalty clauses are always enforceable [[src:SG/INVENTED#s 99]]."
        return json.dumps(out)

    t1p = FakeProvider(t1)
    t2p = FakeProvider(lambda d, m: json.dumps(_rules_json(ep2, d, m)))
    return Router(registry, {"fake_t1": t1p, "fake_t2": t2p}), t1p, t2p


@pytest.fixture
def fake_router(monkeypatch):
    def install(**kw):
        router, t1p, t2p = make_router(**kw)
        import travo_api.ingest
        import travo_api.reviews

        monkeypatch.setattr(travo_api.reviews, "get_router", lambda: router)
        monkeypatch.setattr(travo_api.ingest, "get_router", lambda: router)
        return t1p, t2p

    return install


def _byo(client, t):
    client.post(
        "/v1/admin/provider-credentials",
        json={"provider": "anthropic", "api_key": "sk-ant-test-0000"},
        headers=t.headers(),
    )


def test_low_confidence_and_bad_citations_escalate_to_t2(client, make_tenant, fake_router):
    t1p, t2p = fake_router()
    t = make_tenant()
    _byo(client, t)
    _, _, review = review_document(client, t)
    assert review["status"] == "completed", review
    findings = client.get(f"/v1/reviews/{review['id']}/findings", headers=t.headers()).json()
    pb = [f for f in findings if f["kind"] == "playbook"]
    assert pb and all(f["escalated"] and f["model_tier"] == "T2" for f in pb)
    law = [f for f in findings if f["kind"] == "law"]
    assert law and all(f["escalated"] and f["status"] == "needs_review" for f in law)
    assert all(c["status"] == "supported" for f in law for c in f["citations"])
    t2_tasks = {d.task_type for _, d in t2p.calls}
    assert {"playbook_compare", "law_check"} <= t2_tasks
    # T1 law note was retried once before escalating.
    t1_law = [d for _, d in t1p.calls if d.task_type == "law_check"]
    assert len(t1_law) == 2 * len(law)
    decisions = client.get("/v1/admin/routing-decisions?limit=500", headers=t.headers()).json()
    assert any(d["chosen_tier"] == "T2" and d["task_type"] == "playbook_compare" for d in decisions)


def test_conflicted_frontier_means_human_review(client, make_tenant, fake_router):
    t1p, t2p = fake_router()
    t = make_tenant()
    _byo(client, t)
    m = create_matter(client, t, deny_providers=["anthropic"])
    _, _, review = review_document(client, t, matter=m)
    assert review["status"] == "completed", review
    findings = client.get(f"/v1/reviews/{review['id']}/findings", headers=t.headers()).json()
    assert t2p.calls == []  # the conflicted vendor is never called
    assert all(f["status"] == "needs_human" for f in findings if f["kind"] == "law")
    pb = [f for f in findings if f["kind"] == "playbook"]
    assert all(f["status"] == "needs_human" and not f["escalated"] for f in pb)
    assert review["summary"]["needs_human"] == len(findings)
    law = [f for f in findings if f["kind"] == "law"]
    assert any(c["status"] == "invalid_source" for f in law for c in f["citations"])
    gate = client.get(f"/v1/reviews/{review['id']}/export-gate", headers=t.headers()).json()
    assert any(b["type"] == "citation_unsupported" for b in gate["blocking"])


def test_confident_t1_does_not_escalate(client, make_tenant, fake_router):
    t1p, t2p = fake_router(t1_compare_conf=0.95, t1_bad_law=False)
    t = make_tenant()
    _byo(client, t)
    _, _, review = review_document(client, t)
    assert review["status"] == "completed"
    assert t2p.calls == []
