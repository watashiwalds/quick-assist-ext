"""Business Layer — AI Settings Service: cấu hình AI theo từng user (BYOK, ADR-0016).

P1 (resolver): đọc row `user_ai_settings`, giải mã key, tra `provider_cache`.
  - mode='inherit' hoặc chưa có row → provider TOÀN CỤC của server, hành vi y hệt trước đây.
  - mode='byok' → provider per-user (OpenAI-compatible / Gemini), cache theo user.
CRUD + validate + test-connection ở P2; rebuild orchestration ở P3.
"""

import uuid

from cryptography.exceptions import InvalidTag
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import AppError
from quickassist.data_access.repositories.user_ai_settings_repository import UserAISettingsRepository
from quickassist.infrastructure import ai_keys
from quickassist.infrastructure.openai import UserProviderConfig, get_ai_provider, provider_cache
from quickassist.infrastructure.openai.base import AIProvider


class AISettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserAISettingsRepository(session)

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
