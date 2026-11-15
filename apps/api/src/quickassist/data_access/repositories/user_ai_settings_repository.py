"""Data Access Layer — UserAISettingsRepository (bảng user_ai_settings). Chỉ business/ai_settings dùng."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data.models.user_ai_settings import UserAISettings

_UPDATABLE = ("mode", "provider", "base_url", "api_key_enc", "api_key_hint",
              "chat_model", "embedding_model", "embedding_fingerprint", "timeout_seconds")


class UserAISettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, user_id: uuid.UUID) -> UserAISettings | None:
        return (await self.s.execute(
            select(UserAISettings).where(UserAISettings.user_id == user_id)
        )).scalar_one_or_none()

    async def upsert(self, user_id: uuid.UUID, fields: dict[str, Any]) -> UserAISettings:
        """Insert nếu chưa có row, ngược lại chỉ cập nhật các trường có trong `fields`.

        `updated_at` luôn được làm mới. Không commit — business quyết định.
        """
        clean = {k: v for k, v in fields.items() if k in _UPDATABLE}
        row = await self.get(user_id)
        if row is None:
            row = UserAISettings(user_id=user_id, **clean)
            self.s.add(row)
        else:
            for k, v in clean.items():
                setattr(row, k, v)
            row.updated_at = func.now()  # type: ignore[assignment]
        await self.s.flush()
        return row
