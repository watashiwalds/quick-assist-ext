"""Presentation Layer — DTO request/response (summary, rag)."""

import uuid

from pydantic import Field

from quickassist.presentation.schemas.common import ApiModel


class SummaryIn(ApiModel):
    text: str | None = Field(default=None, min_length=1)
    note_id: uuid.UUID | None = None


class SummaryOut(ApiModel):
    summary: str
    tokens_used: int
    request_id: str
