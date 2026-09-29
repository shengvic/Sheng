"""Endpoint catalogue: every model endpoint the router may call."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from travo_router.descriptor import Capability, Tier

Billing = Literal["travo", "byo", "proxy"]


class Endpoint(BaseModel):
    id: str
    # Model vendor (the lab whose weights run). Conflict and allow/deny policy apply here.
    provider: str
    model: str
    # Aggregator/host the call goes through (openrouter, fireworks, baseten); also policy-checked.
    via: str | None = None
    # Adapter used to talk to the endpoint (see Router.adapters).
    adapter: str = "openai_compatible"
    tier: Tier
    billing: Billing
    base_url: str | None = None
    # Regions where inference runs; "*" = self-hosted / local, usable for any residency.
    regions: list[str] = Field(default_factory=lambda: ["SG"])
    capabilities: list[Capability] = Field(default_factory=list)
    max_context: int = 32_000
    price_in_per_mtok: float = 0.0
    price_out_per_mtok: float = 0.0
    enabled: bool = True
    # Env var holding the Travo-owned API key (billing travo/proxy).
    api_key_env: str | None = None

    @property
    def parties(self) -> set[str]:
        """Every organisation that would see the data on this endpoint."""
        return {self.provider} | ({self.via} if self.via else set())

    @property
    def credential_provider(self) -> str:
        return self.via or self.provider

    def serves_region(self, region: str) -> bool:
        return "*" in self.regions or region in self.regions

    def estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.price_in_per_mtok + tokens_out * self.price_out_per_mtok) / 1e6


class EndpointRegistry:
    def __init__(self, endpoints: list[Endpoint]):
        ids = [e.id for e in endpoints]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate endpoint ids")
        self._endpoints = {e.id: e for e in endpoints}

    @classmethod
    def from_yaml(cls, path: str | Path) -> EndpointRegistry:
        data = yaml.safe_load(Path(path).read_text())
        return cls([Endpoint.model_validate(e) for e in data.get("endpoints", [])])

    def all(self) -> list[Endpoint]:
        return list(self._endpoints.values())

    def get(self, endpoint_id: str) -> Endpoint:
        return self._endpoints[endpoint_id]
