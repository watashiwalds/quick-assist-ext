"""Data Access Layer — UserAISettingsRepository (bảng user_ai_settings). Chỉ business/ai_settings dùng."""

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data.models.user_ai_settings import UserAISettings

_UPDATABLE = ("mode", "provider", "base_url", "api_key_enc", "api_key_hint",
              "chat_model", "embedding_model", "embedding_fingerprint", "applied_fingerprint",
              "timeout_seconds")


class UserAISettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, user_id: uuid.UUID) -> UserAISettings | None:
        return (await self.s.execute(
            select(UserAISettings).where(UserAISettings.user_id == user_id)
        )).scalar_one_or_none()

    async def upsert(self, user_id: uuid.UUID, fields: dict[str, Any]) -> UserAISettings:
        """Insert nếu chưa có row, ngược lại chỉ cập nhật các trường có trong `fields`.

        `updated_at` luôn được làm mới. Không commit — business quyết định.
        """
        clean = {k: v for k, v in fields.items() if k in _UPDATABLE}
        row = await self.get(user_id)
        if row is None:
            row = UserAISettings(user_id=user_id, **clean)
            self.s.add(row)
        else:
            for k, v in clean.items():
                setattr(row, k, v)
            row.updated_at = func.now()  # type: ignore[assignment]
        await self.s.flush()
        return row

    async def mark_applied(self, user_id: uuid.UUID, fingerprint: str) -> None:
        """Đánh dấu fingerprint đã được bàn giao cho rebuild. Điều kiện
        `embedding_fingerprint = :fp` để KHÔNG đè dấu lên cấu hình mới hơn (P5 §7.4)."""
        await self.s.execute(
            update(UserAISettings)
            .where(UserAISettings.user_id == user_id,
                   UserAISettings.embedding_fingerprint == fingerprint)
            .values(applied_fingerprint=fingerprint)
        )

    async def fingerprint_is_current(self, user_id: uuid.UUID, fingerprint: str) -> bool:
        """Fingerprint truyền vào có còn là cấu hình hiện hành không (guard chống save cũ
        ghi đè save mới — start_rebuild không được enqueue job của cấu hình đã bị thay)."""
        row = await self.get(user_id)
        return row is not None and row.embedding_fingerprint == fingerprint

    async def set_inherit_fingerprint(self, user_id: uuid.UUID, fingerprint: str) -> None:
        """Đồng bộ fingerprint server hiện tại cho row inherit trước khi repair enqueue."""
        await self.s.execute(
            update(UserAISettings)
            .where(UserAISettings.user_id == user_id,
                   UserAISettings.mode == "inherit")
            .values(embedding_fingerprint=fingerprint)
        )

    async def find_applied_mismatches(self) -> list[tuple[uuid.UUID, str, str | None]]:
        """Các row có applied_fingerprint lệch embedding_fingerprint (crash giữa save và
        rebuild — P5 §7.2). Trả (user_id, mode, embedding_fingerprint) cho worker repair."""
        rows = (await self.s.execute(
            select(UserAISettings.user_id, UserAISettings.mode, UserAISettings.embedding_fingerprint)
            .where(
                UserAISettings.embedding_fingerprint.is_not(None),
                or_(
                    and_(UserAISettings.mode == "byok",
                         UserAISettings.applied_fingerprint.is_(None)),
                    and_(UserAISettings.applied_fingerprint.is_not(None),
                         UserAISettings.applied_fingerprint != UserAISettings.embedding_fingerprint),
                ),
            )
        )).all()
        return [(r[0], r[1], r[2]) for r in rows]
