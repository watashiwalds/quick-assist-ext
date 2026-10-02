"""Truy cập bảng users. CHỈ module accounts được import file này."""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.modules.accounts.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.s.get(User, user_id)

    async def get_by_google_sub(self, sub: str) -> User | None:
        return (await self.s.execute(select(User).where(User.google_sub == sub))).scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.s.add(user)
        await self.s.flush()
        return user

    async def touch(self, user_id: uuid.UUID) -> None:
        await self.s.execute(update(User).where(User.id == user_id).values(last_active_at=func.now()))

    async def delete(self, user_id: uuid.UUID) -> int:
        return (await self.s.execute(delete(User).where(User.id == user_id))).rowcount
