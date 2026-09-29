from __future__ import annotations

from travo_router.client import RoutingRecord
from travo_router.policy import MatterContext, ModelPolicy
from travo_router.registry import Endpoint, EndpointRegistry


def ep(id_: str, provider: str, tier: str = "T1", billing: str = "travo", **kw) -> Endpoint:
    return Endpoint(
        id=id_,
        provider=provider,
        model=f"{id_}-m",
        tier=tier,
        billing=billing,
        base_url="https://example.invalid/v1",
        adapter=kw.pop("adapter", provider),
        capabilities=kw.pop("capabilities", ["json_output"]),
        **kw,
    )


def catalogue() -> EndpointRegistry:
    return EndpointRegistry(
        [
            ep("rules", "travo", "T0", regions=["*"], adapter="rules"),
            ep(
                "ow-t1",
                "travo",
                "T1",
                via="fireworks",
                adapter="fw",
                regions=["US"],
                price_in_per_mtok=1,
                price_out_per_mtok=1,
            ),
            ep(
                "ow-t1-sg",
                "travo",
                "T1",
                via="baseten",
                adapter="bt",
                regions=["SG"],
                price_in_per_mtok=2,
                price_out_per_mtok=2,
            ),
            ep(
                "openai",
                "openai",
                "T2",
                billing="byo",
                regions=["US"],
                price_in_per_mtok=2,
                price_out_per_mtok=8,
            ),
            ep(
                "anthropic",
                "anthropic",
                "T2",
                billing="byo",
                regions=["US"],
                price_in_per_mtok=3,
                price_out_per_mtok=15,
            ),
            ep(
                "or-anthropic",
                "anthropic",
                "T2",
                billing="proxy",
                via="openrouter",
                adapter="openrouter",
                price_in_per_mtok=3,
                price_out_per_mtok=15,
            ),
        ]
    )


class Ctx:
    """In-memory RouterContext."""

    def __init__(
        self,
        policy: ModelPolicy | None = None,
        matter: MatterContext | None = None,
        byo: set[str] | None = None,
        spend: tuple[float, float] = (0.0, 0.0),
    ):
        self._policy = policy or ModelPolicy()
        self._matter = matter
        self._byo = byo if byo is not None else {"openai", "anthropic"}
        self._spend = spend
        self.records: list[RoutingRecord] = []

    def policy(self) -> ModelPolicy:
        return self._policy

    def matter(self, matter_id):
        return self._matter

    def byo_providers(self) -> set[str]:
        return self._byo

    def api_key(self, provider, billing, api_key_env):
        return f"key-{provider}"

    def spend(self, matter_id):
        return self._spend

    def record(self, record: RoutingRecord):
        self.records.append(record)
        return str(len(self.records))
