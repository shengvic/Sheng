from tests.conftest import create_matter, upload

POLICY = """
billing: {mode: mixed}
providers: {deny: [openai]}
defaults:
  law_check: {tier: T1, escalate_to: T2}
"""


def test_policy_versioning_and_dry_run(client, make_tenant):
    t = make_tenant()
    h = t.headers()
    assert client.get("/v1/admin/model-policy", headers=h).json()["source"] == "default"
    assert (
        client.put(
            "/v1/admin/model-policy", json={"yaml": "providers: {allow: 3}"}, headers=h
        ).status_code
        == 422
    )
    r = client.put("/v1/admin/model-policy", json={"yaml": POLICY}, headers=h)
    assert r.json()["version"] == 1
    assert (
        client.put("/v1/admin/model-policy", json={"yaml": POLICY}, headers=h).json()["version"]
        == 2
    )
    got = client.get("/v1/admin/model-policy", headers=h).json()
    assert got["source"] == "tenant" and got["version"] == 2

    client.post(
        "/v1/admin/provider-credentials",
        json={"provider": "anthropic", "api_key": "sk-ant-00000000"},
        headers=h,
    )
    matter = create_matter(client, t, deny_providers=["anthropic"])
    plan = client.post(
        "/v1/admin/model-policy/dry-run",
        json={"task_type": "law_check", "matter_id": matter["id"], "escalation_reason": "x"},
        headers=h,
    ).json()
    reasons = {f["endpoint_id"]: f["reason"] for f in plan["filtered"]}
    assert reasons["openai-byo-frontier"] == "tenant_provider_denied"
    assert reasons["anthropic-byo-frontier"] == "matter_conflict_deny"
    assert reasons["openrouter-proxy-anthropic"] == "matter_conflict_deny"
    assert plan["candidates"] == []

    # Without the conflicted matter, the BYO Anthropic key makes it eligible.
    plan = client.post(
        "/v1/admin/model-policy/dry-run",
        json={"task_type": "law_check", "escalation_reason": "x"},
        headers=h,
    ).json()
    assert [c["endpoint_id"] for c in plan["candidates"]] == ["anthropic-byo-frontier"]

    bad = client.post("/v1/admin/model-policy/dry-run", json={"task_type": "nope"}, headers=h)
    assert bad.status_code == 422


def test_document_needs_model_when_policy_blocks_everything(client, make_tenant):
    t = make_tenant()
    client.put(
        "/v1/admin/model-policy", json={"yaml": "providers: {deny: [travo]}"}, headers=t.headers()
    )
    matter = create_matter(client, t)
    doc = upload(client, t, matter["id"]).json()
    assert doc["parse_status"] == "needs_model"
    decisions = client.get("/v1/admin/routing-decisions", headers=t.headers()).json()
    assert decisions[0]["outcome"] == "no_candidate"
    assert all(
        f["reason"]
        in {"tenant_provider_denied", "no_byo_credential", "endpoint_disabled", "tier_above_rule"}
        for f in decisions[0]["filtered"]
    )
