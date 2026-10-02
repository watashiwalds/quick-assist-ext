"""Truy cập folders/notes. MỌI query đều lọc theo user_id (chống IDOR)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.modules.notes.models import INBOX_NAME, Folder, Note


class FolderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def list(self, user_id: uuid.UUID) -> list[Folder]:
        stmt = (select(Folder).where(Folder.user_id == user_id)
                .order_by(Folder.is_default.desc(), Folder.name))
        return list((await self.s.execute(stmt)).scalars())

    async def get(self, user_id: uuid.UUID, folder_id: uuid.UUID) -> Folder | None:
        stmt = select(Folder).where(Folder.id == folder_id, Folder.user_id == user_id)
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def get_by_name(self, user_id: uuid.UUID, name: str) -> Folder | None:
        stmt = select(Folder).where(Folder.user_id == user_id, Folder.name == name)
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def get_or_create_inbox(self, user_id: uuid.UUID) -> Folder:
        # INSERT ... ON CONFLICT DO NOTHING: an toàn khi 2 request đầu tiên chạy song song.
        await self.s.execute(
            insert(Folder).values(id=uuid.uuid4(), user_id=user_id, name=INBOX_NAME, is_default=True)
            .on_conflict_do_nothing(constraint="uq_folders_user_name")
        )
        inbox = await self.get_by_name(user_id, INBOX_NAME)
        assert inbox is not None
        return inbox

    async def add(self, folder: Folder) -> Folder:
        self.s.add(folder)
        await self.s.flush()
        return folder

    async def delete(self, folder: Folder) -> None:
        await self.s.delete(folder)


class NoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def get(self, user_id: uuid.UUID, note_id: uuid.UUID, *, for_update: bool = False,
                  include_deleted: bool = False) -> Note | None:
        stmt = select(Note).where(Note.id == note_id, Note.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Note.deleted_at.is_(None))
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def get_any(self, note_id: uuid.UUID) -> Note | None:
        """Không lọc user — CHỈ dùng trong job nền (đã có note_id từ hệ thống)."""
        return await self.s.get(Note, note_id)

    async def list_page(
        self, user_id: uuid.UUID, *, folder_id: uuid.UUID | None, updated_since: datetime | None,
        after: tuple[datetime, uuid.UUID] | None, limit: int, include_deleted: bool,
    ) -> list[Note]:
        """Sắp theo (updated_at, id) tăng dần → dùng được cho cả hiển thị lẫn sync tăng dần."""
        conds = [Note.user_id == user_id]
        if folder_id:
            conds.append(Note.folder_id == folder_id)
        if updated_since:
            conds.append(Note.updated_at > updated_since)
        if not include_deleted:
            conds.append(Note.deleted_at.is_(None))
        if after:
            ts, nid = after
            conds.append(or_(Note.updated_at > ts, and_(Note.updated_at == ts, Note.id > nid)))
        stmt = select(Note).where(*conds).order_by(Note.updated_at, Note.id).limit(limit)
        return list((await self.s.execute(stmt)).scalars())

    async def add(self, note: Note) -> Note:
        self.s.add(note)
        await self.s.flush()
        await self.s.refresh(note)
        return note

    async def soft_delete_many(self, user_id: uuid.UUID, ids: list[uuid.UUID]) -> list[uuid.UUID]:
        stmt = (
            update(Note)
            .where(Note.user_id == user_id, Note.id.in_(ids), Note.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC), version=Note.version + 1,
                    index_rev=Note.index_rev + 1, updated_at=func.now())
            .returning(Note.id)
        )
        return list((await self.s.execute(stmt)).scalars())

    async def move_all(
        self, user_id: uuid.UUID, from_folder: uuid.UUID, to_folder: uuid.UUID
    ) -> list[uuid.UUID]:
        stmt = (
            update(Note)
            .where(Note.user_id == user_id, Note.folder_id == from_folder)
            .values(folder_id=to_folder, version=Note.version + 1,
                    index_rev=Note.index_rev + 1, updated_at=func.now())
            .returning(Note.id)
        )
        return list((await self.s.execute(stmt)).scalars())

    async def get_many(self, user_id: uuid.UUID, ids: list[uuid.UUID]) -> list[Note]:
        stmt = select(Note).where(Note.user_id == user_id, Note.id.in_(ids), Note.deleted_at.is_(None))
        return list((await self.s.execute(stmt)).scalars())
