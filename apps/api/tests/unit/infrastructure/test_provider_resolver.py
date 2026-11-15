"""Test P1 — resolver provider per-user + cache LRU (ADR-0016 §4.4).

Trọng tâm an toàn: provider KHÔNG BAO GIỜ chia sẻ giữa 2 user, kể cả cấu hình giống hệt;
model_copy không làm bến get_settings(); invalidate_user có tác dụng ngay.
"""

import asyncio

from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.openai import ProviderCache, UserProviderConfig, build_provider
from quickassist.infrastructure.openai.dimensions import CanonicalEmbeddingProvider
from quickassist.infrastructure.openai.openai_client import OpenAIClient


def cfg(user_id: str = "u1", **kw) -> UserProviderConfig:
    base = dict(user_id=user_id, provider="openai", base_url="http://localhost:11434/v1",
                api_key="sk-abc", chat_model="llama3.1", embedding_model="nomic-embed-text",
                timeout_seconds=None)
    base.update(kw)
    return UserProviderConfig(**base)  # type: ignore[arg-type]


def test_build_wraps_openai_adapter_with_overrides() -> None:
    p = build_provider(cfg(timeout_seconds=180))
    assert isinstance(p, CanonicalEmbeddingProvider)
    inner = p._inner
    assert isinstance(inner, OpenAIClient) and inner.name == "openai"
    assert str(inner._client.base_url).rstrip("/") == "http://localhost:11434/v1"
    assert inner._client.timeout.read == 180.0  # timeout user override
    assert inner._client.headers["authorization"] == "Bearer sk-abc"


def test_model_copy_does_not_pollute_global_settings() -> None:
    s0 = get_settings()
    before = (s0.openai_base_url, s0.embedding_dim, s0.ai_embedding_strict_dim,
              s0.ai_request_embedding_dimensions, s0.ai_timeout_seconds)
    build_provider(cfg(timeout_seconds=42))
    s1 = get_settings()
    assert (s1.openai_base_url, s1.embedding_dim, s1.ai_embedding_strict_dim,
            s1.ai_request_embedding_dimensions, s1.ai_timeout_seconds) == before


def test_cache_reuses_same_config_and_splits_users() -> None:
    cache = ProviderCache()
    a, b = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    p1, p1b = cache.get_or_build(cfg(a)), cache.get_or_build(cfg(a))
    assert p1 is p1b  # cùng user + cùng config → tái dùng
    p2 = cache.get_or_build(cfg(b))
    assert p2 is not p1  # user khác, config GIỐNG HỆT → provider khác (chống rò chéo)
    p3 = cache.get_or_build(cfg(a, api_key="sk-other"))
    assert p3 is not p1  # đổi key → provider mới


def test_invalidate_user_drops_only_that_user() -> None:
    cache = ProviderCache()
    a, b = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    pa, pb = cache.get_or_build(cfg(a)), cache.get_or_build(cfg(b))
    assert cache.invalidate_user(a) == 1
    assert cache.get_or_build(cfg(a)) is not pa  # user a → provider mới (key mới)
    assert cache.get_or_build(cfg(b)) is pb  # user b không bị ảnh hưởng
    assert cache.invalidate_user("không-tồn-tại") == 0


def test_lru_bounded_evicts_oldest() -> None:
    cache = ProviderCache(max_size=2)
    oldest = cache.get_or_build(cfg("u0"))
    cache.get_or_build(cfg("u1"))
    cache.get_or_build(cfg("u2"))
    assert len(cache) == 2
    assert cache.get_or_build(cfg("u0")) is not oldest  # u0 đã bị evict → build lại


async def test_close_all_closes_clients_and_empties_cache() -> None:
    cache = ProviderCache()
    p1, p2 = cache.get_or_build(cfg("u1")), cache.get_or_build(cfg("u2"))
    await cache.close_all()
    assert len(cache) == 0
    assert p1._inner._client.is_closed and p2._inner._client.is_closed


async def test_scheduled_close_runs_in_running_loop() -> None:
    cache = ProviderCache()
    p = cache.get_or_build(cfg("u1"))
    cache.invalidate_user("u1")  # có event loop → schedule task
    await asyncio.sleep(0)  # nhường task chạy
    assert p._inner._client.is_closed
    await cache.close_all()  # idempotent, không lỗi
