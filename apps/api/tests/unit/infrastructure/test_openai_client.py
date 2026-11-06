"""P07 — adapter OpenAI qua HTTP giả lập: 429/5xx/timeout retry có giới hạn, 4xx không retry,
parse embedding/completion/stream, kiểm tra số chiều."""

import json

import httpx
import pytest

from quickassist.infrastructure.config import Settings
from quickassist.infrastructure.openai import openai_client as mod
from quickassist.infrastructure.openai.base import AIProviderError, ChatMessage
from quickassist.infrastructure.openai.openai_client import OpenAIClient

DIM = 8


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):  # type: ignore[no-untyped-def]
    async def fast(_: float) -> None:
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", fast)


def client(handler, retries: int = 2) -> OpenAIClient:  # type: ignore[no-untyped-def]
    s = Settings(openai_api_key="sk-test", embedding_dim=DIM, ai_max_retries=retries)
    return OpenAIClient(s, transport=httpx.MockTransport(handler))


def emb_response(n: int, dim: int = DIM) -> httpx.Response:
    data = [{"index": i, "embedding": [float(i)] * dim} for i in reversed(range(n))]
    return httpx.Response(200, json={"data": data, "usage": {"prompt_tokens": 7}, "model": "m"})


async def test_embed_sends_model_dims_auth_and_orders_by_index() -> None:
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return emb_response(3)

    r = await client(h).embed(["a", "b", "c"])
    assert [v[0] for v in r.vectors] == [0.0, 1.0, 2.0]
    assert r.usage.prompt_tokens == 7 and seen["auth"] == "Bearer sk-test"
    assert seen["body"]["dimensions"] == DIM and seen["body"]["input"] == ["a", "b", "c"]


async def test_embed_empty_input_makes_no_call() -> None:
    def h(_: httpx.Request) -> httpx.Response:
        raise AssertionError("không được gọi mạng")

    assert (await client(h).embed([])).vectors == []


async def test_wrong_dimension_is_permanent_error() -> None:
    with pytest.raises(AIProviderError) as e:
        await client(lambda r: emb_response(1, dim=DIM + 1)).embed(["a"])
    assert not e.value.retryable


@pytest.mark.parametrize("status", [429, 500, 502, 503])
async def test_retryable_status_is_retried_then_succeeds(status: int) -> None:
    calls = []

    def h(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status) if len(calls) < 3 else emb_response(1)

    assert len((await client(h, retries=2).embed(["a"])).vectors) == 1
    assert len(calls) == 3


async def test_retry_budget_is_bounded() -> None:
    calls = []

    def h(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(AIProviderError) as e:
        await client(h, retries=2).embed(["a"])
    assert e.value.retryable and len(calls) == 3  # 1 + 2 lần thử lại


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_client_errors_are_not_retried(status: int) -> None:
    calls = []

    def h(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status, json={"error": {"message": "x"}})

    with pytest.raises(AIProviderError) as e:
        await client(h).embed(["a"])
    assert not e.value.retryable and len(calls) == 1


async def test_timeout_and_network_errors_are_retryable() -> None:
    def h(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(AIProviderError) as e:
        await client(h, retries=1).embed(["a"])
    assert e.value.retryable and "ReadTimeout" in str(e.value)


async def test_complete_parses_text_and_usage() -> None:
    def h(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["max_tokens"] == 50 and body["messages"][0]["role"] == "system"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "tóm tắt"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3}, "model": "m",
        })

    r = await client(h).complete([ChatMessage("system", "s"), ChatMessage("user", "u")], max_tokens=50)
    assert r.text == "tóm tắt" and r.usage.total == 13


async def test_stream_yields_deltas_then_usage_and_skips_garbage() -> None:
    lines = [
        'data: {"choices":[{"delta":{"content":"Xin "}}]}',
        "data: {not json",
        'data: {"choices":[{"delta":{"content":"chào"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
        "data: [DONE]",
    ]
    body = ("\n\n".join(lines) + "\n\n").encode()
    c = client(lambda r: httpx.Response(200, content=body, headers={"content-type": "text/event-stream"}))
    chunks = [ch async for ch in c.stream([ChatMessage("user", "hi")], max_tokens=10)]
    assert "".join(ch.delta for ch in chunks) == "Xin chào"
    assert chunks[-1].usage is not None and chunks[-1].usage.total == 7


async def test_stream_http_error_raises() -> None:
    c = client(lambda r: httpx.Response(429))
    with pytest.raises(AIProviderError) as e:
        async for _ in c.stream([ChatMessage("user", "hi")], max_tokens=10):
            pass
    assert e.value.retryable


def test_provider_switch_by_config(monkeypatch) -> None:
    from quickassist.infrastructure import openai as pkg
    from quickassist.infrastructure.config import get_settings

    pkg.get_ai_provider.cache_clear()
    monkeypatch.setattr(get_settings(), "ai_provider", "openai")
    assert pkg.get_ai_provider().name == "openai"
    pkg.get_ai_provider.cache_clear()
    monkeypatch.setattr(get_settings(), "ai_provider", "mock")
    assert pkg.get_ai_provider().name == "mock"
    pkg.get_ai_provider.cache_clear()
