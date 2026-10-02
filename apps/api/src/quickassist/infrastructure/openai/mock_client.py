"""Infrastructure Layer — mock AI client: deterministic, không gọi mạng, không tốn quota.

Dùng cho: unit/integration test, CI, demo offline, dev khi chưa có API key.
Embedding = vector hash theo từ (bag-of-words) → các câu chung từ khoá sẽ gần nhau,
đủ để test luồng tìm kiếm end-to-end.
"""

import hashlib
import math
import re
from collections.abc import AsyncIterator, Sequence

from quickassist.infrastructure.openai.base import (
    ChatMessage,
    CompletionResult,
    EmbeddingResult,
    StreamChunk,
    Usage,
    estimate_tokens,
)

_WORD = re.compile(r"\w+", re.UNICODE)


class MockAIClient:
    name = "mock"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for w in _WORD.findall(text.lower()):
            h = int.from_bytes(hashlib.md5(w.encode()).digest()[:4], "little")
            v[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        tokens = sum(estimate_tokens(t) for t in texts)
        return EmbeddingResult([self._vector(t) for t in texts], Usage(tokens, 0), "mock-embed")

    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> CompletionResult:
        last = messages[-1].content if messages else ""
        text = "[mock] " + " ".join(last.split()[:40])
        prompt = sum(estimate_tokens(m.content) for m in messages)
        return CompletionResult(text, Usage(prompt, estimate_tokens(text)), "mock-chat")

    async def stream(
        self, messages: Sequence[ChatMessage], *, max_tokens: int
    ) -> AsyncIterator[StreamChunk]:
        result = await self.complete(messages, max_tokens=max_tokens)
        for word in result.text.split(" "):
            yield StreamChunk(delta=word + " ")
        yield StreamChunk(usage=result.usage)
