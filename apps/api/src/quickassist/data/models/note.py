"""Entity Folder, Note — owner: business/notes (Notes Service)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from quickassist.data.database import Base

INBOX_NAME = "Inbox"

# Trạng thái xử lý AI của note (SDS §5.1.2). Note gốc LUÔN được lưu dù AI lỗi.
INDEX_STATUSES = ("PROCESSING", "READY", "SKIPPED", "FAILED")


class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_folders_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint(
            "index_status IN ('PROCESSING','READY','SKIPPED','FAILED')", name="index_status"
        ),
        CheckConstraint("source_type IN ('selection','document')", name="ck_notes_source_type"),
        CheckConstraint(
            "part_index >= 0 AND part_count >= 1 AND part_index < part_count",
            name="ck_notes_part_range",
        ),
        UniqueConstraint(
            "user_id", "document_id", "part_index", name="uq_notes_user_document_part"
        ),
        Index("ix_notes_user_updated", "user_id", "updated_at", "id"),
        Index("ix_notes_user_folder", "user_id", "folder_id"),
        Index("ix_notes_user_document", "user_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="RESTRICT")
    )
    url: Mapped[str | None] = mapped_column(String(2048))
    domain: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    # Tài liệu dài = nhiều note vật lý cùng document_id (D2). Note cũ: NULL / 0 / 1 / selection.
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    part_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    part_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    original_chars: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(20), default="selection", server_default="selection")
    summary_text: Mapped[str | None] = mapped_column(Text)
    index_status: Mapped[str] = mapped_column(String(20), default="PROCESSING")
    index_error: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic concurrency (do user sửa)
    # Tăng mỗi khi cần index lại (nội dung/thư mục/xoá). Job index chỉ ghi trạng thái nếu
    # index_rev còn khớp → sửa tiêu đề không làm note kẹt PROCESSING, sửa nội dung giữa
    # chừng không bị job cũ ghi đè READY.
    index_rev: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # tombstone cho sync
