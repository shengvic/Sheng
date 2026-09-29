"""API endpoints added for the web review canvas."""

from urllib.parse import quote

from tests.conftest import review_document


def test_me(client, make_tenant):
    t = make_tenant()
    me = client.get("/v1/me", headers=t.headers("partner")).json()
    assert me["role"] == "partner" and me["tenant_id"] == t.tenant_id
    assert me["tenant_name"].startswith("Firm")
    assert client.get("/v1/me").status_code == 401


def test_legal_unit_lookup(client, make_tenant):
    t = make_tenant()
    uid = "SG/FIXTURE-CONTRACT-TERMS#s 3"
    r = client.get(f"/v1/legal-units/{quote(uid, safe='')}", headers=t.headers())
    assert r.status_code == 200, r.text
    unit = r.json()
    assert unit["id"] == uid and unit["is_fixture"] is True
    assert "FIXTURE" in unit["pinpoint"] and "liquidated damages" in unit["text"]
    missing = quote("SG/NOPE#s 1", safe="")
    assert client.get(f"/v1/legal-units/{missing}", headers=t.headers()).status_code == 404
    assert client.get(f"/v1/legal-units/{quote(uid, safe='')}").status_code == 401


def test_review_routing_visible_to_members_only(client, make_tenant):
    t = make_tenant(roles={"partner": "partner", "lateral": "associate"})
    _, _, review = review_document(client, t, "my_one_way_nda", who="partner")
    rows = client.get(f"/v1/reviews/{review['id']}/routing", headers=t.headers("partner")).json()
    tasks = [r["task_type"] for r in rows]
    assert tasks[:2] == ["classify", "clause_extraction"]
    assert {"playbook_compare", "law_check", "memo"} <= set(tasks)
    assert all(r["chosen_endpoint"] == "travo-rules-v0" for r in rows)
    assert all(r["escalation_reason"] is None for r in rows)
    for who in ("lateral", "admin"):
        r = client.get(f"/v1/reviews/{review['id']}/routing", headers=t.headers(who))
        assert r.status_code == 404


def test_reset_disposition_undoes_and_reopens_gate(client, make_tenant):
    t = make_tenant()
    _, _, review = review_document(client, t, "sg_mutual_nda")
    findings = client.get(f"/v1/reviews/{review['id']}/findings", headers=t.headers()).json()
    issues = [f for f in findings if f["severity"] != "info"]
    for f in issues:
        client.patch(f"/v1/findings/{f['id']}", json={"action": "accept"}, headers=t.headers())
    gate = f"/v1/reviews/{review['id']}/export-gate"
    assert client.get(gate, headers=t.headers()).json()["open"]
    r = client.patch(
        f"/v1/findings/{issues[0]['id']}", json={"action": "reset"}, headers=t.headers()
    )
    assert r.status_code == 200 and r.json()["disposition"] is None
    blocking = client.get(gate, headers=t.headers()).json()["blocking"]
    assert [b["finding_id"] for b in blocking] == [issues[0]["id"]]


def test_dev_token_is_idempotent(client, database):
    from travo_api.cli import dev_token

    t1, t2 = dev_token(), dev_token()
    me1 = client.get("/v1/me", headers={"Authorization": f"Bearer {t1}"}).json()
    me2 = client.get("/v1/me", headers={"Authorization": f"Bearer {t2}"}).json()
    assert me1["role"] == "partner" and me1["tenant_name"] == "Travo Demo LLP"
    assert me1["id"] == me2["id"]
