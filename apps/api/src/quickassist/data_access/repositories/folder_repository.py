"""Data Access Layer — FolderRepository (bảng folders). Chỉ business/notes được dùng.

MỌI query đều lọc theo user_id (chống IDOR)."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.data.models.note import INBOX_NAME, Folder


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
