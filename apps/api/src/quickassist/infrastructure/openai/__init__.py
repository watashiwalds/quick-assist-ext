"""Infrastructure Layer — "OpenAI API" (SDS Hình 1) sau một port chung (ADR-0004).

Business Layer chỉ dùng `AIProvider` (base.py) và `get_ai_provider()`; không import SDK.
AI_PROVIDER=mock → MockAIClient (test/CI/demo offline); =openai → OpenAIClient;
=gemini → GeminiClient (Gemma 4 + gemini-embedding-001).

ADR-0016 (BYOK per-user): `build_provider(UserProviderConfig)` tái dùng 2 adapter sẵn có qua
`Settings.model_copy` (không sửa adapter), bọc `CanonicalEmbeddingProvider` để chuẩn hoá vector
về 1536 chiều. `provider_cache` giữ LRU 64 theo (user_id ‖ config ‖ sha256(key)) — luôn có
user_id trong khoá nên không thể chia sẻ provider giữa 2 user. KHÔNG đóng provider theo request
(RAG trả StreamingResponse, vòng đời dài hơn handler) — đóng trong lifespan/worker qua close_all().
"""

import asyncio
import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr

from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.openai.base import AIProvider
from quickassist.infrastructure.openai.dimensions import CANONICAL_DIM, CanonicalEmbeddingProvider

_CACHE_MAX_SIZE = 64


@lru_cache
def get_ai_provider() -> AIProvider:
    s = get_settings()
    if s.ai_provider == "openai":
        from quickassist.infrastructure.openai.openai_client import OpenAIClient

        return OpenAIClient(s)
    if s.ai_provider == "gemini":
        from quickassist.infrastructure.openai.gemini_client import GeminiClient

        return GeminiClient(s)
    from quickassist.infrastructure.openai.mock_client import MockAIClient

    return MockAIClient(s.embedding_dim)


@dataclass(frozen=True)
class UserProviderConfig:
    """Cấu hình AI của MỘT user (đã giải mã key) — input của build_provider/cache."""

    user_id: str
    provider: Literal["openai", "gemini"]
    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str
    timeout_seconds: float | None


def build_provider(cfg: UserProviderConfig) -> AIProvider:
    """Provider cho user: model_copy Settings (không làm bẩn get_settings()) → adapter sẵn có.

    embedding_dim giữ 1536 = hợp đồng lưu trữ; strict_dim/`dimensions` tắt để adapter trả
    chiều native, CanonicalEmbeddingProvider lo chuẩn hoá/pad (ADR-0016 §4.5).
    """
    s = get_settings()
    update: dict[str, object] = {
        "ai_timeout_seconds": cfg.timeout_seconds or s.ai_timeout_seconds,
        "embedding_dim": CANONICAL_DIM,
        "ai_embedding_strict_dim": False,
        "ai_request_embedding_dimensions": False,
    }
    if cfg.provider == "openai":
        update.update(openai_base_url=cfg.base_url, openai_api_key=SecretStr(cfg.api_key),
                      chat_model=cfg.chat_model, embedding_model=cfg.embedding_model)
    else:
        update.update(gemini_base_url=cfg.base_url, gemini_api_key=SecretStr(cfg.api_key),
                      gemini_chat_model=cfg.chat_model, gemini_embedding_model=cfg.embedding_model)
    sp = s.model_copy(update=update)
    from quickassist.infrastructure.openai.gemini_client import GeminiClient
    from quickassist.infrastructure.openai.openai_client import OpenAIClient

    raw: AIProvider = OpenAIClient(sp) if cfg.provider == "openai" else GeminiClient(sp)
    return CanonicalEmbeddingProvider(raw)


def _cache_key(cfg: UserProviderConfig) -> str:
    key_hash = hashlib.sha256(cfg.api_key.encode()).hexdigest()
    raw = "|".join([cfg.user_id, cfg.provider, cfg.base_url, cfg.chat_model,
                    cfg.embedding_model, repr(cfg.timeout_seconds), key_hash])
    return hashlib.sha256(raw.encode()).hexdigest()


async def _aclose_quietly(provider: AIProvider) -> None:
    try:
        await provider.aclose()
    except Exception:  # noqa: BLE001 — lỗi khi đóng không được làm sập request/worker
        pass


class ProviderCache:
    """LRU bounded cho provider BYOK. Khoá chứa user_id + sha256(key) → cách ly tuyệt đối.

    Evict/invalidate KHÔNG close đồng bộ (caller đang giữ event loop) mà schedule task;
    khi không có loop (test sync), đẩy vào pending để close_all() xử lý sau.
    """

    def __init__(self, max_size: int = _CACHE_MAX_SIZE) -> None:
        self._max = max_size
        self._entries: OrderedDict[str, AIProvider] = OrderedDict()
        self._key_user: dict[str, str] = {}  # cache_key → user_id
        self._pending_close: list[AIProvider] = []

    def get_or_build(self, cfg: UserProviderConfig) -> AIProvider:
        key = _cache_key(cfg)
        hit = self._entries.get(key)
        if hit is not None:
            self._entries.move_to_end(key)
            return hit
        provider = build_provider(cfg)
        self._entries[key] = provider
        self._key_user[key] = cfg.user_id
        while len(self._entries) > self._max:
            old_key, old = self._entries.popitem(last=False)
            self._key_user.pop(old_key, None)
            self._schedule_close(old)
        return provider

    def invalidate_user(self, user_id: str) -> int:
        """Đóng provider của user (lưu/xoá cấu hình) — lần gọi kế tiếp dùng key mới ngay."""
        closed = 0
        for key in [k for k, u in self._key_user.items() if u == user_id]:
            self._key_user.pop(key, None)
            provider = self._entries.pop(key, None)
            if provider is not None:
                self._schedule_close(provider)
                closed += 1
        return closed

    def _schedule_close(self, provider: AIProvider) -> None:
        try:
            asyncio.get_running_loop().create_task(_aclose_quietly(provider))
        except RuntimeError:  # ngoài event loop — close_all() sẽ rủi hộ
            self._pending_close.append(provider)

    def __len__(self) -> int:
        return len(self._entries)

    async def close_all(self) -> None:
        """Đóng toàn bộ provider BYOK — gọi trong lifespan FastAPI và finally của worker."""
        entries, self._entries = list(self._entries.values()), OrderedDict()
        self._key_user.clear()
        pending, self._pending_close = self._pending_close, []
        for provider in [*entries, *pending]:
            await _aclose_quietly(provider)


provider_cache = ProviderCache()
