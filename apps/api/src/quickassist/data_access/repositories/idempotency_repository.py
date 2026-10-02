"""Data Access Layer — IdempotencyRepository (bảng idempotency_keys). Dùng bởi business/common/idempotency."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data.models.idempotency_key import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def find(self, user_id: uuid.UUID, key: str, newer_than: datetime) -> IdempotencyKey | None:
        return (await self.s.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == key,
                IdempotencyKey.created_at > newer_than,
            )
        )).scalar_one_or_none()

    async def delete_expired(self, user_id: uuid.UUID, key: str, older_than: datetime) -> None:
        await self.s.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == key,
                IdempotencyKey.created_at <= older_than,
            )
        )

    async def insert_if_absent(self, *, user_id: uuid.UUID, key: str, scope: str, request_hash: str,
                               resource_id: uuid.UUID) -> bool:
        result = await self.s.execute(
            insert(IdempotencyKey)
            .values(user_id=user_id, key=key, scope=scope, request_hash=request_hash,
                    resource_id=resource_id)
            .on_conflict_do_nothing()
        )
        return result.rowcount == 1
