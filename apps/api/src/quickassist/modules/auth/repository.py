import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.modules.auth.models import AuthSession


class AuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def add(self, row: AuthSession) -> AuthSession:
        self.s.add(row)
        await self.s.flush()
        return row

    async def get_by_hash_for_update(self, token_hash: str) -> AuthSession | None:
        stmt = (select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
                .with_for_update())
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.s.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
