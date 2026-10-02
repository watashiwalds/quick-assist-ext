"""Presentation Layer — DTO request/response (search)."""

import uuid

from pydantic import Field

from quickassist.presentation.schemas.common import ApiModel


class SearchIn(ApiModel):
    query: str = Field(min_length=1, max_length=1000)
    folder_id: uuid.UUID | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHitOut(ApiModel):
    chunk_id: uuid.UUID
    note_id: uuid.UUID
    text: str
    score: float
    note_title: str | None
    note_url: str | None
    folder_id: uuid.UUID


class SearchOut(ApiModel):
    items: list[SearchHitOut]
