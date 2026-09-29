import pytest
import yaml
from pydantic import ValidationError
from travo_router import ModelPolicy, PolicyEngine, TaskDescriptor
from travo_router.policy import MatterContext

from tests.router_helpers import Ctx, catalogue

ENGINE = PolicyEngine()


def plan(task="clause_extraction", policy=None, matter=None, byo=None, **d):
    desc = TaskDescriptor(
        task_type=task,
        tenant_id="t",
        matter_id="m",
        est_input_tokens=10_000,
        est_output_tokens=1_000,
        **d,
    )
    return ENGINE.plan(
        desc,
        policy or ModelPolicy(),
        catalogue().all(),
        matter=matter,
        byo_providers=byo if byo is not None else {"openai", "anthropic"},
    )


def reasons(p):
    return {f.endpoint_id: f.reason for f in p.filtered}


def test_default_prefers_t1_cheapest_then_lower_tier():
    p = plan()
    assert [c.endpoint_id for c in p.candidates] == ["ow-t1", "ow-t1-sg", "rules"]
    assert reasons(p)["openai"] == "tier_above_rule"


def test_escalation_goes_to_frontier():
    p = plan("law_check", escalation_reason="low_confidence")
    assert p.preferred_tier == "T2"
    assert [c.endpoint_id for c in p.candidates][:2] == ["openai", "anthropic"]
    assert "or-anthropic" in reasons(p)  # proxy not enabled by default


def test_matter_conflict_blocks_vendor_and_aggregated_routes():
    p = plan("law_check", matter=MatterContext(deny_providers=["anthropic"]), escalation_reason="x")
    ids = [c.endpoint_id for c in p.candidates]
    assert "anthropic" not in ids and "or-anthropic" not in ids
    assert reasons(p)["anthropic"] == "matter_conflict_deny"
    assert reasons(p)["or-anthropic"] == "matter_conflict_deny"
    assert ids[0] == "openai"


def test_deny_aggregator_blocks_hosted_routes():
    p = plan(policy=ModelPolicy.model_validate({"providers": {"deny": ["fireworks"]}}))
    assert reasons(p)["ow-t1"] == "tenant_provider_denied"
    assert p.candidates[0].endpoint_id == "ow-t1-sg"


def test_allowlist_keeps_first_party_but_drops_unlisted_hosts():
    policy = ModelPolicy.model_validate({"providers": {"allow": ["baseten", "anthropic"]}})
    p = plan(policy=policy)
    assert [c.endpoint_id for c in p.candidates] == ["ow-t1-sg", "rules"]
    assert reasons(p)["ow-t1"] == "tenant_provider_not_allowed"


def test_residency_limits_to_in_region_or_self_hosted():
    p = plan(matter=MatterContext(residency="SG"))
    assert [c.endpoint_id for c in p.candidates] == ["ow-t1-sg", "rules"]
    assert reasons(p)["ow-t1"] == "residency"


def test_restricted_without_residency_requires_self_hosted():
    p = plan(sensitivity="restricted")
    assert [c.endpoint_id for c in p.candidates] == ["rules"]


def test_byo_requires_credential_and_proxy_requires_opt_in():
    p = plan("law_check", byo=set(), escalation_reason="x")
    assert reasons(p)["openai"] == "no_byo_credential"
    policy = ModelPolicy.model_validate(
        {"billing": {"mode": "byo_keys", "fallback_to_proxy": True}}
    )
    p = plan("law_check", policy=policy, byo=set(), escalation_reason="x")
    assert p.candidates[0].endpoint_id == "or-anthropic"


def test_quality_floor_and_capabilities():
    p = plan(quality_floor="high")
    assert "rules" not in [c.endpoint_id for c in p.candidates]
    p = plan(requires=["vision"])
    assert p.empty
    assert reasons(p)["rules"].startswith("capability_missing")


def test_budget_exceeded_flag():
    policy = ModelPolicy.model_validate({"budgets": {"per_matter_usd": 0.001}})
    desc = TaskDescriptor(
        task_type="clause_extraction",
        tenant_id="t",
        matter_id="m",
        est_input_tokens=10_000,
        est_output_tokens=1_000,
        quality_floor="high",
    )
    p = ENGINE.plan(desc, policy, catalogue().all(), spent_matter_usd=5)
    assert p.empty and p.budget_exceeded


def test_policy_yaml_matter_override():
    policy = ModelPolicy.from_yaml("""
matter_overrides:
  m:
    deny_providers: [openai]
    residency: SG
""")
    p = plan("law_check", policy=policy, escalation_reason="x")
    r = reasons(p)
    assert r["openai"] == "matter_conflict_deny"
    assert r["anthropic"] == "residency"


@pytest.mark.parametrize("bad", ["providers: {allow: 3}", "defaults: {classify: {tier: T9}}"])
def test_invalid_policy_rejected(bad):
    with pytest.raises((ValidationError, yaml.YAMLError)):
        ModelPolicy.from_yaml(bad)


def test_ctx_helper_is_consistent():
    assert Ctx().policy() == ModelPolicy()
