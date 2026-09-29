"""HITL: dispositions, reason codes, telemetry, citation overrides, walls, few-shot learning."""

from sqlalchemy import select
from travo_api.db import tenant_session
from travo_api.models import TelemetryEvent

from tests.conftest import create_matter, review_document, run_reviews, upload


def _findings(client, t, rid, who="admin"):
    return client.get(f"/v1/reviews/{rid}/findings", headers=t.headers(who)).json()


def test_disposition_validation_and_telemetry(client, make_tenant):
    t = make_tenant()
    _, _, review = review_document(client, t)
    f = next(x for x in _findings(client, t, review["id"]) if x["rule_key"] == "term_length")
    url = f"/v1/findings/{f['id']}"
    h = t.headers()
    assert client.patch(url, json={"action": "reject"}, headers=h).status_code == 422
    assert client.patch(url, json={"action": "edit"}, headers=h).status_code == 422
    assert (
        client.patch(url, json={"action": "reject", "reason_code": "bogus"}, headers=h).status_code
        == 422
    )
    r = client.patch(
        url,
        json={
            "action": "reject",
            "reason_code": "too_aggressive",
            "note": "Client accepts 2 years",
        },
        headers=h,
    )
    assert r.status_code == 200 and r.json()["disposition"] == "rejected"
    r = client.patch(
        url, json={"action": "edit", "edited_text": "Term: four (4) years."}, headers=h
    )
    assert r.json()["disposition"] == "edited"
    with tenant_session(t.tenant_id) as s:
        events = list(
            s.scalars(
                select(TelemetryEvent)
                .where(TelemetryEvent.subject_id == f["id"])
                .order_by(TelemetryEvent.id)
            )
        )
    types = [e.event_type for e in events]
    assert types == ["finding.dispositioned", "finding.dispositioned", "redline.edited"]
    assert events[0].payload["reason_code"] == "too_aggressive"
    assert events[1].payload["previous"] == "rejected"
    assert events[2].payload["final"] == "Term: four (4) years."


def test_rejected_finding_citations_do_not_block(client, make_tenant):
    t = make_tenant()
    _, _, review = review_document(client, t)
    for f in _findings(client, t, review["id"]):
        if f["severity"] != "info":
            action = (
                {"action": "reject", "reason_code": "not_relevant_to_client"}
                if f["kind"] == "law"
                else {"action": "accept"}
            )
            client.patch(f"/v1/findings/{f['id']}", json=action, headers=t.headers())
    gate = client.get(f"/v1/reviews/{review['id']}/export-gate", headers=t.headers()).json()
    assert gate["open"], gate


def test_citation_override_requires_senior_role(client, make_tenant):
    t = make_tenant()
    m = create_matter(client, t, who="partner")
    client.put(
        f"/v1/matters/{m['id']}/members",
        json={
            "members": [
                {"user_id": t.users["partner"], "access": "member"},
                {"user_id": t.users["associate"], "access": "member"},
            ]
        },
        headers=t.headers("partner"),
    )
    _, _, review = review_document(client, t, who="partner", matter=m)
    law = next(f for f in _findings(client, t, review["id"], "partner") if f["citations"])
    cid = law["citations"][0]["id"]
    body = {"reason": "Checked against the official text myself."}
    assert (
        client.post(
            f"/v1/citations/{cid}/override", json=body, headers=t.headers("associate")
        ).status_code
        == 403
    )
    r = client.post(f"/v1/citations/{cid}/override", json=body, headers=t.headers("partner"))
    assert r.status_code == 200 and r.json()["override_reason"]
    assert (
        client.post(
            f"/v1/citations/{cid}/override", json={"reason": "short"}, headers=t.headers("partner")
        ).status_code
        == 422
    )


def test_walls_apply_to_reviews_findings_exports(client, make_tenant):
    t = make_tenant(roles={"partner": "partner", "lateral": "associate"})
    m = create_matter(client, t, who="partner")
    _, _, review = review_document(client, t, who="partner", matter=m)
    f = _findings(client, t, review["id"], "partner")[0]
    for who in ("lateral", "admin"):
        h = t.headers(who)
        assert client.get(f"/v1/reviews/{review['id']}", headers=h).status_code == 404
        assert client.get(f"/v1/reviews/{review['id']}/findings", headers=h).status_code == 404
        assert (
            client.patch(
                f"/v1/findings/{f['id']}", json={"action": "accept"}, headers=h
            ).status_code
            == 404
        )
        assert client.get(f"/v1/matters/{m['id']}/reviews", headers=h).status_code == 404


def test_few_shot_learns_firm_wording_but_respects_walls(client, make_tenant):
    t = make_tenant(roles={"partner": "partner", "other": "partner"})
    firm_wording = "The aggregate liability of each party is capped at RM2,000,000 (firm form)."

    # Matter 1 (partner): lawyer edits the liability-cap redline.
    _, _, r1 = review_document(client, t, "my_one_way_nda", who="partner")
    cap = next(
        f
        for f in _findings(client, t, r1["id"], "partner")
        if f["rule_key"] == "liability_cap_floor"
    )
    assert "RM500,000" in cap["suggested_redline"]
    client.patch(
        f"/v1/findings/{cap['id']}",
        json={"action": "edit", "edited_text": firm_wording},
        headers=t.headers("partner"),
    )

    # Matter 2, same partner: Travo now proposes the firm's own wording.
    _, _, r2 = review_document(client, t, "my_one_way_nda", who="partner")
    cap2 = next(
        f
        for f in _findings(client, t, r2["id"], "partner")
        if f["rule_key"] == "liability_cap_floor"
    )
    assert cap2["suggested_redline"] == firm_wording

    # Matter 3, a partner outside matter 1's wall: no leakage of walled wording.
    _, _, r3 = review_document(client, t, "my_one_way_nda", who="other")
    cap3 = next(
        f for f in _findings(client, t, r3["id"], "other") if f["rule_key"] == "liability_cap_floor"
    )
    assert cap3["suggested_redline"] != firm_wording
    assert "RM500,000" in cap3["suggested_redline"]


def test_inline_reviews_mode(client, make_tenant, monkeypatch):
    from travo_api.config import get_settings

    monkeypatch.setattr(get_settings(), "inline_reviews", True)
    t = make_tenant()
    m = create_matter(client, t)
    doc = upload(client, t, m["id"]).json()
    rid = client.post(f"/v1/documents/{doc['id']}/reviews", json={}, headers=t.headers()).json()[
        "id"
    ]
    # Background task ran after the response, once the request transaction committed.
    assert client.get(f"/v1/reviews/{rid}", headers=t.headers()).json()["status"] == "completed"
    assert run_reviews() == 0


def test_playbook_versions_and_firm_precedence(client, make_tenant):
    t = make_tenant(roles={"associate": "associate", "km": "km"})
    assert (
        client.post(
            "/v1/playbooks", json={"from_starter": "nda_sg"}, headers=t.headers("associate")
        ).status_code
        == 403
    )
    r = client.post(
        "/v1/playbooks",
        json={"from_starter": "nda_sg", "key": "acme_nda_sg"},
        headers=t.headers("km"),
    )
    assert r.status_code == 201 and r.json()["version"] == 1
    spec = r.json()["spec"]
    spec["rules"] = [x for x in spec["rules"] if x["key"] != "personal_data"]
    import yaml

    r2 = client.post("/v1/playbooks", json={"yaml": yaml.safe_dump(spec)}, headers=t.headers("km"))
    assert r2.json()["version"] == 2
    assert (
        client.post(
            "/v1/playbooks", json={"yaml": "key: BAD KEY"}, headers=t.headers("km")
        ).status_code
        == 422
    )
    listed = {
        (p["key"], p["source"]) for p in client.get("/v1/playbooks", headers=t.headers()).json()
    }
    assert ("acme_nda_sg", "tenant") in listed and ("nda_sg", "starter") in listed
    _, _, review = review_document(client, t)
    assert (review["playbook_key"], review["playbook_version"], review["playbook_source"]) == (
        "acme_nda_sg",
        2,
        "tenant",
    )
    assert "personal_data" not in {f["rule_key"] for f in _findings(client, t, review["id"])}


def test_spend_report(client, make_tenant):
    t = make_tenant()
    review_document(client, t, "my_one_way_nda")
    spend = client.get("/v1/admin/spend", headers=t.headers()).json()
    tasks = {row["key"] for row in spend["by_task"]}
    assert {
        "classify",
        "clause_extraction",
        "playbook_compare",
        "law_check",
        "validate_claim",
        "redline",
        "memo",
    } <= tasks
    assert client.get("/v1/admin/spend", headers=t.headers("partner")).status_code == 403
