import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from quickassist.core.db import Base

# Cố định theo migration. Đổi model embedding khác số chiều = migration mới + reindex toàn bộ.
EMBEDDING_DIM = 1536


class NoteChunk(Base):
    """Index tìm kiếm — module search SỞ HỮU bảng này (đọc lẫn ghi).

    folder_id là bản sao (denormalized) từ notes để lọc theo thư mục mà không JOIN
    sang bảng của module khác; được đồng bộ qua job `search.index_note`.
    """

    __tablename__ = "note_chunks"
    __table_args__ = (
        Index("ix_note_chunks_user_folder", "user_id", "folder_id"),
        Index("ix_note_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_note_chunks_embedding_hnsw", "embedding",
            postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))  # hash nội dung NOTE lúc index
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    # 'simple' = không stemming → phù hợp tiếng Việt hơn cấu hình 'english'.
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True))
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
