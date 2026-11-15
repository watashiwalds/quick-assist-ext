"""Test P1 — chuẩn hoá chiều vector 1536 (zero-pad / từ chối vượt) — ADR-0016 §4.5."""

import math
import random

import pytest

from quickassist.data.models.note_chunk import EMBEDDING_DIM
from quickassist.infrastructure.openai.base import (
    AIProviderError,
    ChatMessage,
    CompletionResult,
    EmbeddingResult,
    Usage,
)
from quickassist.infrastructure.openai.dimensions import CANONICAL_DIM, CanonicalEmbeddingProvider, _canonical


def test_canonical_dim_matches_storage_contract() -> None:
    """Bất biến: hằng số ở infrastructure phải bằng cột vector trong DB."""
    assert CANONICAL_DIM == EMBEDDING_DIM == 1536


def test_exact_dim_untouched() -> None:
    v = [0.1] * 1536
    assert _canonical(v) is v  # cùng object — không copy thừa


def test_small_dim_zero_padded() -> None:
    v = [0.5, -0.25, 1.0]
    out = _canonical(v, max_dim=6)
    assert out == [0.5, -0.25, 1.0, 0.0, 0.0, 0.0]
    assert len(out) == 6


def test_oversized_dim_rejected_non_retryable() -> None:
    with pytest.raises(AIProviderError) as ei:
        _canonical([0.0] * 3072)
    assert ei.value.retryable is False
    assert "3072" in str(ei.value)


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb)


def test_zero_pad_preserves_cosine_property() -> None:
    """cos([q,0],[v,0]) = cos(q,v) — property test với vector ngẫu nhiên nhiều lần."""
    rng = random.Random(2026)
    for _ in range(50):
        n = rng.randint(1, 64)
        q = [rng.uniform(-1, 1) for _ in range(n)]
        v = [rng.uniform(-1, 1) for _ in range(n)]
        target = rng.choice([128, 768, 1536])
        assert _cos(_canonical(q, target), _canonical(v, target)) == pytest.approx(_cos(q, v))


class _StubProvider:
    name = "stub"

    async def embed(self, texts):  # type: ignore[no-untyped-def]
        return EmbeddingResult([[0.0] * 768 for _ in texts], Usage(10, 0), "nomic-embed-text")

    async def complete(self, messages, *, max_tokens):  # type: ignore[no-untyped-def]
        return CompletionResult("ok", Usage(1, 1), "stub-chat")

    def stream(self, messages, *, max_tokens):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def aclose(self) -> None:
        self.closed = True


async def test_wrapper_pads_and_passes_through_metadata() -> None:
    stub = _StubProvider()
    wrapped = CanonicalEmbeddingProvider(stub)  # type: ignore[arg-type]
    assert wrapped.name == "stub"
    r = await wrapped.embed(["xin chào", "hai"])
    assert len(r.vectors) == 2
    assert all(len(v) == CANONICAL_DIM for v in r.vectors)
    assert r.usage == Usage(10, 0)
    assert r.model == "nomic-embed-text"


async def test_wrapper_passes_through_chat_and_close() -> None:
    stub = _StubProvider()
    wrapped = CanonicalEmbeddingProvider(stub)  # type: ignore[arg-type]
    msg = [ChatMessage(role="user", content="hi")]
    assert (await wrapped.complete(msg, max_tokens=10)).text == "ok"
    await wrapped.aclose()
    assert getattr(stub, "closed", False) is True
