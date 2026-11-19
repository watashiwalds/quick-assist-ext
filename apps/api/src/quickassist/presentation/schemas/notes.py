"""Presentation Layer — DTO request/response (notes)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, model_validator

from quickassist.presentation.schemas.common import ApiModel

IndexStatus = Literal["PROCESSING", "READY", "SKIPPED", "FAILED"]


# ---------- Folders ----------
class FolderCreateIn(ApiModel):
    name: str = Field(min_length=1, max_length=100)


class FolderUpdateIn(ApiModel):
    name: str = Field(min_length=1, max_length=100)


class FolderOut(ApiModel):
    id: uuid.UUID
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ---------- Notes ----------
PartContent = Annotated[str, Field(min_length=1)]


class NoteCreateIn(ApiModel):
    content: str | None = Field(default=None, min_length=1)
    url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=500)
    folder_id: uuid.UUID | None = None  # None → Inbox
    # D2 — client chia tài liệu dài thành part ≤ MAX_NOTE_CHARS, gửi một lần cùng document_id.
    document_id: uuid.UUID | None = None
    parts: list[PartContent] | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _one_of_content_or_parts(self) -> "NoteCreateIn":
        if (self.content is None) == (self.parts is None):
            raise ValueError("Gửi đúng một trong content hoặc parts")
        if self.parts is not None and self.document_id is None:
            raise ValueError("parts yêu cầu document_id do client sinh")
        return self


class NoteUpdateIn(ApiModel):
    version: int = Field(ge=1, description="Version client đang giữ — lệch sẽ trả 409")
    content: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, max_length=500)
    url: HttpUrl | None = None
    folder_id: uuid.UUID | None = None


class NoteSummaryIn(ApiModel):
    """Người dùng xác nhận bản tóm tắt preview (SDS §5.1.4)."""

    version: int = Field(ge=1)
    summary_text: str = Field(min_length=1, max_length=10_000)


class NoteOut(ApiModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    url: str | None
    domain: str | None
    title: str | None
    content: str
    summary_text: str | None
    index_status: IndexStatus
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    # D2 — metadata tài liệu nhiều part. Note cũ: None / 0 / 1 / None / selection.
    document_id: uuid.UUID | None = None
    part_index: int = 0
    part_count: int = 1
    original_chars: int | None = None
    source_type: Literal["selection", "document"] = "selection"
    # Chỉ có trong response tạo mới: id mọi part theo part_index (None ở các endpoint khác).
    part_ids: list[uuid.UUID] | None = None


class BulkDeleteIn(ApiModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class BulkDeleteOut(ApiModel):
    deleted: int


class NotesMoveIn(ApiModel):
    """Chuyển nhiều ghi chú sang một thư mục (Phase 2, UX plan §6.4).

    ``folder_id = None`` → Inbox. Chỉ ghi chú thuộc user và chưa bị xoá mới được chuyển;
    id không tồn tại/không sở hữu trả trong ``missing`` thay vì làm hỏng cả lô.
    """

    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    folder_id: uuid.UUID | None = None


class NotesMoveOut(ApiModel):
    moved: int
    missing: list[uuid.UUID]
