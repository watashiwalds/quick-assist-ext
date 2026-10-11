"""Presentation Layer — DTO hỏi đáp RAG (SDS §5.1.6). Phản hồi là luồng SSE, xem rag_controller."""

import uuid
from typing import Literal

from pydantic import Field

from quickassist.presentation.schemas.common import ApiModel


class ChatTurnIn(ApiModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8_000)


class ChatIn(ApiModel):
    question: str = Field(min_length=1, max_length=2_000)
    folder_id: uuid.UUID | None = None
    # Tối đa 5 cặp hỏi–đáp gần nhất (server tự cắt thêm nếu client gửi dư) — ADR-0012.
    history: list[ChatTurnIn] = Field(default_factory=list, max_length=20)

