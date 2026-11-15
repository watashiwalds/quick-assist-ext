"""Business Layer — AI Settings Service: cấu hình AI theo từng user (BYOK, ADR-0016).

- `provider_for(user_id)`: resolver cho API dependency và indexing worker (P1).
- `get/save/delete`: CRUD cấu hình + validate (§5). Key chỉ vào DB dưới dạng ciphertext
  AES-GCM; response KHÔNG bao giờ chứa key.
- `test_connection`: kiểm tra kết nối embed+complete với timeout ngắn (§4.9).
- `is_byok`: quota dùng để cho phép reset usage (D6).
- Rebuild chỉ mục khi fingerprint đổi: orchestration ở P3.
"""

import hashlib
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.exceptions import InvalidTag
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import AppError
from quickassist.data.models.user_ai_settings import UserAISettings
from quickassist.data_access.repositories.user_ai_settings_repository import UserAISettingsRepository
from quickassist.infrastructure import ai_keys
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.openai import (
    UserProviderConfig,
    build_raw_provider,
    get_ai_provider,
    provider_cache,
)
from quickassist.infrastructure.openai.base import AIProvider, AIProviderError, ChatMessage
from quickassist.infrastructure.openai.dimensions import CANONICAL_DIM

_TIMEOUT_RANGE = (5.0, 600.0)

# Test kết nối: timeout ngắn cố định, không retry → phản hồi nhanh cho UI (§4.9).
_TEST_TIMEOUT_SECONDS = 30.0
_TEST_EMBED_TEXT = "Hà Nội là thủ đô của Việt Nam."
_TEST_CHAT = [ChatMessage("system", "Bạn trả lời cực ngắn gọn."),
              ChatMessage("user", "Thủ đô của Việt Nam là gì? Trả lời đúng một từ.")]


@dataclass(frozen=True)
class AITestResult:
    ok: bool
    embedding: dict[str, object] | None = None  # {model, dim, padded, latency_ms}
    chat: dict[str, object] | None = None       # {model, latency_ms, sample}
    stage: str | None = None
    code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class AISettingsInput:
    """Input của save() — controller truyền từ AISettingsIn.model_dump()."""

    mode: str
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # None = giữ key cũ; "" = xoá key; khác rỗng = thay key
    chat_model: str | None = None
    embedding_model: str | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class AISettingsState:
    """Trạng thái cấu hình để controller dựng response (không bao giờ chứa key)."""

    mode: str
    provider: str | None
    base_url: str | None
    has_key: bool
    key_hint: str | None
    chat_model: str | None
    embedding_model: str | None
    timeout_seconds: float | None
    rebuild_note_count: int = 0  # wire thật ở P3 (rebuild orchestration)


def embedding_fingerprint(provider: str, base_url: str, embedding_model: str) -> str:
    """sha256(provider|base_url|model) — ĐỔI KEY hoặc CHAT MODEL KHÔNG đổi fingerprint
    → không rebuild. Đổi embedding model / base_url / provider → rebuild (P3 dùng)."""
    raw = f"{provider}|{base_url.rstrip('/')}|{embedding_model}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _invalid(message: str) -> AppError:
    return AppError(message, code="AI_CONFIG_INVALID")


def validate_base_url(base_url: str | None) -> str:
    """Bắt buộc http/https, host không rỗng; allowlist khác rỗng → phải khớp prefix (§5)."""
    if not base_url or not base_url.strip():
        raise _invalid("base_url không được để trống")
    base_url = base_url.strip()
    u = urlparse(base_url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise _invalid("base_url phải là URL http/https hợp lệ")
    allowlist = get_settings().ai_base_url_allowlist
    if allowlist and not any(base_url.rstrip("/").startswith(a.rstrip("/")) for a in allowlist):
        raise _invalid("base_url không nằm trong danh sách được phép (AI_BASE_URL_ALLOWLIST)")
    return base_url


def _validate(data: AISettingsInput) -> None:
    if data.provider not in ("openai", "gemini"):
        raise _invalid("provider phải là 'openai' hoặc 'gemini'")
    for name, value in (("chat_model", data.chat_model), ("embedding_model", data.embedding_model)):
        if not value or not value.strip():
            raise _invalid(f"{name} không được để trống")
        if len(value.strip()) > 100:
            raise _invalid(f"{name} dài tối đa 100 ký tự")
    lo, hi = _TIMEOUT_RANGE
    if data.timeout_seconds is not None and not (lo <= data.timeout_seconds <= hi):
        raise _invalid(f"timeout_seconds phải trong [{lo:.0f}, {hi:.0f}]")


def _state(row: UserAISettings | None) -> AISettingsState:
    if row is None:
        return AISettingsState(mode="inherit", provider=None, base_url=None, has_key=False,
                               key_hint=None, chat_model=None, embedding_model=None, timeout_seconds=None)
    return AISettingsState(
        mode=row.mode, provider=row.provider, base_url=row.base_url,
        has_key=row.api_key_enc is not None, key_hint=row.api_key_hint,
        chat_model=row.chat_model, embedding_model=row.embedding_model,
        timeout_seconds=float(row.timeout_seconds) if row.timeout_seconds is not None else None,
    )


class AISettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserAISettingsRepository(session)
        self._session = session

    # ---------------------------------------------------------- resolver (P1)
    async def provider_for(self, user_id: uuid.UUID) -> AIProvider:
        """Provider AI của user. Được cả API dependency và indexing worker dùng → cùng cache."""
        row = await self._repo.get(user_id)
        if row is None or row.mode == "inherit":
            return get_ai_provider()

        if row.provider not in ("openai", "gemini"):
            raise AppError("Cấu hình AI của user không hợp lệ", code="AI_CONFIG_INVALID")
        api_key = ""
        if row.api_key_enc is not None:
            try:
                api_key = ai_keys.decrypt(user_id, row.api_key_enc)
            except (InvalidTag, ValueError) as e:
                # Xoay JWT_SECRET khi chưa đặt AI_KEY_SECRET → key cũ không đọc được (runbook).
                raise AppError(
                    "Khoá API đã lưu không giải mã được (server đổi khoá mã hoá?), "
                    "vui lòng nhập lại khoá trong Cài đặt",
                    code="AI_KEY_UNREADABLE",
                ) from e

        cfg = UserProviderConfig(
            user_id=str(user_id),
            provider=row.provider,  # type: ignore[arg-type] — đã kiểm tra ở trên
            base_url=row.base_url or "",
            api_key=api_key,
            chat_model=row.chat_model or "",
            embedding_model=row.embedding_model or "",
            timeout_seconds=float(row.timeout_seconds) if row.timeout_seconds is not None else None,
        )
        return provider_cache.get_or_build(cfg)

    # ---------------------------------------------------------- CRUD (P2)
    async def get(self, user_id: uuid.UUID) -> AISettingsState:
        return _state(await self._repo.get(user_id))

    async def is_byok(self, user_id: uuid.UUID) -> bool:
        row = await self._repo.get(user_id)
        return row is not None and row.mode == "byok"

    async def save(self, user_id: uuid.UUID, data: AISettingsInput) -> AISettingsState:
        if data.mode == "inherit":
            # Quay về cấu hình server: chỉ đổi mode, GIỮ nguyên row (biết fingerprint đang dùng,
            # §4.1). Chưa từng cấu hình → không cần tạo row.
            row = await self._repo.get(user_id)
            if row is not None:
                row = await self._repo.upsert(user_id, {"mode": "inherit"})
                await self._session.commit()
        else:
            _validate(data)
            fields: dict[str, object] = {
                "mode": "byok",
                "provider": data.provider,
                "base_url": validate_base_url(data.base_url),
                "chat_model": data.chat_model.strip() if data.chat_model else None,
                "embedding_model": data.embedding_model.strip() if data.embedding_model else None,
                "embedding_fingerprint": embedding_fingerprint(
                    data.provider or "", data.base_url or "", data.embedding_model or ""),
                "timeout_seconds": data.timeout_seconds,
            }
            if data.api_key is not None:  # None = giữ key cũ (một số model local không cần key)
                key = data.api_key.strip()
                fields["api_key_enc"] = ai_keys.encrypt(user_id, key) if key else None
                fields["api_key_hint"] = key[-4:] if key else None
            row = await self._repo.upsert(user_id, fields)
            await self._session.commit()

        provider_cache.invalidate_user(str(user_id))  # lần gọi kế tiếp dùng key mới ngay
        return _state(row)

    async def delete(self, user_id: uuid.UUID) -> AISettingsState:
        """Về mode=inherit (nút "Dùng cấu hình server"): giữ provider/models làm bản nháp,
        XOÁ key khỏi DB (reset = không giữ vật liệu nhạy cảm)."""
        row = await self._repo.upsert(user_id, {"mode": "inherit", "api_key_enc": None,
                                                "api_key_hint": None})
        await self._session.commit()
        provider_cache.invalidate_user(str(user_id))
        return _state(row)

    # ---------------------------------------------------------- test kết nối (P2, §4.9)
    async def test_connection(self, user_id: uuid.UUID, data: AISettingsInput) -> AITestResult:
        """Chạy 1 embed + 1 complete với timeout 30s, không retry. KHÔNG lưu cấu hình,
        KHÔNG dùng provider cache (cấu hình test có thể khác đã lưu) — đóng client sau khi chạy.

        `api_key` None → dùng key đã lưu; rỗng → không key (model local)."""
        _validate(data)
        base_url = validate_base_url(data.base_url)
        api_key = data.api_key.strip() if data.api_key else ""
        if data.api_key is None:  # không gửi key → dùng key đã lưu (nếu có)
            row = await self._repo.get(user_id)
            if row is not None and row.api_key_enc is not None:
                try:
                    api_key = ai_keys.decrypt(user_id, row.api_key_enc)
                except (InvalidTag, ValueError) as e:
                    raise AppError(
                        "Khoá API đã lưu không giải mã được, vui lòng nhập lại khoá",
                        code="AI_KEY_UNREADABLE",
                    ) from e
        assert data.provider is not None  # _validate đảm bảo
        cfg = UserProviderConfig(
            user_id=str(user_id), provider=data.provider, base_url=base_url, api_key=api_key,
            chat_model=(data.chat_model or "").strip(), embedding_model=(data.embedding_model or "").strip(),
            timeout_seconds=data.timeout_seconds,
        )
        probe = build_raw_provider(cfg, timeout_seconds=_TEST_TIMEOUT_SECONDS, max_retries=0)
        try:
            try:
                t0 = time.perf_counter()
                emb = await probe.embed([_TEST_EMBED_TEXT])
                latency = int((time.perf_counter() - t0) * 1000)
                dim = len(emb.vectors[0]) if emb.vectors else 0
                if dim > CANONICAL_DIM:
                    return AITestResult(
                        ok=False, stage="embedding", code="AI_PROVIDER_ERROR",
                        message=f"Model embedding trả {dim} chiều, vượt giới hạn {CANONICAL_DIM} chiều "
                                "được lưu trữ. Hãy chọn model có số chiều ≤ 1536.")
                embedding = {"model": emb.model, "dim": dim,
                             "padded": dim < CANONICAL_DIM, "latency_ms": latency}
            except AIProviderError as e:
                return AITestResult(ok=False, stage="embedding", code="AI_PROVIDER_ERROR",
                                    message=str(e))
            try:
                t0 = time.perf_counter()
                comp = await probe.complete(_TEST_CHAT, max_tokens=32)
                latency = int((time.perf_counter() - t0) * 1000)
                chat = {"model": comp.model, "latency_ms": latency, "sample": comp.text.strip()[:200]}
            except AIProviderError as e:
                return AITestResult(ok=False, stage="chat", code="AI_PROVIDER_ERROR", message=str(e),
                                    embedding=embedding)
            return AITestResult(ok=True, embedding=embedding, chat=chat)
        finally:
            await probe.aclose()  # client test không vào cache — luôn đóng
