"""Data Access Layer — kiểm tra kết nối CSDL (health/readiness)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SystemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def ping(self) -> None:
        await self.s.execute(text("SELECT 1"))
