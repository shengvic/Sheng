"""Wires travo_router to the database: policy, matter constraints, keys, spend, decision log."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from travo_agents.rules_model import RulesProvider
from travo_router import EndpointRegistry, ModelPolicy, Router
from travo_router.client import RoutingRecord
from travo_router.policy import MatterContext
from travo_router.providers import OpenAICompatibleProvider, Provider

from travo_api.config import get_settings
from travo_api.keys import load_credential
from travo_api.models import Matter, ModelPolicyRow, ProviderCredential, RoutingDecision


def default_policy_yaml() -> str:
    return get_settings().default_policy_file.read_text()


def load_registry() -> EndpointRegistry:
    registry = EndpointRegistry.from_yaml(get_settings().endpoints_file)
    for ep in registry.all():
        # Travo-billed endpoints need a Travo-owned key present in the environment.
        if ep.api_key_env and not os.environ.get(ep.api_key_env):
            ep.enabled = False
    return registry


def default_adapters() -> dict[str, Provider]:
    return {"openai_compatible": OpenAICompatibleProvider(), "travo_rules": RulesProvider()}


@lru_cache
def get_router() -> Router:
    return Router(load_registry(), default_adapters())


class DbRouterContext:
    """RouterContext backed by the tenant-scoped session (RLS applies to every query)."""

    def __init__(self, session: Session, tenant_id: str, document_id: uuid.UUID | None = None):
        self.session = session
        self.tenant_id = tenant_id
        self.document_id = document_id
        self.decision_ids: list[uuid.UUID] = []

    def policy(self) -> ModelPolicy:
        row = self.session.scalar(select(ModelPolicyRow).where(ModelPolicyRow.active.is_(True)))
        return ModelPolicy.from_yaml(row.yaml if row else default_policy_yaml())

    def matter(self, matter_id: str | None) -> MatterContext | None:
        if not matter_id:
            return None
        m = self.session.get(Matter, uuid.UUID(matter_id))
        if m is None:
            return None
        return MatterContext(
            deny_providers=list(m.deny_providers or []),
            allow_providers=list(m.allow_providers) if m.allow_providers is not None else None,
            residency=m.residency,
        )

    def byo_providers(self) -> set[str]:
        return set(
            self.session.scalars(
                select(ProviderCredential.provider).where(ProviderCredential.status == "active")
            )
        )

    def api_key(self, provider: str, billing: str, api_key_env: str | None) -> str | None:
        if billing == "byo":
            return load_credential(self.session, self.tenant_id, provider)
        return os.environ.get(api_key_env) if api_key_env else None

    def spend(self, matter_id: str | None) -> tuple[float, float]:
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month = self.session.scalar(
            select(func.coalesce(func.sum(RoutingDecision.cost_usd), 0)).where(
                RoutingDecision.created_at >= month_start
            )
        )
        matter_total: Decimal | int = 0
        if matter_id:
            matter_total = (
                self.session.scalar(
                    select(func.coalesce(func.sum(RoutingDecision.cost_usd), 0)).where(
                        RoutingDecision.matter_id == uuid.UUID(matter_id)
                    )
                )
                or 0
            )
        return float(matter_total), float(month or 0)

    def record(self, record: RoutingRecord) -> str | None:
        d = record.descriptor
        row = RoutingDecision(
            tenant_id=uuid.UUID(self.tenant_id),
            matter_id=uuid.UUID(d.matter_id) if d.matter_id else None,
            document_id=self.document_id,
            task_type=d.task_type,
            descriptor=d.model_dump(mode="json"),
            candidates=[c.model_dump(mode="json") for c in record.plan.candidates],
            filtered=[f.model_dump(mode="json") for f in record.plan.filtered],
            attempts=[a.model_dump(mode="json") for a in record.attempts],
            chosen_endpoint=record.chosen_endpoint,
            chosen_tier=record.chosen_tier,
            outcome=record.outcome,
            tokens_in=record.tokens_in,
            tokens_out=record.tokens_out,
            cost_usd=Decimal(str(round(record.cost_usd, 6))),
            latency_ms=record.latency_ms,
        )
        self.session.add(row)
        self.session.flush()
        self.decision_ids.append(row.id)
        return str(row.id)
