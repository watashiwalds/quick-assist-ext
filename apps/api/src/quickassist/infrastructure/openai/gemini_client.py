"""Infrastructure Layer — adapter Google Gemini API (ADR-0004): chat bằng Gemma/Gemini, embedding
bằng gemini-embedding-001. Gọi REST thuần qua httpx (không phụ thuộc SDK), cùng port `AIProvider`
nên Business Layer không đổi gì.

Hỗ trợ 2 kiểu endpoint (chọn bằng GEMINI_BASE_URL):
  - Google AI Studio (mặc định): https://generativelanguage.googleapis.com/v1beta/models
      chat  → POST /{model}:generateContent | :streamGenerateContent?alt=sse
      embed → POST /{model}:batchEmbedContents (≤100 đoạn/lần)
  - Vertex AI express mode:      https://aiplatform.googleapis.com/v1/publishers/google/models
      chat  → giống trên
      embed → POST /{model}:predict (gemini-embedding-001 nhận 1 đoạn/lần)
Khoá gửi qua header `x-goog-api-key` (không đặt trong URL để không lọt vào log).

Gemma 4 có chế độ "thinking": mặc định tắt (GEMINI_THINKING_LEVEL=minimal) để tóm tắt nhanh, rẻ và
không bị suy nghĩ chiếm hết max_tokens. Nếu endpoint/model không nhận tham số này (HTTP 400) →
tự gọi lại không kèm tham số và ghi nhớ cho các lần sau. Phần "thought" luôn bị bỏ khỏi kết quả.

Chính sách lỗi giống OpenAIClient: timeout + retry có giới hạn, backoff + jitter cho 429/5xx.
"""

import asyncio
import json
import math
import random
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from quickassist.infrastructure.config import Settings
from quickassist.infrastructure.openai.base import (
    AIProviderError,
    ChatMessage,
    CompletionResult,
    EmbeddingResult,
    StreamChunk,
    Usage,
    estimate_tokens,
)

_RETRYABLE = {408, 409, 429, 500, 502, 503, 504}
_BATCH = 100


class GeminiClient:
    name = "gemini"

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._s = settings
        self._vertex = "aiplatform.googleapis.com" in settings.gemini_base_url
        self._thinking: str | None = settings.gemini_thinking_level.strip() or None
        self._client = httpx.AsyncClient(
            base_url=settings.gemini_base_url.rstrip("/"),
            timeout=settings.ai_timeout_seconds,
            headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()},
            transport=transport,
        )

    # ---------------------------------------------------------------- HTTP
    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        last: AIProviderError | None = None
        for attempt in range(self._s.ai_max_retries + 1):
            try:
                r = await self._client.post(path, json=body)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = AIProviderError(f"network: {type(e).__name__}", retryable=True)
            else:
                if r.status_code < 400:
                    return r.json()
                last = AIProviderError(_err(r), retryable=r.status_code in _RETRYABLE)
                if not last.retryable:
                    raise last
            if attempt < self._s.ai_max_retries:
                await asyncio.sleep((2**attempt) * 0.5 + random.uniform(0, 0.3))
        assert last is not None
        raise last

    # ----------------------------------------------------------- embedding
    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        model = self._s.gemini_embedding_model
        if not texts:
            return EmbeddingResult([], Usage(), model)
        dim = self._s.embedding_dim
        vectors: list[list[float]] = []
        tokens = 0
        if self._vertex:
            for t in texts:  # gemini-embedding-001 trên Vertex: 1 instance / request
                data = await self._post(
                    f"/{model}:predict",
                    {"instances": [{"content": t}], "parameters": {"outputDimensionality": dim}},
                )
                preds = data.get("predictions") or []
                if len(preds) != 1:
                    raise AIProviderError("embedding trả về sai số lượng", retryable=False)
                emb = preds[0].get("embeddings") or {}
                vectors.append(emb.get("values") or [])
                tokens += int((emb.get("statistics") or {}).get("token_count") or estimate_tokens(t))
        else:
            for i in range(0, len(texts), _BATCH):
                part = list(texts[i : i + _BATCH])
                data = await self._post(
                    f"/{model}:batchEmbedContents",
                    {"requests": [
                        {"model": f"models/{model}", "content": {"parts": [{"text": t}]},
                         "outputDimensionality": dim}
                        for t in part
                    ]},
                )
                got = [e.get("values") or [] for e in data.get("embeddings") or []]
                if len(got) != len(part):
                    raise AIProviderError("embedding trả về sai số lượng", retryable=False)
                vectors.extend(got)
                tokens += sum(estimate_tokens(t) for t in part)  # API không trả usage cho embedding
        if len(vectors) != len(texts) or any(len(v) != dim for v in vectors):
            raise AIProviderError("embedding trả về sai số lượng/số chiều", retryable=False)
        # Số chiều < 3072 (MRL) không được chuẩn hoá sẵn → chuẩn hoá L2 cho cosine ổn định.
        return EmbeddingResult([_l2(v) for v in vectors], Usage(tokens, 0), model)

    # ---------------------------------------------------------------- chat
    def _body(self, messages: Sequence[ChatMessage], max_tokens: int, *, thinking: bool) -> dict[str, Any]:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        contents: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            role = "model" if m.role == "assistant" else "user"
            if contents and contents[-1]["role"] == role:  # API yêu cầu xen kẽ user/model
                contents[-1]["parts"].append({"text": m.content})
            else:
                contents.append({"role": role, "parts": [{"text": m.content}]})
        gen: dict[str, Any] = {"maxOutputTokens": max_tokens}
        if thinking and self._thinking:
            gen["thinkingConfig"] = {"thinkingLevel": self._thinking}
        body: dict[str, Any] = {"contents": contents, "generationConfig": gen}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    async def _generate(self, messages: Sequence[ChatMessage], max_tokens: int) -> dict[str, Any]:
        path = f"/{self._s.gemini_chat_model}:generateContent"
        try:
            return await self._post(path, self._body(messages, max_tokens, thinking=True))
        except AIProviderError as e:
            if self._thinking and "http 400" in str(e):
                self._thinking = None  # model/endpoint không nhận thinkingConfig → bỏ hẳn
                return await self._post(path, self._body(messages, max_tokens, thinking=False))
            raise

    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> CompletionResult:
        data = await self._generate(messages, max_tokens)
        _raise_if_blocked(data)
        cands = data.get("candidates") or []
        text = _text(cands[0]) if cands else ""
        if not cands:
            raise AIProviderError("Gemini không trả kết quả", retryable=True)
        return CompletionResult(text, _usage(data), data.get("modelVersion") or self._s.gemini_chat_model)

    async def stream(
        self, messages: Sequence[ChatMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamChunk]:
        path = f"/{self._s.gemini_chat_model}:streamGenerateContent"
        body = self._body(messages, max_tokens, thinking=True)
        last_usage: Usage | None = None
        async with self._client.stream("POST", path, params={"alt": "sse"}, json=body) as r:
            if r.status_code >= 400:
                await r.aread()
                raise AIProviderError(_err(r), retryable=r.status_code in _RETRYABLE)
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if evt.get("usageMetadata"):
                    last_usage = _usage(evt)  # cộng dồn — giữ bản cuối
                for c in evt.get("candidates") or []:
                    delta = _text(c)
                    if delta:
                        yield StreamChunk(delta=delta)
        if last_usage is not None:
            yield StreamChunk(usage=last_usage)

    async def aclose(self) -> None:
        await self._client.aclose()


# --------------------------------------------------------------- helpers
def _text(candidate: dict[str, Any]) -> str:
    parts = (candidate.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _usage(data: dict[str, Any]) -> Usage:
    u = data.get("usageMetadata") or {}
    return Usage(
        int(u.get("promptTokenCount") or 0),
        int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0),
    )


def _raise_if_blocked(data: dict[str, Any]) -> None:
    reason = (data.get("promptFeedback") or {}).get("blockReason")
    if reason:
        raise AIProviderError(f"bị chặn bởi bộ lọc an toàn: {reason}", retryable=False)


def _l2(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n > 0 else v


def _err(r: httpx.Response) -> str:
    """Mã HTTP + trạng thái lỗi của Google (VD 400 INVALID_ARGUMENT) — không kèm nội dung người dùng."""
    status = ""
    try:
        status = (r.json().get("error") or {}).get("status") or ""
    except (ValueError, AttributeError):
        pass
    return f"http {r.status_code}" + (f" {status}" if status else "")
