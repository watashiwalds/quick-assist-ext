"""Public API của module notes cho module KHÁC (search, ai).

Chỉ expose dữ liệu tối thiểu dưới dạng DTO bất biến — module khác không được
cầm ORM object `Note` để tránh sửa ngầm dữ liệu không thuộc quyền sở hữu.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.modules.notes.models import Note
from quickassist.modules.notes.repository import NoteRepository


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


async def get_briefs(
    session: AsyncSession, user_id: uuid.UUID, note_ids: list[uuid.UUID]
) -> dict[uuid.UUID, NoteBrief]:
    rows = await NoteRepository(session).get_many(user_id, note_ids)
    return {n.id: NoteBrief(n.id, n.folder_id, n.title, n.url, n.domain) for n in rows}


async def set_index_status(
    session: AsyncSession, note_id: uuid.UUID, *, status: str, index_rev: int,
    error: str | None = None,
) -> None:
    """Chỉ cập nhật nếu index_rev còn khớp → job cũ không ghi đè trạng thái của lần sửa mới.
    Không tăng version: đây là trạng thái hệ thống, không phải chỉnh sửa của người dùng."""
    await session.execute(
        update(Note)
        .where(Note.id == note_id, Note.index_rev == index_rev)
        .values(index_status=status, index_error=error)
    )
