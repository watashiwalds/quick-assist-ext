"""Presentation Layer — DTO request/response (notes)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl

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
class NoteCreateIn(ApiModel):
    content: str = Field(min_length=1)
    url: HttpUrl | None = None
    title: str | None = Field(default=None, max_length=500)
    folder_id: uuid.UUID | None = None  # None → Inbox


class NoteUpdateIn(ApiModel):
    version: int = Field(ge=1, description="Version client đang giữ — lệch sẽ trả 409")
    content: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, max_length=500)
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


class BulkDeleteIn(ApiModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class BulkDeleteOut(ApiModel):
    deleted: int
