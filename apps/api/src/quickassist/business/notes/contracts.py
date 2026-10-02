"""Business Layer — hợp đồng Notes Service cung cấp cho service KHÁC
(semantic_search, summary, rag). Trả DTO bất biến, không trả entity ORM để service
khác không thể sửa ngầm dữ liệu không thuộc quyền sở hữu.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data_access.repositories.note_repository import NoteRepository


@dataclass(frozen=True)
class NoteForIndexing:
    id: uuid.UUID
    user_id: uuid.UUID
    folder_id: uuid.UUID
    title: str | None
    content: str
    index_rev: int
    is_deleted: bool


@dataclass(frozen=True)
class NoteBrief:
    id: uuid.UUID
    folder_id: uuid.UUID
    title: str | None
    url: str | None
    domain: str | None


async def get_note_for_indexing(session: AsyncSession, note_id: uuid.UUID) -> NoteForIndexing | None:
    n = await NoteRepository(session).get_any(note_id)
    if n is None:
        return None
    return NoteForIndexing(n.id, n.user_id, n.folder_id, n.title, n.content, n.index_rev,
                           n.deleted_at is not None)


async def get_note_content(session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID) -> str | None:
    n = await NoteRepository(session).get(user_id, note_id)
    return n.content if n else None


async def get_briefs(session: AsyncSession, user_id: uuid.UUID,
                     note_ids: list[uuid.UUID]) -> dict[uuid.UUID, NoteBrief]:
    rows = await NoteRepository(session).get_many(user_id, note_ids)
    return {n.id: NoteBrief(n.id, n.folder_id, n.title, n.url, n.domain) for n in rows}


async def set_index_status(session: AsyncSession, note_id: uuid.UUID, *, status: str, index_rev: int,
                           error: str | None = None) -> None:
    await NoteRepository(session).set_index_status(note_id, status=status, index_rev=index_rev, error=error)
