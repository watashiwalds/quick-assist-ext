"""Entity UserAISettings — cấu hình AI per-user (BYOK), owner: business/ai_settings (ADR-0016).

mode='inherit' → mọi lời gọi AI dùng provider toàn cục của server (hành vi mặc định,
không có row cũng tương đương). mode='byok' → server proxy lời gọi qua provider của user;
key lưu mã hoá AES-GCM (infrastructure/ai_keys), KHÔNG bao giờ nằm trong response API.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, LargeBinary, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from quickassist.data.database import Base

AI_MODES = ("inherit", "byok")
AI_PROVIDERS = ("openai", "gemini")


class UserAISettings(Base):
    """Cấu hình AI của user. PRIMARY KEY = user_id (một cấu hình active / user, D5).

    mode='inherit' vẫn giữ row (nếu đã từng cấu hình) để biết embedding_fingerprint
    đang dùng; cột byok được phép NULL khi quay về inherit.
    """

    __tablename__ = "user_ai_settings"
    __table_args__ = (
        # Tên constraint dùng naming convention ck_%(table_name)s_%(constraint_name)s
        # → khớp nguyên văn tên trong migration 0003.
        CheckConstraint("mode IN ('inherit','byok')", name="mode"),
        CheckConstraint(
            "mode = 'inherit' OR ("
            "provider IS NOT NULL AND base_url IS NOT NULL AND "
            "chat_model IS NOT NULL AND embedding_model IS NOT NULL AND "
            "embedding_fingerprint IS NOT NULL)",
            name="byok",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="inherit")
    provider: Mapped[str | None] = mapped_column(String(20))
    base_url: Mapped[str | None] = mapped_column(Text)
    # nonce(12) || ciphertext || tag(16) — AES-GCM, AAD = user_id.bytes
    api_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    api_key_hint: Mapped[str | None] = mapped_column(String(8))  # 4 ký tự cuối để hiển thị
    chat_model: Mapped[str | None] = mapped_column(String(100))
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    # sha256(provider|base_url|model) — đổi key/chat model KHÔNG đổi fingerprint
    embedding_fingerprint: Mapped[str | None] = mapped_column(String(64))
    timeout_seconds: Mapped[float | None] = mapped_column(Numeric(6, 2))  # NULL = dùng global
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
