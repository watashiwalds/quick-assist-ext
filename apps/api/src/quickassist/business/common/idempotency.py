"""Business Layer — Idempotency-Key cho thao tác tạo mới (SDS §5.1.2, NFR độ tin cậy).

Client sinh UUID cho mỗi thao tác "lưu" và gửi header `Idempotency-Key`.
Gửi lại cùng key + cùng nội dung → trả lại ĐÚNG bản ghi đã tạo, không tạo trùng.
Cùng key nhưng nội dung khác → Conflict (409).
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import Conflict
from quickassist.data_access.repositories.idempotency_repository import IdempotencyRepository

TTL = timedelta(hours=24)


def hash_request(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class IdempotencyGuard:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID, key: str, scope: str, request_hash: str):
        self.repo = IdempotencyRepository(session)
        self.user_id, self.key, self.scope, self.request_hash = user_id, key, scope, request_hash

    async def existing_resource(self) -> uuid.UUID | None:
        row = await self.repo.find(self.user_id, self.key, datetime.now(UTC) - TTL)
        if row is None:
            return None
        if row.scope != self.scope or row.request_hash != self.request_hash:
            raise Conflict("Idempotency-Key đã dùng cho request khác", code="IDEMPOTENCY_KEY_REUSED")
        return row.resource_id

    async def remember(self, resource_id: uuid.UUID) -> bool:
        """Ghi trong CÙNG transaction với bản ghi được tạo. False → request song song đã thắng."""
        await self.repo.delete_expired(self.user_id, self.key, datetime.now(UTC) - TTL)
        return await self.repo.insert_if_absent(
            user_id=self.user_id, key=self.key, scope=self.scope,
            request_hash=self.request_hash, resource_id=resource_id,
        )
