"""Adapter Gemini (Gemma 4 + gemini-embedding-001) qua HTTP giả lập: header khoá, định dạng request,
bỏ phần "thought", tự bỏ thinkingConfig khi bị 400, retry 429/5xx, batch embedding, Vertex :predict."""

import json
import math

import httpx
import pytest

from quickassist.infrastructure.config import Settings
from quickassist.infrastructure.openai import gemini_client as mod
from quickassist.infrastructure.openai.base import AIProviderError, ChatMessage
from quickassist.infrastructure.openai.gemini_client import GeminiClient

DIM = 4
VERTEX = "https://aiplatform.googleapis.com/v1/publishers/google/models"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):  # type: ignore[no-untyped-def]
    async def fast(_: float) -> None:
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", fast)


def client(handler, **kw) -> GeminiClient:  # type: ignore[no-untyped-def]
    s = Settings(ai_provider="gemini", gemini_api_key="g-test", embedding_dim=DIM, ai_max_retries=2, **kw)
    return GeminiClient(s, transport=httpx.MockTransport(handler))


MSGS = [ChatMessage("system", "Bạn là trợ lý."), ChatMessage("user", "Tóm tắt: xin chào")]


def gen_ok(text: str = "Tóm tắt.", *, thought: bool = False) -> httpx.Response:
    parts = ([{"text": "đang nghĩ...", "thought": True}] if thought else []) + [{"text": text}]
    return httpx.Response(200, json={
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 5, "thoughtsTokenCount": 2},
        "modelVersion": "gemma-4-31b-it",
    })


async def test_complete_request_shape_and_parsing() -> None:
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["key"] = req.headers["x-goog-api-key"]
        seen["body"] = json.loads(req.content)
        return gen_ok(thought=True)

    r = await client(h).complete(MSGS, max_tokens=99)
    assert seen["url"].endswith("/v1beta/models/gemma-4-31b-it:generateContent")
    assert seen["key"] == "g-test" and "key=" not in seen["url"]  # khoá không nằm trong URL
    b = seen["body"]
    assert b["systemInstruction"] == {"parts": [{"text": "Bạn là trợ lý."}]}
    assert b["contents"] == [{"role": "user", "parts": [{"text": "Tóm tắt: xin chào"}]}]
    assert b["generationConfig"] == {"maxOutputTokens": 99, "thinkingConfig": {"thinkingLevel": "MINIMAL"}}
    assert r.text == "Tóm tắt."  # phần thought bị bỏ
    assert (r.usage.prompt_tokens, r.usage.completion_tokens) == (11, 7)  # thought tính vào quota


async def test_assistant_role_maps_to_model_and_merges_consecutive() -> None:
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return gen_ok()

    msgs = [ChatMessage("user", "a"), ChatMessage("user", "b"), ChatMessage("assistant", "c")]
    await client(h).complete(msgs, max_tokens=10)
    assert seen["body"]["contents"] == [
        {"role": "user", "parts": [{"text": "a"}, {"text": "b"}]},
        {"role": "model", "parts": [{"text": "c"}]},
    ]
    assert "systemInstruction" not in seen["body"]


async def test_thinking_config_dropped_after_400_and_remembered() -> None:
    bodies = []

    def h(req: httpx.Request) -> httpx.Response:
        b = json.loads(req.content)
        bodies.append(b)
        if "thinkingConfig" in b["generationConfig"]:
            return httpx.Response(400, json={"error": {"status": "INVALID_ARGUMENT"}})
        return gen_ok()

    c = client(h)
    assert (await c.complete(MSGS, max_tokens=10)).text == "Tóm tắt."
    await c.complete(MSGS, max_tokens=10)
    assert len(bodies) == 3 and "thinkingConfig" not in bodies[2]["generationConfig"]


async def test_empty_thinking_level_sends_no_thinking_config() -> None:
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return gen_ok()

    await client(h, gemini_thinking_level="").complete(MSGS, max_tokens=10)
    assert seen["body"]["generationConfig"] == {"maxOutputTokens": 10}


async def test_retry_on_429_then_success_and_no_retry_on_403() -> None:
    calls = {"n": 0}

    def h(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] < 3 else gen_ok()

    assert (await client(h).complete(MSGS, max_tokens=10)).text == "Tóm tắt."
    assert calls["n"] == 3

    with pytest.raises(AIProviderError) as e:
        await client(lambda r: httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}})).complete(
            MSGS, max_tokens=10)
    assert not e.value.retryable and "403 PERMISSION_DENIED" in str(e.value)


async def test_blocked_prompt_is_permanent_error() -> None:
    resp = httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(AIProviderError) as e:
        await client(lambda r: resp).complete(MSGS, max_tokens=10)
    assert not e.value.retryable


async def test_embed_batches_normalizes_and_sets_dimension() -> None:
    reqs = []

    def h(req: httpx.Request) -> httpx.Response:
        b = json.loads(req.content)
        reqs.append((str(req.url), b))
        embs = [{"values": [3.0, 4.0, 0.0, 0.0]} for _ in b["requests"]]
        return httpx.Response(200, json={"embeddings": embs})

    texts = [f"đoạn {i}" for i in range(150)]
    r = await client(h).embed(texts)
    assert len(reqs) == 2 and len(reqs[0][1]["requests"]) == 100 and len(reqs[1][1]["requests"]) == 50
    assert reqs[0][0].endswith("/gemini-embedding-001:batchEmbedContents")
    first = reqs[0][1]["requests"][0]
    assert first == {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": "đoạn 0"}]},
                     "outputDimensionality": DIM}
    assert len(r.vectors) == 150 and r.vectors[0] == [0.6, 0.8, 0.0, 0.0]
    assert math.isclose(sum(x * x for x in r.vectors[0]), 1.0)
    assert r.usage.prompt_tokens > 0


async def test_embed_wrong_dimension_is_permanent_error() -> None:
    resp = httpx.Response(200, json={"embeddings": [{"values": [1.0] * (DIM + 1)}]})
    with pytest.raises(AIProviderError) as e:
        await client(lambda r: resp).embed(["a"])
    assert not e.value.retryable


async def test_embed_empty_input_makes_no_call() -> None:
    def h(_: httpx.Request) -> httpx.Response:
        raise AssertionError("không được gọi mạng")

    assert (await client(h).embed([])).vectors == []


async def test_vertex_embed_uses_predict_one_per_request() -> None:
    urls = []

    def h(req: httpx.Request) -> httpx.Response:
        urls.append(str(req.url))
        b = json.loads(req.content)
        assert b["parameters"] == {"outputDimensionality": DIM} and len(b["instances"]) == 1
        return httpx.Response(200, json={"predictions": [
            {"embeddings": {"values": [1.0, 0.0, 0.0, 0.0], "statistics": {"token_count": 3}}}]})

    r = await client(h, gemini_base_url=VERTEX).embed(["a", "b"])
    assert len(urls) == 2 and urls[0].startswith(VERTEX) and urls[0].endswith(":predict")
    assert r.usage.prompt_tokens == 6


async def test_stream_yields_text_without_thoughts_and_final_usage() -> None:
    def evt(d: dict) -> str:
        return "data: " + json.dumps(d) + "\r\n\r\n"

    body = (
        evt({"candidates": [{"content": {"parts": [{"text": "nghĩ", "thought": True}]}}]})
        + evt({"candidates": [{"content": {"parts": [{"text": "Xin "}]}}],
               "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 1}})
        + "data: {hỏng\r\n\r\n"
        + evt({"candidates": [{"content": {"parts": [{"text": "chào"}]}}],
               "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2}})
    )
    seen = {}

    def h(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})

    chunks = [c async for c in client(h).stream(MSGS, max_tokens=10)]
    assert seen["url"].endswith(":streamGenerateContent?alt=sse")
    assert "".join(c.delta for c in chunks) == "Xin chào"
    assert chunks[-1].usage is not None and chunks[-1].usage.completion_tokens == 2


def test_factory_returns_gemini_client(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from quickassist.infrastructure import openai as factory

    monkeypatch.setattr(factory, "get_settings", lambda: Settings(ai_provider="gemini", gemini_api_key="k"))
    factory.get_ai_provider.cache_clear()
    try:
        assert factory.get_ai_provider().name == "gemini"
    finally:
        factory.get_ai_provider.cache_clear()


async def test_persistent_500_falls_back_to_system_in_user_turn_and_remembers() -> None:
    bodies = []

    def h(req: httpx.Request) -> httpx.Response:
        b = json.loads(req.content)
        bodies.append(b)
        if "systemInstruction" in b:  # model giả lập không nhận systemInstruction
            return httpx.Response(500, json={"error": {"status": "INTERNAL"}})
        return gen_ok()

    c = client(h)
    assert (await c.complete(MSGS, max_tokens=10)).text == "Tóm tắt."
    ok = bodies[-1]
    assert "thinkingConfig" not in ok["generationConfig"]
    parts = [{"text": "Bạn là trợ lý."}, {"text": "Tóm tắt: xin chào"}]
    assert ok["contents"] == [{"role": "user", "parts": parts}]
    n = len(bodies)
    await c.complete(MSGS, max_tokens=10)
    assert len(bodies) == n + 1  # lần sau dùng ngay biến thể đã chạy được


async def test_all_variants_fail_raises_last_error() -> None:
    with pytest.raises(AIProviderError) as e:
        await client(lambda r: httpx.Response(500, json={"error": {"status": "INTERNAL"}})).complete(
            MSGS, max_tokens=10)
    assert "500" in str(e.value)


async def test_stream_falls_back_when_model_rejects_params_before_any_text() -> None:
    bodies = []
    evt = {"candidates": [{"content": {"parts": [{"text": "chào"}]}}],
           "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1}}
    ok = "data: " + json.dumps(evt) + "\r\n\r\n"

    def h(req: httpx.Request) -> httpx.Response:
        b = json.loads(req.content)
        bodies.append(b)
        if "thinkingConfig" in b["generationConfig"]:
            return httpx.Response(500, json={"error": {"status": "INTERNAL"}})
        return httpx.Response(200, content=ok.encode(), headers={"content-type": "text/event-stream"})

    chunks = [c async for c in client(h).stream(MSGS, max_tokens=10)]
    assert "".join(c.delta for c in chunks) == "chào" and chunks[-1].usage is not None
    assert len(bodies) == 2 and "thinkingConfig" not in bodies[1]["generationConfig"]


async def test_stream_error_without_fallback_left_raises() -> None:
    with pytest.raises(AIProviderError) as e:
        denied = httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}})
        _ = [c async for c in client(lambda r: denied).stream(MSGS, max_tokens=10)]
    assert not e.value.retryable
