"""Data Access Layer — QuotaRepository (quota_accounts, quota_ledger). Chỉ business/quota được dùng.

Mọi thao tác trừ/giữ quota là MỘT câu UPDATE có điều kiện → nguyên tử, không race.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data.models.quota import QuotaAccount, QuotaLedger


class QuotaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def ensure_account(self, user_id: uuid.UUID, default_limit: int) -> None:
        await self.s.execute(
            insert(QuotaAccount)
            .values(user_id=user_id, limit_tokens=default_limit, used_tokens=0, reserved_tokens=0)
            .on_conflict_do_nothing(index_elements=[QuotaAccount.user_id])
        )

    async def get_account(self, user_id: uuid.UUID) -> QuotaAccount:
        return (await self.s.execute(
            select(QuotaAccount).where(QuotaAccount.user_id == user_id)
        )).scalar_one()

    async def find_ledger(self, request_id: str) -> QuotaLedger | None:
        return (await self.s.execute(
            select(QuotaLedger).where(QuotaLedger.request_id == request_id)
        )).scalar_one_or_none()

    async def try_reserve(self, user_id: uuid.UUID, tokens: int) -> bool:
        """Giữ chỗ nếu còn đủ hạn mức. Trả False nếu không đủ."""
        row = (await self.s.execute(
            update(QuotaAccount)
            .where(
                QuotaAccount.user_id == user_id,
                QuotaAccount.used_tokens + QuotaAccount.reserved_tokens + tokens
                <= QuotaAccount.limit_tokens,
            )
            .values(reserved_tokens=QuotaAccount.reserved_tokens + tokens)
            .returning(QuotaAccount.user_id)
        )).scalar_one_or_none()
        return row is not None

    def add_ledger(self, entry: QuotaLedger) -> None:
        self.s.add(entry)

    async def settle_ledger(self, request_id: str, *, status: str, actual: int) -> bool:
        """Chuyển ledger RESERVED → status. Trả False nếu đã settle trước đó (chống trừ trùng)."""
        row = (await self.s.execute(
            update(QuotaLedger)
            .where(QuotaLedger.request_id == request_id, QuotaLedger.status == "RESERVED")
            .values(status=status, actual_tokens=actual, settled_at=datetime.now(UTC))
            .returning(QuotaLedger.id)
        )).scalar_one_or_none()
        return row is not None

    async def apply_settlement(self, user_id: uuid.UUID, *, reserved: int, actual: int) -> None:
        await self.s.execute(
            update(QuotaAccount)
            .where(QuotaAccount.user_id == user_id)
            .values(reserved_tokens=QuotaAccount.reserved_tokens - reserved,
                    used_tokens=QuotaAccount.used_tokens + actual)
        )
