from fastapi import APIRouter

from quickassist.core.db import DbSession
from quickassist.core.jobs import ping_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: DbSession) -> dict[str, str]:
    await ping_db(session)
    return {"status": "ok", "db": "ok"}
