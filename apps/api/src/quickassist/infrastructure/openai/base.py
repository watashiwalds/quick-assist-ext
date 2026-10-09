"""Infrastructure Layer — port (interface) tới nhà cung cấp AI (ADR-0004).

Business Layer (semantic_search, summary, rag) CHỈ phụ thuộc vào các Protocol ở đây, không import
SDK OpenAI. Đổi OpenAI → Dify/llama.cpp/vLLM = viết thêm 1 adapter + đổi AI_PROVIDER.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    usage: Usage
    model: str


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class CompletionResult:
    text: str
    usage: Usage
    model: str


@dataclass(frozen=True)
class StreamChunk:
    delta: str = ""
    usage: Usage | None = None  # chỉ có ở chunk cuối


class AIProviderError(Exception):
    """Lỗi từ provider. retryable=True với timeout/429/5xx."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class EmbeddingProvider(Protocol):
    async def embed(self, texts: Sequence[str]) -> EmbeddingResult: ...


class ChatProvider(Protocol):
    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> CompletionResult: ...

    def stream(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> AsyncIterator[StreamChunk]: ...


class AIProvider(EmbeddingProvider, ChatProvider, Protocol):
    name: str


def estimate_tokens(text: str) -> int:
    """Ước lượng để RESERVE quota trước khi gọi AI (chốt bằng usage thật sau đó).

    Spike P03 (docs/ai/spike-openai.md) đo trên tiếng Việt: cl100k_base (text-embedding-3-small)
    ≈ 2.14 ký tự/token, o200k_base (gpt-4o-mini) ≈ 3.44 ký tự/token. Chia 2 → luôn ước lượng
    DƯ một chút (giữ chỗ đủ), phần thừa được trả lại khi commit.
    """
    return max(1, len(text) // 2 + 1)
