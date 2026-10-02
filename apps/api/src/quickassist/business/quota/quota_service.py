"""Business Layer — QuotaService (SDS §5.2 "Quota Service"): kiểm tra hạn mức TRƯỚC mỗi lệnh
gọi OpenAI và ghi nhận token thực tế theo request_id.

Mô hình RESERVE → COMMIT/RELEASE:
    lease = await quota.reserve(user_id, "summary", estimate, request_id)   # trước khi gọi AI
    ... gọi AI ...
    await quota.commit(lease, actual_tokens)     # trừ số thật
    # hoặc await quota.release(lease)            # AI lỗi → không trừ

QuotaService TỰ COMMIT từng bước: quota phải bền vững kể cả khi nghiệp vụ phía sau
rollback → luôn tạo trên một session RIÊNG (`QuotaService.open()`).
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import QuotaExceeded
from quickassist.data.database import get_sessionmaker
from quickassist.data.models.quota import QuotaLedger
from quickassist.data_access.repositories.quota_repository import QuotaRepository
from quickassist.infrastructure.config import get_settings


@dataclass(frozen=True)
class QuotaLease:
    user_id: uuid.UUID
    request_id: str
    reserved: int
    already_settled: bool = False  # request_id đã xử lý trước đó (retry) → bỏ qua


@dataclass(frozen=True)
class QuotaStatus:
    limit_tokens: int
    used_tokens: int
    reserved_tokens: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit_tokens - self.used_tokens - self.reserved_tokens)


class QuotaService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session
        self.repo = QuotaRepository(session)

    @classmethod
    @asynccontextmanager
    async def open(cls) -> AsyncIterator["QuotaService"]:
        """QuotaService trên session riêng — dùng từ service khác (semantic_search, summary, rag)."""
        async with get_sessionmaker()() as session:
            yield cls(session)

    async def status(self, user_id: uuid.UUID) -> QuotaStatus:
        await self.repo.ensure_account(user_id, get_settings().quota_default_tokens)
        await self.s.commit()
        acc = await self.repo.get_account(user_id)
        return QuotaStatus(acc.limit_tokens, acc.used_tokens, acc.reserved_tokens)

    async def reserve(self, user_id: uuid.UUID, operation: str, estimate: int, request_id: str) -> QuotaLease:
        await self.repo.ensure_account(user_id, get_settings().quota_default_tokens)
        existing = await self.repo.find_ledger(request_id)
        if existing is not None:
            return QuotaLease(user_id, request_id, existing.reserved_tokens,
                              already_settled=existing.status != "RESERVED")
        if not await self.repo.try_reserve(user_id, estimate):
            await self.s.rollback()
            raise QuotaExceeded("Bạn đã dùng hết hạn mức AI", code="QUOTA_EXCEEDED")
        self.repo.add_ledger(QuotaLedger(user_id=user_id, request_id=request_id, operation=operation,
                                         reserved_tokens=estimate, status="RESERVED"))
        await self.s.commit()
        return QuotaLease(user_id, request_id, estimate)

    async def _settle(self, lease: QuotaLease, actual: int, status: str) -> None:
        if lease.already_settled:
            return
        if not await self.repo.settle_ledger(lease.request_id, status=status, actual=actual):
            await self.s.rollback()  # đã settle bởi lần gọi trước
            return
        await self.repo.apply_settlement(lease.user_id, reserved=lease.reserved, actual=actual)
        await self.s.commit()

    async def commit(self, lease: QuotaLease, actual_tokens: int) -> None:
        await self._settle(lease, max(0, actual_tokens), "COMMITTED")

    async def release(self, lease: QuotaLease) -> None:
        await self._settle(lease, 0, "RELEASED")
