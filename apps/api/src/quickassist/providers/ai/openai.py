"""Adapter OpenAI qua HTTP (httpx) — không phụ thuộc SDK để dễ trỏ sang
endpoint tương thích OpenAI (vLLM, llama.cpp server, Dify OpenAI-compatible...)
bằng cách đổi OPENAI_BASE_URL.

Chính sách lỗi: timeout + retry có giới hạn, exponential backoff + jitter cho
429/5xx (SDS §10). Lỗi 4xx khác → không retry.
"""

import asyncio
import json
import random
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from quickassist.core.config import Settings
from quickassist.providers.ai.base import (
    AIProviderError,
    ChatMessage,
    CompletionResult,
    EmbeddingResult,
    StreamChunk,
    Usage,
)

_RETRYABLE = {408, 409, 429, 500, 502, 503, 504}


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openai_base_url,
            timeout=settings.ai_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}"},
        )

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(self._s.ai_max_retries + 1):
            try:
                r = await self._client.post(path, json=body)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = AIProviderError(f"network: {type(e).__name__}", retryable=True)
            else:
                if r.status_code < 400:
                    return r.json()
                last = AIProviderError(f"http {r.status_code}", retryable=r.status_code in _RETRYABLE)
                if not last.retryable:
                    raise last
            if attempt < self._s.ai_max_retries:
                await asyncio.sleep((2**attempt) * 0.5 + random.uniform(0, 0.3))
        assert last is not None
        raise last

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        data = await self._post(
            "/embeddings",
            {"model": self._s.embedding_model, "input": list(texts),
             "dimensions": self._s.embedding_dim},
        )
        vectors = [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]
        u = data.get("usage", {})
        return EmbeddingResult(vectors, Usage(u.get("prompt_tokens", 0), 0), data.get("model", ""))

    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> CompletionResult:
        data = await self._post(
            "/chat/completions",
            {"model": self._s.chat_model, "max_tokens": max_tokens,
             "messages": [{"role": m.role, "content": m.content} for m in messages]},
        )
        u = data.get("usage", {})
        return CompletionResult(
            data["choices"][0]["message"]["content"] or "",
            Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0)),
            data.get("model", ""),
        )

    async def stream(
        self, messages: Sequence[ChatMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamChunk]:
        body = {
            "model": self._s.chat_model, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        async with self._client.stream("POST", "/chat/completions", json=body) as r:
            if r.status_code >= 400:
                raise AIProviderError(f"http {r.status_code}", retryable=r.status_code in _RETRYABLE)
            async for line in r.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                evt = json.loads(line[6:])
                if evt.get("usage"):
                    u = evt["usage"]
                    yield StreamChunk(usage=Usage(u.get("prompt_tokens", 0),
                                                  u.get("completion_tokens", 0)))
                for ch in evt.get("choices", []):
                    delta = (ch.get("delta") or {}).get("content")
                    if delta:
                        yield StreamChunk(delta=delta)

    async def aclose(self) -> None:
        await self._client.aclose()
