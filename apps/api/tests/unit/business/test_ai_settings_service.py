"""Test P1 — AISettingsService.provider_for: inherit → singleton toàn cục; BYOK → provider
per-user có cache; key hỏng → AI_KEY_UNREADABLE. Fake repository (DB thật ở test integration P3)."""

import uuid
from types import SimpleNamespace

import pytest

from quickassist.business.ai_settings import AISettingsService
from quickassist.business.common.exceptions import AppError
from quickassist.infrastructure import ai_keys
from quickassist.infrastructure.openai import get_ai_provider, provider_cache

UID = uuid.uuid5(uuid.NAMESPACE_DNS, "byok-test-user")
UID2 = uuid.uuid5(uuid.NAMESPACE_DNS, "byok-test-user-2")


def row_for(uid: uuid.UUID, **kw) -> SimpleNamespace:
    with_key = kw.pop("with_key", True)
    base = dict(mode="byok", provider="openai", base_url="http://localhost:11434/v1",
                api_key_enc=ai_keys.encrypt(uid, "sk-user-key") if with_key else None,
                chat_model="llama3.1", embedding_model="nomic-embed-text", timeout_seconds=None)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def rows(monkeypatch: pytest.MonkeyPatch) -> dict[uuid.UUID, SimpleNamespace]:
    """Repository giả: get(uid) tra bảng `rows` do test nạp."""
    table: dict[uuid.UUID, SimpleNamespace] = {}

    class FakeRepo:
        def __init__(self, _session: object) -> None: ...

        async def get(self, uid: uuid.UUID) -> SimpleNamespace | None:
            return table.get(uid)

    monkeypatch.setattr("quickassist.business.ai_settings.service.UserAISettingsRepository", FakeRepo)
    return table


async def test_no_row_returns_global_singleton(rows: dict) -> None:
    p = await AISettingsService(None).provider_for(UID)  # type: ignore[arg-type]
    assert p is get_ai_provider()
    assert p.name == "mock"  # môi trường test AI_PROVIDER=mock


async def test_inherit_row_returns_global_singleton(rows: dict) -> None:
    rows[UID] = SimpleNamespace(mode="inherit")  # row cũ giữ lại sau khi quay về inherit
    assert await AISettingsService(None).provider_for(UID) is get_ai_provider()  # type: ignore[arg-type]


async def test_byok_builds_and_caches_per_user(rows: dict) -> None:
    rows[UID] = row_for(UID)
    rows[UID2] = row_for(UID2)  # cùng cấu hình, khác user

    svc = AISettingsService(None)  # type: ignore[arg-type]
    p1 = await svc.provider_for(UID)
    assert p1.name == "openai"
    assert str(p1._inner._client.base_url).rstrip("/") == "http://localhost:11434/v1"
    assert p1._inner._client.headers["authorization"] == "Bearer sk-user-key"
    assert await svc.provider_for(UID) is p1  # cache hit
    assert await svc.provider_for(UID2) is not p1  # user khác → provider khác

    provider_cache.invalidate_user(str(UID))
    assert await svc.provider_for(UID) is not p1  # lưu/xoá cấu hình → key mới ngay


async def test_byok_without_key_and_with_timeout(rows: dict) -> None:
    from decimal import Decimal

    rows[UID] = row_for(UID, with_key=False, timeout_seconds=Decimal("180.00"))
    p = await AISettingsService(None).provider_for(UID)  # type: ignore[arg-type]
    assert p.name == "openai"  # model local không cần key → vẫn build được
    assert p._inner._client.timeout.read == 180.0
    provider_cache.invalidate_user(str(UID))


async def test_unreadable_key_raises_ai_key_unreadable(rows: dict) -> None:
    rows[UID] = row_for(UID, api_key_enc=b"garbage-not-a-blob")
    with pytest.raises(AppError) as ei:
        await AISettingsService(None).provider_for(UID)  # type: ignore[arg-type]
    assert ei.value.code == "AI_KEY_UNREADABLE"
    assert "sk-user-key" not in str(ei.value)  # không lộ plaintext
