"""Data Access Layer — UserAISettingsRepository (bảng user_ai_settings). Chỉ business/ai_settings dùng."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data.models.user_ai_settings import UserAISettings


class UserAISettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, user_id: uuid.UUID) -> UserAISettings | None:
        return (await self.s.execute(
            select(UserAISettings).where(UserAISettings.user_id == user_id)
        )).scalar_one_or_none()
