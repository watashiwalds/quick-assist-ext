"""API Controller — health/readiness."""

from fastapi import APIRouter

from quickassist.business.system import HealthService
from quickassist.presentation.api.deps import DbSession

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: DbSession) -> dict[str, str]:
    return await HealthService(session).check_ready()
