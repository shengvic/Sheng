"""Contract: a provider denied by policy or matter conflict is never called (docs/03 §8)."""

import typing

import httpx
import pytest
from travo_router import ModelPolicy, Router, TaskDescriptor
from travo_router.client import NoEligibleModel
from travo_router.descriptor import TaskType
from travo_router.policy import MatterContext
from travo_router.providers import FakeProvider, Message, OpenAICompatibleProvider

from tests.router_helpers import Ctx, catalogue

ALL_TASKS = list(typing.get_args(TaskType))


def adapters(**overrides):
    names = ["rules", "fw", "bt", "openai", "anthropic", "openrouter"]
    fakes = {n: FakeProvider('{"ok": true}') for n in names}
    fakes.update(overrides)
    return fakes


@pytest.mark.parametrize("task", ALL_TASKS)
@pytest.mark.parametrize("escalate", [None, "low_confidence"])
def test_conflicted_vendor_never_called(task, escalate):
    fakes = adapters(
        fw=FakeProvider(fail=True),
        bt=FakeProvider(fail=True),
        rules=FakeProvider(fail=True),
        openai=FakeProvider(fail=True),
    )
    router = Router(catalogue(), fakes)
    policy = ModelPolicy.model_validate({"billing": {"mode": "mixed"}})
    ctx = Ctx(policy=policy, matter=MatterContext(deny_providers=["anthropic"]))
    desc = TaskDescriptor(task_type=task, tenant_id="t", matter_id="m", escalation_reason=escalate)
    with pytest.raises(NoEligibleModel):
        router.complete(desc, [Message(role="user", content="{}")], ctx)
    assert fakes["anthropic"].calls == []
    assert fakes["openrouter"].calls == []
    assert ctx.records[-1].outcome in {"all_failed", "no_candidate"}


def test_fallback_to_next_candidate_and_record():
    fakes = adapters(fw=FakeProvider(fail=True))
    router = Router(catalogue(), fakes)
    ctx = Ctx()
    res = router.complete(
        TaskDescriptor(task_type="clause_extraction", tenant_id="t", matter_id="m"),
        [Message(role="user", content="{}")],
        ctx,
    )
    rec = res.record
    assert rec.outcome == "ok" and rec.chosen_endpoint == "ow-t1-sg"
    assert [(a.endpoint_id, a.ok) for a in rec.attempts] == [("ow-t1", False), ("ow-t1-sg", True)]
    assert ctx.records == [rec]


def test_budget_exceeded_outcome():
    router = Router(catalogue(), adapters())
    policy = ModelPolicy.model_validate({"budgets": {"per_month_usd": 1}})
    ctx = Ctx(policy=policy, spend=(0, 5))
    with pytest.raises(NoEligibleModel) as exc:
        router.complete(
            TaskDescriptor(
                task_type="memo", tenant_id="t", est_input_tokens=1000, quality_floor="high"
            ),
            [Message(role="user", content="{}")],
            ctx,
        )
    assert exc.value.record.outcome == "budget_exceeded"


def test_openai_compatible_adapter_request_shape_and_error_hygiene():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"a":1}'}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            },
        )

    prov = OpenAICompatibleProvider(httpx.Client(transport=httpx.MockTransport(handler)))
    ep = catalogue().get("openai")
    desc = TaskDescriptor(task_type="memo", tenant_id="t", requires=["json_output"])
    out = prov.complete(ep, desc, [Message(role="user", content="hi")], "sk-live-xyz")
    assert out.text == '{"a":1}' and out.tokens_in == 7
    assert seen["url"].endswith("/chat/completions")
    assert seen["auth"] == "Bearer sk-live-xyz"
    assert '"response_format"' in seen["body"]

    def boom(request):
        return httpx.Response(500, text="sk-live-xyz leaked?")

    prov = OpenAICompatibleProvider(httpx.Client(transport=httpx.MockTransport(boom)))
    with pytest.raises(Exception) as exc:
        prov.complete(ep, desc, [Message(role="user", content="hi")], "sk-live-xyz")
    assert "sk-live-xyz" not in str(exc.value)


def test_vendor_sdks_only_imported_in_router():
    """ADR-002 guard: no vendor SDK imports outside services/router."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "services"
    pat = re.compile(
        r"^\s*(import|from)\s+(openai|anthropic|google\.genai|mistralai|cohere)\b", re.M
    )
    offenders = [
        str(p)
        for p in root.rglob("*.py")
        if "router" not in p.parts[len(root.parts)] and pat.search(p.read_text())
    ]
    assert offenders == []
