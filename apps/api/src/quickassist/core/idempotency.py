"""Idempotency-Key cho request tạo mới (SDS §5.1.2, NFR độ tin cậy).

Extension sinh UUID cho mỗi thao tác "lưu" và gửi trong header `Idempotency-Key`.
Retry cùng key + cùng body → trả lại đúng kết quả cũ, không tạo bản ghi trùng.
Cùng key nhưng body khác → 409.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Integer, String, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from quickassist.core.db import Base
from quickassist.core.errors import Conflict

TTL = timedelta(hours=24)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    scope: Mapped[str] = mapped_column(String(50))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def hash_request(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


async def lookup(
    session: AsyncSession, user_id: uuid.UUID, key: str, scope: str, request_hash: str
) -> tuple[int, dict[str, Any]] | None:
    row = (
        await session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.key == key,
                IdempotencyKey.created_at > datetime.now(UTC) - TTL,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.scope != scope or row.request_hash != request_hash:
        raise Conflict("Idempotency-Key đã dùng cho request khác", code="IDEMPOTENCY_KEY_REUSED")
    return row.status_code, row.response


async def remember(
    session: AsyncSession,
    user_id: uuid.UUID,
    key: str,
    scope: str,
    request_hash: str,
    status_code: int,
    response: dict[str, Any],
) -> bool:
    """Lưu kết quả trong CÙNG transaction với bản ghi được tạo.

    Trả False nếu một request song song đã ghi key trước → caller rollback và lookup lại.
    """
    await session.execute(
        delete(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.key == key,
            IdempotencyKey.created_at <= datetime.now(UTC) - TTL,
        )
    )
    result = await session.execute(
        insert(IdempotencyKey)
        .values(user_id=user_id, key=key, scope=scope, request_hash=request_hash,
                status_code=status_code, response=response)
        .on_conflict_do_nothing()
    )
    return result.rowcount == 1
