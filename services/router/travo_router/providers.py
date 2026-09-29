"""Provider adapters. Only this package may talk to model vendors (ADR-002)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from travo_router.descriptor import TaskDescriptor
from travo_router.registry import Endpoint


class Message(BaseModel):
    role: str
    content: str


class Completion(BaseModel):
    text: str
    tokens_in: int = 0
    tokens_out: int = 0


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    def complete(
        self,
        endpoint: Endpoint,
        descriptor: TaskDescriptor,
        messages: list[Message],
        api_key: str | None,
    ) -> Completion: ...


class OpenAICompatibleProvider:
    """Any OpenAI-compatible chat/completions endpoint (Fireworks, Baseten, OpenRouter,
    vLLM, LiteLLM, and most frontier vendors' compatibility layers)."""

    def __init__(self, client: httpx.Client | None = None, timeout: float = 120.0):
        self._client = client or httpx.Client(timeout=timeout)

    def complete(
        self,
        endpoint: Endpoint,
        descriptor: TaskDescriptor,
        messages: list[Message],
        api_key: str | None,
    ) -> Completion:
        if not endpoint.base_url:
            raise ProviderError(f"endpoint {endpoint.id} has no base_url")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        body: dict[str, Any] = {
            "model": endpoint.model,
            "messages": [m.model_dump() for m in messages],
            "temperature": 0,
        }
        if "json_output" in descriptor.requires:
            body["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.post(
                endpoint.base_url.rstrip("/") + "/chat/completions", json=body, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Never include request bodies or keys in errors.
            raise ProviderError(f"{endpoint.id}: {type(exc).__name__}") from None
        usage = data.get("usage") or {}
        return Completion(
            text=data["choices"][0]["message"]["content"] or "",
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
        )


Responder = Callable[[TaskDescriptor, list[Message]], str]


class FakeProvider:
    """Deterministic provider for tests and offline development. Records every call."""

    def __init__(self, responder: Responder | str = "{}", fail: bool = False):
        self._responder = responder
        self.fail = fail
        self.calls: list[tuple[str, TaskDescriptor]] = []

    def complete(
        self,
        endpoint: Endpoint,
        descriptor: TaskDescriptor,
        messages: list[Message],
        api_key: str | None,
    ) -> Completion:
        self.calls.append((endpoint.id, descriptor))
        if self.fail:
            raise ProviderError(f"{endpoint.id}: simulated failure")
        text = (
            self._responder(descriptor, messages) if callable(self._responder) else self._responder
        )
        return Completion(
            text=text,
            tokens_in=sum(len(m.content) for m in messages) // 4,
            tokens_out=len(text) // 4,
        )


def json_payload(messages: list[Message]) -> Any:
    """Helper for rule-based providers: the last user message carries a JSON payload."""
    for m in reversed(messages):
        if m.role == "user":
            return json.loads(m.content)
    raise ProviderError("no user message")
