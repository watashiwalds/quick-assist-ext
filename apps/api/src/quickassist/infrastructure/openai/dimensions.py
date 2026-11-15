"""Chuẩn hoá chiều vector về cố định 1536 mà không đổi cosine (ADR-0016 §4.5).

Cột `note_chunks.embedding` cố định 1536 chiều (HNSW). Model BYOK có thể trả ít chiều hơn
(vd nomic-embed-text = 768): **zero-pad** giữ nguyên cosine vì cos([q,0],[v,0]) = cos(q,v)
— tử số (dot) và mẫu số (norm) không đổi, chỉ tốn thêm dung lượng. Model trả NHIỀU hơn
1536 chiều → **từ chối** (truncate sẽ làm mất chất lượng một cách âm thầm).
"""

from collections.abc import AsyncIterator, Sequence

from quickassist.infrastructure.openai.base import (
    AIProvider,
    AIProviderError,
    ChatMessage,
    CompletionResult,
    EmbeddingResult,
    StreamChunk,
)

# Hợp đồng lưu trữ — phải bằng data.models.note_chunk.EMBEDDING_DIM (unit test chốt bất biến;
# infrastructure không được import data.models theo luật phân tầng).
CANONICAL_DIM = 1536


def _canonical(v: list[float], max_dim: int = CANONICAL_DIM) -> list[float]:
    n = len(v)
    if n == max_dim:
        return v
    if n < max_dim:
        return v + [0.0] * (max_dim - n)  # zero-pad: dot và norm không đổi → cosine bất biến
    raise AIProviderError(
        f"Model embedding trả {n} chiều, vượt giới hạn {max_dim} chiều được lưu trữ. "
        "Hãy chọn model có chiều ≤ 1536 (vd text-embedding-3-small, nomic-embed-text).",
        retryable=False,
    )


class CanonicalEmbeddingProvider:
    """Bọc một AIProvider, chuẩn hoá mọi vector embed() về CANONICAL_DIM chiều.

    complete()/stream() đi thẳng vào adapter bên trong. Được dùng cho provider BYOK;
    provider toàn cục của server không cần (adapter đã kiểm tra đúng embedding_dim).
    """

    def __init__(self, inner: AIProvider, max_dim: int = CANONICAL_DIM) -> None:
        self._inner = inner
        self._max_dim = max_dim

    @property
    def name(self) -> str:
        return self._inner.name

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        r = await self._inner.embed(texts)
        return EmbeddingResult([_canonical(v, self._max_dim) for v in r.vectors], r.usage, r.model)

    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> CompletionResult:
        return await self._inner.complete(messages, max_tokens=max_tokens)

    def stream(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> AsyncIterator[StreamChunk]:
        return self._inner.stream(messages, max_tokens=max_tokens)

    async def aclose(self) -> None:
        await self._inner.aclose()
