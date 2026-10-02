import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from quickassist.core.db import Base


class QuotaAccount(Base):
    """Số dư hiện hành. Ràng buộc CHECK đảm bảo không bao giờ vượt hạn mức kể cả khi race."""

    __tablename__ = "quota_accounts"
    __table_args__ = (
        CheckConstraint("used_tokens >= 0 AND reserved_tokens >= 0", name="non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    limit_tokens: Mapped[int] = mapped_column(BigInteger)
    used_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class QuotaLedger(Base):
    """Nhật ký append-only; request_id UNIQUE → một thao tác AI không bao giờ bị trừ 2 lần."""

    __tablename__ = "quota_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(200), unique=True)
    operation: Mapped[str] = mapped_column(String(50))  # embed_note | search | summary | chat
    reserved_tokens: Mapped[int] = mapped_column(BigInteger)
    actual_tokens: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))  # RESERVED | COMMITTED | RELEASED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
