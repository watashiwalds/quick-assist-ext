"""Test P2 — test_connection (POST /me/ai-settings/test): đo dim native, pad flag, từ chối
>1536, lỗi chat có embedding kèm theo, client test luôn đóng, dùng key đã lưu khi api_key=None."""

import uuid

import pytest

from quickassist.business.ai_settings import AISettingsInput, AISettingsService
from quickassist.business.common.exceptions import AppError
from quickassist.infrastructure.openai.base import (
    AIProviderError,
    CompletionResult,
    EmbeddingResult,
    Usage,
)

UID = uuid.uuid5(uuid.NAMESPACE_DNS, "ai-settings-test")

CFG = dict(mode="byok", provider="openai", base_url="http://localhost:11434/v1",
           chat_model="llama3.1", embedding_model="nomic-embed-text")


class StubProbe:
    """Thay build_raw_provider — không mạng. Ghi nhận aclose để bảo đảm client được đóng."""

    name = "openai"

    def __init__(self, dim: int = 768, *, chat_fail: bool = False) -> None:
        self.dim, self.chat_fail, self.closed = dim, chat_fail, False

    async def embed(self, texts):  # type: ignore[no-untyped-def]
        return EmbeddingResult([[0.5] * self.dim for _ in texts], Usage(9, 0), "nomic-embed-text")

    async def complete(self, messages, *, max_tokens):  # type: ignore[no-untyped-def]
        if self.chat_fail:
            raise AIProviderError("http 401", retryable=False)
        return CompletionResult("Hà Nội", Usage(5, 2), "llama3.1")

    def stream(self, messages, *, max_tokens):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    holders: dict[str, StubProbe] = {}

    class FakeRepo:
        def __init__(self, _session: object) -> None: ...

        async def get(self, uid: uuid.UUID):  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr("quickassist.business.ai_settings.service.UserAISettingsRepository", FakeRepo)
    monkeypatch.setattr(
        "quickassist.business.ai_settings.service.build_raw_provider",
        lambda cfg, **kw: holders.setdefault("probe", StubProbe()))
    monkeypatch.setattr(
        "quickassist.business.ai_settings.service.UserAISettingsRepository", FakeRepo)
    return holders


async def test_ok_reports_native_dim_padded_and_closes(harness) -> None:
    svc = AISettingsService(None)  # type: ignore[arg-type]
    r = await svc.test_connection(UID, AISettingsInput(**CFG))  # 768 chiều → padded=True
    assert r.ok and r.stage is None
    assert r.embedding is not None
    assert r.embedding["model"] == "nomic-embed-text"
    assert r.embedding["dim"] == 768 and r.embedding["padded"] is True
    assert isinstance(r.embedding["latency_ms"], int) and r.embedding["latency_ms"] >= 0
    assert r.chat is not None and r.chat["model"] == "llama3.1" and r.chat["sample"] == "Hà Nội"
    assert harness["probe"].closed  # client test luôn được đóng


async def test_dim_over_1536_rejected(harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quickassist.business.ai_settings.service.build_raw_provider",
        lambda cfg, **kw: harness.setdefault("big", StubProbe(dim=3072)))
    svc = AISettingsService(None)  # type: ignore[arg-type]
    r = await svc.test_connection(UID, AISettingsInput(**CFG))
    assert not r.ok and r.stage == "embedding" and r.code == "AI_PROVIDER_ERROR"
    assert "3072" in (r.message or "") and "1536" in (r.message or "")
    assert harness["big"].closed


async def test_chat_failure_keeps_embedding_result(harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quickassist.business.ai_settings.service.build_raw_provider",
        lambda cfg, **kw: harness.setdefault("cf", StubProbe(dim=1536, chat_fail=True)))
    svc = AISettingsService(None)  # type: ignore[arg-type]
    r = await svc.test_connection(UID, AISettingsInput(**CFG))
    assert not r.ok and r.stage == "chat" and r.message == "http 401"
    assert r.embedding is not None and r.embedding["dim"] == 1536 and r.embedding["padded"] is False
    assert r.chat is None


async def test_invalid_config_rejected_without_probe(harness) -> None:
    svc = AISettingsService(None)  # type: ignore[arg-type]
    with pytest.raises(AppError) as ei:
        await svc.test_connection(UID, AISettingsInput(**{**CFG, "base_url": "ftp://x"}))
    assert ei.value.code == "AI_CONFIG_INVALID"
    assert "probe" not in harness  # chưa từng tạo client
