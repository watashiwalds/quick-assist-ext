"""Business Layer — kiểm tra sức khoẻ hệ thống (dùng cho /health/ready)."""

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data_access.repositories.system_repository import SystemRepository


class HealthService:
    def __init__(self, session: AsyncSession) -> None:
        self.system = SystemRepository(session)

    async def check_ready(self) -> dict[str, str]:
        await self.system.ping()
        return {"status": "ok", "db": "ok"}
