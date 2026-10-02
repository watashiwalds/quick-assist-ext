"""Business Layer — quản lý thư mục (thuộc Notes Service). Thư mục mặc định: Inbox."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import Conflict, NotFound
from quickassist.business.notes.indexing_events import publish_note_changed
from quickassist.data.models.note import Folder
from quickassist.data_access.repositories.folder_repository import FolderRepository
from quickassist.data_access.repositories.note_repository import NoteRepository


class FolderService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session
        self.folders = FolderRepository(session)
        self.notes = NoteRepository(session)

    async def list_all(self, user_id: uuid.UUID) -> list[Folder]:
        await self.folders.get_or_create_inbox(user_id)
        await self.s.commit()
        return await self.folders.list(user_id)

    async def create(self, user_id: uuid.UUID, name: str) -> Folder:
        try:
            folder = await self.folders.add(Folder(user_id=user_id, name=name.strip()))
            await self.s.commit()
        except IntegrityError as e:
            await self.s.rollback()
            raise Conflict("Thư mục đã tồn tại", code="FOLDER_EXISTS") from e
        return folder

    async def rename(self, user_id: uuid.UUID, folder_id: uuid.UUID, name: str) -> Folder:
        folder = await self._get_editable(user_id, folder_id)
        folder.name = name.strip()
        try:
            await self.s.commit()
        except IntegrityError as e:
            await self.s.rollback()
            raise Conflict("Thư mục đã tồn tại", code="FOLDER_EXISTS") from e
        return folder

    async def delete(self, user_id: uuid.UUID, folder_id: uuid.UUID) -> None:
        """Xoá thư mục → chuyển toàn bộ note về Inbox (không mất dữ liệu)."""
        folder = await self._get_editable(user_id, folder_id)
        inbox = await self.folders.get_or_create_inbox(user_id)
        for nid in await self.notes.move_all(user_id, folder.id, inbox.id):
            await publish_note_changed(self.s, nid)  # index giữ bản sao folder_id
        await self.folders.delete(folder)
        await self.s.commit()

    async def _get_editable(self, user_id: uuid.UUID, folder_id: uuid.UUID) -> Folder:
        folder = await self.folders.get(user_id, folder_id)
        if folder is None:
            raise NotFound("Không tìm thấy thư mục", code="FOLDER_NOT_FOUND")
        if folder.is_default:
            raise Conflict("Không sửa/xoá thư mục mặc định", code="FOLDER_IS_DEFAULT")
        return folder
