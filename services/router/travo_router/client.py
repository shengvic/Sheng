"""Router: policy → call → fallback → RoutingDecision record (docs/03)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel

from travo_router.descriptor import TaskDescriptor
from travo_router.policy import MatterContext, ModelPolicy, PolicyEngine, RoutingPlan
from travo_router.providers import Completion, Message, Provider, ProviderError
from travo_router.registry import EndpointRegistry


class Attempt(BaseModel):
    endpoint_id: str
    ok: bool
    error: str | None = None
    latency_ms: int = 0


class RoutingRecord(BaseModel):
    """Everything needed to persist a RoutingDecision row (docs/09)."""

    descriptor: TaskDescriptor
    plan: RoutingPlan
    attempts: list[Attempt]
    chosen_endpoint: str | None
    chosen_tier: str | None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    outcome: str  # ok | no_candidate | budget_exceeded | all_failed


class RouterResult(BaseModel):
    completion: Completion | None
    record: RoutingRecord


class NoEligibleModel(RuntimeError):
    def __init__(self, record: RoutingRecord):
        super().__init__(f"no eligible model for {record.descriptor.task_type}: {record.outcome}")
        self.record = record


class RouterContext(Protocol):
    """Per-tenant state the router needs; implemented by the API layer."""

    def policy(self) -> ModelPolicy: ...
    def matter(self, matter_id: str | None) -> MatterContext | None: ...
    def byo_providers(self) -> set[str]: ...
    def api_key(self, provider: str, billing: str, api_key_env: str | None) -> str | None: ...
    def spend(self, matter_id: str | None) -> tuple[float, float]: ...
    def record(self, record: RoutingRecord) -> str | None: ...


class Router:
    def __init__(
        self,
        registry: EndpointRegistry,
        adapters: dict[str, Provider],
        engine: PolicyEngine | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.registry = registry
        self.adapters = adapters
        self.engine = engine or PolicyEngine()
        self._clock = clock

    def plan(self, descriptor: TaskDescriptor, ctx: RouterContext) -> RoutingPlan:
        spent_matter, spent_month = ctx.spend(descriptor.matter_id)
        return self.engine.plan(
            descriptor,
            ctx.policy(),
            self.registry.all(),
            matter=ctx.matter(descriptor.matter_id),
            byo_providers=ctx.byo_providers(),
            spent_matter_usd=spent_matter,
            spent_month_usd=spent_month,
        )

    def complete(
        self, descriptor: TaskDescriptor, messages: list[Message], ctx: RouterContext
    ) -> RouterResult:
        start = self._clock()
        plan = self.plan(descriptor, ctx)
        attempts: list[Attempt] = []
        for cand in plan.candidates:
            ep = self.registry.get(cand.endpoint_id)
            provider = self.adapters.get(ep.adapter)
            if provider is None:
                attempts.append(Attempt(endpoint_id=ep.id, ok=False, error="no_adapter"))
                continue
            t0 = self._clock()
            try:
                key = ctx.api_key(ep.credential_provider, ep.billing, ep.api_key_env)
                completion = provider.complete(ep, descriptor, messages, key)
            except ProviderError as exc:
                attempts.append(
                    Attempt(
                        endpoint_id=ep.id,
                        ok=False,
                        error=str(exc),
                        latency_ms=int((self._clock() - t0) * 1000),
                    )
                )
                continue
            attempts.append(
                Attempt(endpoint_id=ep.id, ok=True, latency_ms=int((self._clock() - t0) * 1000))
            )
            record = RoutingRecord(
                descriptor=descriptor,
                plan=plan,
                attempts=attempts,
                chosen_endpoint=ep.id,
                chosen_tier=ep.tier,
                tokens_in=completion.tokens_in,
                tokens_out=completion.tokens_out,
                cost_usd=ep.estimate_cost(completion.tokens_in, completion.tokens_out),
                latency_ms=int((self._clock() - start) * 1000),
                outcome="ok",
            )
            ctx.record(record)
            return RouterResult(completion=completion, record=record)

        if plan.budget_exceeded:
            outcome = "budget_exceeded"
        elif not plan.candidates:
            outcome = "no_candidate"
        else:
            outcome = "all_failed"
        record = RoutingRecord(
            descriptor=descriptor,
            plan=plan,
            attempts=attempts,
            chosen_endpoint=None,
            chosen_tier=None,
            latency_ms=int((self._clock() - start) * 1000),
            outcome=outcome,
        )
        ctx.record(record)
        raise NoEligibleModel(record)
