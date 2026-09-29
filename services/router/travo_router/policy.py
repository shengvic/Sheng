"""Deterministic routing policy engine (docs/03 §4). No LLM in the policy path."""

from __future__ import annotations

from typing import Literal

import yaml
from pydantic import BaseModel, Field

from travo_router.descriptor import TaskDescriptor, TaskType, Tier
from travo_router.registry import Endpoint

TIER_RANK: dict[str, int] = {"T0": 0, "T1": 1, "T2": 2}
# Travo's own models on Travo-controlled infrastructure. Allowlists ("only these vendors")
# do not exclude first-party inference; explicit deny lists still do.
FIRST_PARTY = "travo"


class BillingPolicy(BaseModel):
    mode: Literal["byo_keys", "proxy", "mixed"] = "byo_keys"
    fallback_to_proxy: bool = False

    def proxy_allowed(self) -> bool:
        return self.mode in ("proxy", "mixed") or self.fallback_to_proxy

    def byo_allowed(self) -> bool:
        return self.mode in ("byo_keys", "mixed")


class ProviderPolicy(BaseModel):
    allow: list[str] | None = None  # None = all providers allowed
    deny: list[str] = Field(default_factory=list)


class TaskRule(BaseModel):
    tier: Tier = "T1"
    escalate_to: Tier | None = None


class MatterOverride(BaseModel):
    deny_providers: list[str] = Field(default_factory=list)
    allow_providers: list[str] | None = None
    residency: str | None = None


class Budgets(BaseModel):
    per_matter_usd: float | None = None
    per_month_usd: float | None = None


DEFAULT_RULES: dict[str, TaskRule] = {
    "classify": TaskRule(tier="T1"),
    "clause_extraction": TaskRule(tier="T1"),
    "playbook_compare": TaskRule(tier="T1", escalate_to="T2"),
    "law_check": TaskRule(tier="T1", escalate_to="T2"),
    "redline": TaskRule(tier="T1", escalate_to="T2"),
    "memo": TaskRule(tier="T1", escalate_to="T2"),
    "embed": TaskRule(tier="T0"),
    "rerank": TaskRule(tier="T0"),
    "validate_claim": TaskRule(tier="T1", escalate_to="T2"),
}


class ModelPolicy(BaseModel):
    """Tenant model policy; stored as versioned YAML (docs/03 §4)."""

    billing: BillingPolicy = Field(default_factory=BillingPolicy)
    providers: ProviderPolicy = Field(default_factory=ProviderPolicy)
    defaults: dict[TaskType, TaskRule] = Field(default_factory=dict)
    matter_overrides: dict[str, MatterOverride] = Field(default_factory=dict)
    budgets: Budgets = Field(default_factory=Budgets)

    @classmethod
    def from_yaml(cls, text: str) -> ModelPolicy:
        return cls.model_validate(yaml.safe_load(text) or {})

    def rule_for(self, task_type: str) -> TaskRule:
        return self.defaults.get(task_type) or DEFAULT_RULES.get(task_type) or TaskRule()  # type: ignore[call-overload]


class MatterContext(BaseModel):
    """Per-matter constraints held in the database (conflict profile, residency)."""

    deny_providers: list[str] = Field(default_factory=list)
    allow_providers: list[str] | None = None
    residency: str | None = None


class FilteredEndpoint(BaseModel):
    endpoint_id: str
    provider: str
    reason: str


class Candidate(BaseModel):
    endpoint_id: str
    provider: str
    tier: Tier
    est_cost_usd: float


class RoutingPlan(BaseModel):
    candidates: list[Candidate]
    filtered: list[FilteredEndpoint]
    preferred_tier: Tier
    budget_exceeded: bool = False

    @property
    def empty(self) -> bool:
        return not self.candidates


class PolicyEngine:
    def plan(
        self,
        descriptor: TaskDescriptor,
        policy: ModelPolicy,
        endpoints: list[Endpoint],
        *,
        matter: MatterContext | None = None,
        byo_providers: set[str] | None = None,
        spent_matter_usd: float = 0.0,
        spent_month_usd: float = 0.0,
    ) -> RoutingPlan:
        matter = self._merge_matter(policy, descriptor.matter_id, matter)
        byo_providers = byo_providers or set()
        rule = policy.rule_for(descriptor.task_type)
        preferred: Tier = rule.tier
        if descriptor.escalation_reason and rule.escalate_to:
            preferred = rule.escalate_to
        max_rank = max(TIER_RANK[rule.tier], TIER_RANK[rule.escalate_to or rule.tier])
        if descriptor.escalation_reason:
            max_rank = TIER_RANK[preferred]

        filtered: list[FilteredEndpoint] = []
        eligible: list[tuple[Endpoint, float]] = []
        budget_hits = 0
        for ep in endpoints:
            reason = self._hard_filter(ep, descriptor, policy, matter, byo_providers, max_rank)
            if reason is None:
                cost = ep.estimate_cost(descriptor.est_input_tokens, descriptor.est_output_tokens)
                reason = self._budget_filter(policy, cost, spent_matter_usd, spent_month_usd)
                if reason:
                    budget_hits += 1
                else:
                    eligible.append((ep, cost))
            if reason:
                filtered.append(
                    FilteredEndpoint(endpoint_id=ep.id, provider=ep.provider, reason=reason)
                )

        pref_rank = TIER_RANK[preferred]

        def order(item: tuple[Endpoint, float]) -> tuple[int, int, float]:
            ep, cost = item
            rank = TIER_RANK[ep.tier]
            # Preferred tier first, then lower tiers (cheaper fallbacks), then higher tiers.
            if rank == pref_rank:
                bucket = 0
            elif rank < pref_rank:
                bucket = 1
            else:
                bucket = 2
            distance = abs(rank - pref_rank)
            return (bucket, distance, cost)

        eligible.sort(key=order)
        candidates = [
            Candidate(endpoint_id=ep.id, provider=ep.provider, tier=ep.tier, est_cost_usd=cost)
            for ep, cost in eligible
        ]
        return RoutingPlan(
            candidates=candidates,
            filtered=filtered,
            preferred_tier=preferred,
            budget_exceeded=not candidates and budget_hits > 0,
        )

    @staticmethod
    def _merge_matter(
        policy: ModelPolicy, matter_id: str | None, matter: MatterContext | None
    ) -> MatterContext:
        merged = MatterContext() if matter is None else matter.model_copy(deep=True)
        override = policy.matter_overrides.get(matter_id or "")
        if override:
            merged.deny_providers = sorted(
                set(merged.deny_providers) | set(override.deny_providers)
            )
            if override.allow_providers is not None:
                merged.allow_providers = override.allow_providers
            merged.residency = merged.residency or override.residency
        return merged

    @staticmethod
    def _hard_filter(
        ep: Endpoint,
        d: TaskDescriptor,
        policy: ModelPolicy,
        matter: MatterContext,
        byo_providers: set[str],
        max_rank: int,
    ) -> str | None:
        # Conflict and vendor rules are reported first so audits show the policy reason even
        # when an endpoint is also unavailable.
        parties = ep.parties
        third_parties = parties - {FIRST_PARTY}
        if parties & set(matter.deny_providers):
            return "matter_conflict_deny"
        if matter.allow_providers is not None and not third_parties <= set(matter.allow_providers):
            return "matter_not_allowlisted"
        if parties & set(policy.providers.deny):
            return "tenant_provider_denied"
        allow = policy.providers.allow
        if allow is not None and not third_parties <= set(allow):
            return "tenant_provider_not_allowed"
        if not ep.enabled:
            return "endpoint_disabled"
        if matter.residency and not ep.serves_region(matter.residency):
            return "residency"
        if d.sensitivity == "restricted" and "*" not in ep.regions and not matter.residency:
            return "restricted_requires_self_hosted"
        missing = [c for c in d.requires if c not in ep.capabilities]
        if missing:
            return "capability_missing:" + ",".join(missing)
        if d.est_input_tokens + d.est_output_tokens > ep.max_context:
            return "context_too_long"
        if TIER_RANK[ep.tier] > max_rank:
            return "tier_above_rule"
        if d.escalation_reason and TIER_RANK[ep.tier] < max_rank:
            # An escalation exists because the lower tier was not good enough.
            return "below_escalation_tier"
        if d.quality_floor == "high" and ep.tier == "T0":
            return "below_quality_floor"
        if ep.billing == "byo":
            if not policy.billing.byo_allowed():
                return "byo_disabled"
            if ep.credential_provider not in byo_providers:
                return "no_byo_credential"
        if ep.billing == "proxy" and not policy.billing.proxy_allowed():
            return "proxy_not_enabled"
        return None

    @staticmethod
    def _budget_filter(
        policy: ModelPolicy, cost: float, spent_matter: float, spent_month: float
    ) -> str | None:
        b = policy.budgets
        if b.per_matter_usd is not None and spent_matter + cost > b.per_matter_usd:
            return "budget_matter"
        if b.per_month_usd is not None and spent_month + cost > b.per_month_usd:
            return "budget_month"
        return None
