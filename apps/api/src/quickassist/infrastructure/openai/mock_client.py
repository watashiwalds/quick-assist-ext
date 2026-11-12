"""Infrastructure Layer — mock AI client: deterministic, không gọi mạng, không tốn quota.

Dùng cho: unit/integration test, CI, demo offline, dev khi chưa có API key.
Embedding = vector hash theo từ (bag-of-words) → các câu chung từ khoá sẽ gần nhau,
đủ để test luồng tìm kiếm end-to-end.
"""

import hashlib
import json
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
# Prompt hỏi đáp RAG (business/rag/prompts.py): lấy nội dung các <note id="n" ...>…</note>
_NOTE = re.compile(r'<note id="(\d+)"[^>]*>\n?(.*?)\n?</note>', re.DOTALL)
# Prompt thẩm định AutoChunk (business/page_match/prompts.py): <query>…</query> + <block id="bNN">…</block>
_QUERY = re.compile(r"<query>(.*?)</query>", re.DOTALL)
_BLOCK = re.compile(r'<block id="(b\d+)">(.*?)</block>', re.DOTALL)


def _verdict_json(query: str, blocks: list[tuple[str, str]]) -> str:
    """Thẩm định giả lập: đoạn liên quan khi chứa ≥ một nửa số từ (≥2 ký tự) của truy vấn."""
    q = {w for w in _WORD.findall(query.lower()) if len(w) >= 2}
    need = max(1, (len(q) + 1) // 2)
    results = [{"id": bid, "relevant": len(q & set(_WORD.findall(text.lower()))) >= need}
               for bid, text in blocks]
    return json.dumps({"results": results}, ensure_ascii=False)


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
        notes = _NOTE.findall(last)
        blocks = _BLOCK.findall(last)
        query = _QUERY.search(last)
        if blocks and query:  # thẩm định AutoChunk → JSON verdict như LLM thật
            text = _verdict_json(query.group(1), blocks)
        elif notes:  # hỏi đáp RAG → câu trả lời giả lập có trích dẫn [n] như LLM thật
            text = "[mock] Theo ghi chú của bạn: " + " ".join(
                " ".join(body.split()[:25]) + f" [{i}]" for i, body in notes[:2])
        else:
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
