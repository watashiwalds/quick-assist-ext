"""Test P2 — validate cấu hình + fingerprint + save/delete semantics (fake repo; DB thật ở
integration). Trọng tâm: key KHÔNG BAO GIỜ xuất hiện ở state, "null giữ key cũ / '' xoá key"."""

import uuid

import pytest

from quickassist.business.ai_settings import (
    AISettingsInput,
    AISettingsService,
    embedding_fingerprint,
)
from quickassist.business.common.exceptions import AppError
from quickassist.infrastructure import ai_keys

UID = uuid.uuid5(uuid.NAMESPACE_DNS, "ai-settings-crud")

BYOK = dict(mode="byok", provider="openai", base_url="http://localhost:11434/v1",
            chat_model="llama3.1", embedding_model="nomic-embed-text", timeout_seconds=180.0)


class SimpleRow:
    def __init__(self, d: dict) -> None:  # type: ignore[type-arg]
        self.__dict__.update(d)


class FakeRepo:
    """Mô phỏng đủ upsert/get của UserAISettingsRepository (in-memory row)."""

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, dict] = {}

    async def get(self, uid: uuid.UUID):  # type: ignore[no-untyped-def]
        d = self.rows.get(uid)
        return None if d is None else SimpleRow(d)

    async def upsert(self, uid: uuid.UUID, fields: dict) -> SimpleRow:  # type: ignore[type-arg]
        self.rows.setdefault(uid, {"user_id": uid, "mode": "inherit", "provider": None,
                                   "base_url": None, "api_key_enc": None, "api_key_hint": None,
                                   "chat_model": None, "embedding_model": None,
                                   "embedding_fingerprint": None, "applied_fingerprint": None,
                                   "timeout_seconds": None})
        self.rows[uid].update(fields)
        return SimpleRow(self.rows[uid])


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def svc(monkeypatch: pytest.MonkeyPatch) -> AISettingsService:
    fake = FakeRepo()
    monkeypatch.setattr(
        "quickassist.business.ai_settings.service.UserAISettingsRepository", lambda _s: fake)
    return AISettingsService(FakeSession())  # type: ignore[arg-type]


def test_validate_embedding_dim() -> None:
    from quickassist.business.ai_settings.service import AISettingsInput, _validate

    with pytest.raises(AppError, match="4096"):
        _validate(AISettingsInput(**BYOK, embedding_dim=4096))
    _validate(AISettingsInput(**BYOK, embedding_dim=768))  # ≤1536: OK
    _validate(AISettingsInput(**BYOK, embedding_dim=None))  # không biết: OK (guard cuối khi embed)


def test_fingerprint_ignores_key_and_chat_model() -> None:
    a = embedding_fingerprint("openai", "http://localhost:11434/v1", "nomic-embed-text")
    assert len(a) == 64
    # đổi key / chat model → KHÔNG đổi fingerprint (không rebuild)
    assert embedding_fingerprint("openai", "http://localhost:11434/v1/", "nomic-embed-text") == a
    # đổi provider / base_url / embedding model → đổi fingerprint (rebuild)
    assert embedding_fingerprint("gemini", "http://localhost:11434/v1", "nomic-embed-text") != a
    assert embedding_fingerprint("openai", "http://other:11434/v1", "nomic-embed-text") != a
    assert embedding_fingerprint("openai", "http://localhost:11434/v1", "bge-m3") != a


def test_validate_base_url_scheme_and_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    from quickassist.business.ai_settings.service import validate_base_url
    assert validate_base_url("http://localhost:11434/v1/") == "http://localhost:11434/v1/"
    for bad in ("ftp://x", "localhost:11434/v1", "javascript:alert(1)", "", "  "):
        with pytest.raises(AppError):
            validate_base_url(bad)

    from quickassist.infrastructure.config import get_settings

    def _with_allowlist(value: str) -> None:
        monkeypatch.setenv("AI_BASE_URL_ALLOWLIST", value)
        get_settings.cache_clear()

    # Bảng bypass SSRF (P5 guide §4.4)
    _with_allowlist("https://api.openai.com")
    assert validate_base_url("https://api.openai.com/v1")
    assert validate_base_url("https://API.OPENAI.COM/v1")  # host lowercase
    assert validate_base_url("https://api.openai.com/v1/x")  # path con
    for bad in (
        "https://api.openai.com.evil.com/v1",  # host thật khác (khớp prefix chuỗi)
        "https://api.openai.com@evil.com/v1",  # userinfo → host thật là evil.com
        "https://api.openai.com:8443/v1",  # sai port
        "http://api.openai.com/v1",  # sai scheme
    ):
        with pytest.raises(AppError):
            validate_base_url(bad)

    _with_allowlist("https://api.openai.com/v1")
    assert validate_base_url("https://api.openai.com/v1/x")  # prefix path được phép
    for bad in (
        "https://api.openai.com/v1evil",  # sai biên segment
        "https://api.openai.com/v2",  # sai path
        "http://localhost:11434/v1",  # host khác
    ):
        with pytest.raises(AppError):
            validate_base_url(bad)

    get_settings.cache_clear()


def test_settings_allowlist_rejects_bad_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Entry hỏng trong allowlist phải fail-fast khi load config, không âm thầm bỏ qua.
    from pydantic import ValidationError

    from quickassist.infrastructure.config import get_settings

    for entry in ("file:///etc/passwd", "https://user:pw@api.openai.com", "https://x.com/v1?a=b"):
        monkeypatch.setenv("AI_BASE_URL_ALLOWLIST", entry)
        get_settings.cache_clear()
        with pytest.raises(ValidationError):
            get_settings()
    get_settings.cache_clear()


async def test_save_byok_encrypts_key_and_state_never_has_plaintext(svc: AISettingsService) -> None:
    r = await svc.save(UID, AISettingsInput(**BYOK, api_key="sk-live-secret-9999"))
    st = r.state
    assert st.mode == "byok" and st.has_key and st.key_hint == "9999"
    assert not hasattr(st, "api_key") and "sk-live-secret" not in repr(st)
    row = svc._repo.rows[UID]
    assert row["api_key_enc"] not in (None, b"")
    assert b"sk-live-secret" not in row["api_key_enc"]  # DB chỉ có ciphertext
    assert ai_keys.decrypt(UID, row["api_key_enc"]) == "sk-live-secret-9999"
    assert len(row["embedding_fingerprint"]) == 64 and row["timeout_seconds"] == 180.0


async def test_save_null_keeps_key_empty_clears_key(svc: AISettingsService) -> None:
    await svc.save(UID, AISettingsInput(**BYOK, api_key="sk-first"))
    await svc.save(UID, AISettingsInput(**BYOK, api_key=None))
    assert svc._repo.rows[UID]["api_key_enc"] is not None  # null → giữ key cũ
    await svc.save(UID, AISettingsInput(**BYOK, api_key=""))
    assert svc._repo.rows[UID]["api_key_enc"] is None  # "" → xoá key
    assert svc._repo.rows[UID]["api_key_hint"] is None


async def test_save_inherit_keeps_row_and_key(svc: AISettingsService) -> None:
    await svc.save(UID, AISettingsInput(**BYOK, api_key="sk-keep"))
    st = (await svc.save(UID, AISettingsInput(mode="inherit"))).state
    row = svc._repo.rows[UID]
    assert st.mode == "inherit" and row["mode"] == "inherit"
    assert row["api_key_enc"] is not None  # giữ nguyên row + key (quay lại BYOK nhanh)
    assert row["provider"] == "openai"  # giữ để biết fingerprint đang dùng


async def test_delete_returns_inherit_and_clears_key(svc: AISettingsService) -> None:
    await svc.save(UID, AISettingsInput(**BYOK, api_key="sk-gone"))
    st = (await svc.delete(UID)).state
    row = svc._repo.rows[UID]
    assert st.mode == "inherit" and not st.has_key
    assert row["api_key_enc"] is None and row["api_key_hint"] is None  # xoá key khỏi DB
    assert row["provider"] == "openai"  # giữ provider/models làm bản nháp


async def test_save_invalid_configs_rejected(svc: AISettingsService) -> None:
    bad = [
        dict(BYOK, provider="anthropic"),
        dict(BYOK, base_url="ftp://x"),
        dict(BYOK, base_url=""),
        dict(BYOK, chat_model=""),
        dict(BYOK, embedding_model="x" * 101),
        dict(BYOK, timeout_seconds=3.0),
        dict(BYOK, timeout_seconds=601.0),
        dict(mode="byok"),  # thiếu hết
    ]
    for i, kwargs in enumerate(bad):
        with pytest.raises(AppError) as ei:
            await svc.save(UID, AISettingsInput(**kwargs))
        assert ei.value.code == "AI_CONFIG_INVALID", i
    assert UID not in svc._repo.rows  # không có gì được lưu


async def test_is_byok(svc: AISettingsService) -> None:
    assert await svc.is_byok(UID) is False  # chưa có row
    await svc.save(UID, AISettingsInput(**BYOK, api_key="sk-x"))
    assert await svc.is_byok(UID) is True
    await svc.delete(UID)
    assert await svc.is_byok(UID) is False


# --- P3/P5: rebuild_required → rebuild orchestration ---


async def test_rebuild_required_semantics(svc: AISettingsService) -> None:
    from quickassist.infrastructure.openai import provider_cache

    def _mark_applied(fp: str) -> None:
        # Mô phỏng controller gọi start_rebuild thành công (mark_applied cùng transaction).
        svc._repo.rows[UID]["applied_fingerprint"] = fp

    r1 = await svc.save(UID, AISettingsInput(**BYOK, api_key="sk-1"))
    assert r1.rebuild_required is True  # chưa có row → byok: chunk đang theo server
    fp_byok = r1.fingerprint
    _mark_applied(fp_byok)

    r2 = await svc.save(UID, AISettingsInput(**{**BYOK, "api_key": "sk-2"}))
    assert r2.rebuild_required is False  # đổi key → fingerprint giữ nguyên + đã applied
    assert r2.fingerprint == fp_byok

    r3 = await svc.save(UID, AISettingsInput(**{**BYOK, "embedding_model": "bge-m3"}))
    assert r3.rebuild_required is True and r3.fingerprint != fp_byok  # đổi model → rebuild
    _mark_applied(r3.fingerprint)

    with_bge = {**BYOK, "embedding_model": "bge-m3"}
    r4 = await svc.save(UID, AISettingsInput(**{**with_bge, "chat_model": "llama3.2"}))
    assert r4.rebuild_required is False  # đổi chat model → không rebuild
    assert r4.fingerprint == r3.fingerprint

    r5 = await svc.save(UID, AISettingsInput(mode="inherit"))
    assert r5.rebuild_required is True  # byok → inherit: fingerprint server khác applied
    _mark_applied(r5.fingerprint)

    r6 = await svc.save(UID, AISettingsInput(mode="inherit"))
    assert r6.rebuild_required is False  # inherit → inherit, đã applied server fp
    provider_cache.invalidate_user(str(UID))


async def test_rebuild_required_when_applied_stale(svc: AISettingsService) -> None:
    # P5 §7: save B (cùng config) sau crash giữa save và rebuild → applied cũ ≠ fp mới → True.
    r = await svc.save(UID, AISettingsInput(**BYOK, api_key="sk-1"))
    assert r.rebuild_required is True
    # KHÔNG mark_applied (giả lập crash trước start_rebuild) → save lại cùng config vẫn rebuild
    r2 = await svc.save(UID, AISettingsInput(**{**BYOK, "api_key": "sk-2"}))
    assert r2.rebuild_required is True and r2.fingerprint == r.fingerprint


async def test_delete_rebuild_required_only_when_was_byok(svc: AISettingsService) -> None:
    r = await svc.delete(UID)  # chưa có row → không có gì để rebuild
    assert r.rebuild_required is False
    r_save = await svc.save(UID, AISettingsInput(**BYOK))
    assert r_save.rebuild_required is True
    svc._repo.rows[UID]["applied_fingerprint"] = r_save.fingerprint  # mô phỏng start_rebuild
    r2 = await svc.delete(UID)
    assert r2.rebuild_required is True and r2.state.mode == "inherit"


async def test_current_fingerprint_byok_uses_stored_row(svc: AISettingsService) -> None:
    await svc.save(UID, AISettingsInput(**BYOK))
    row = svc._repo.rows[UID]
    assert await svc.current_fingerprint(UID) == row["embedding_fingerprint"]
    await svc.save(UID, AISettingsInput(mode="inherit"))
    from quickassist.business.ai_settings import server_embedding_fingerprint
    assert await svc.current_fingerprint(UID) == server_embedding_fingerprint()
