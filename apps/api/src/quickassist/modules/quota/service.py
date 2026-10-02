"""Quota theo mô hình RESERVE → COMMIT/RELEASE (SDS §5.1.2, §5.1.4).

    lease = await quota.reserve(user_id, "summary", estimate, request_id)   # trước khi gọi AI
    ... gọi AI ...
    await quota.commit(lease, actual_tokens)                                # trừ số thật
    # hoặc await quota.release(lease) nếu AI lỗi → không trừ

- Kiểm tra + giữ chỗ bằng MỘT câu UPDATE có điều kiện → nguyên tử, không race.
- request_id UNIQUE trong ledger → retry không trừ trùng.
- Service tự commit từng bước: quota phải bền vững kể cả khi nghiệp vụ phía sau rollback.
  Vì vậy hãy dùng session RIÊNG cho quota (xem `QuotaService.standalone()`).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.core.config import get_settings
from quickassist.core.errors import QuotaExceeded
from quickassist.core.logging import get_logger
from quickassist.modules.quota.models import QuotaAccount, QuotaLedger

log = get_logger(__name__)


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

    async def _ensure_account(self, user_id: uuid.UUID) -> None:
        await self.s.execute(
            insert(QuotaAccount)
            .values(user_id=user_id, limit_tokens=get_settings().quota_default_tokens,
                    used_tokens=0, reserved_tokens=0)
            .on_conflict_do_nothing(index_elements=[QuotaAccount.user_id])
        )

    async def status(self, user_id: uuid.UUID) -> QuotaStatus:
        await self._ensure_account(user_id)
        await self.s.commit()
        acc = (await self.s.execute(
            select(QuotaAccount).where(QuotaAccount.user_id == user_id)
        )).scalar_one()
        return QuotaStatus(acc.limit_tokens, acc.used_tokens, acc.reserved_tokens)

    async def reserve(self, user_id: uuid.UUID, operation: str, estimate: int, request_id: str) -> QuotaLease:
        await self._ensure_account(user_id)
        existing = (await self.s.execute(
            select(QuotaLedger).where(QuotaLedger.request_id == request_id)
        )).scalar_one_or_none()
        if existing is not None:
            return QuotaLease(user_id, request_id, existing.reserved_tokens,
                              already_settled=existing.status != "RESERVED")

        ok = (await self.s.execute(
            update(QuotaAccount)
            .where(
                QuotaAccount.user_id == user_id,
                QuotaAccount.used_tokens + QuotaAccount.reserved_tokens + estimate
                <= QuotaAccount.limit_tokens,
            )
            .values(reserved_tokens=QuotaAccount.reserved_tokens + estimate)
            .returning(QuotaAccount.user_id)
        )).scalar_one_or_none()
        if ok is None:
            await self.s.rollback()
            raise QuotaExceeded("Bạn đã dùng hết hạn mức AI", code="QUOTA_EXCEEDED")
        self.s.add(QuotaLedger(user_id=user_id, request_id=request_id, operation=operation,
                               reserved_tokens=estimate, status="RESERVED"))
        await self.s.commit()
        return QuotaLease(user_id, request_id, estimate)

    async def _settle(self, lease: QuotaLease, actual: int, status: str) -> None:
        if lease.already_settled:
            return
        row = (await self.s.execute(
            update(QuotaLedger)
            .where(QuotaLedger.request_id == lease.request_id, QuotaLedger.status == "RESERVED")
            .values(status=status, actual_tokens=actual, settled_at=datetime.now(UTC))
            .returning(QuotaLedger.id)
        )).scalar_one_or_none()
        if row is None:  # đã settle bởi lần gọi trước
            await self.s.rollback()
            return
        await self.s.execute(
            update(QuotaAccount)
            .where(QuotaAccount.user_id == lease.user_id)
            .values(reserved_tokens=QuotaAccount.reserved_tokens - lease.reserved,
                    used_tokens=QuotaAccount.used_tokens + actual)
        )
        await self.s.commit()

    async def commit(self, lease: QuotaLease, actual_tokens: int) -> None:
        await self._settle(lease, max(0, actual_tokens), "COMMITTED")

    async def release(self, lease: QuotaLease) -> None:
        await self._settle(lease, 0, "RELEASED")
