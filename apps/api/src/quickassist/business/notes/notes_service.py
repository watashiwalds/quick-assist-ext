"""Business Layer — NotesService (SDS Hình 1, §5.2): tạo/xem/sửa/xoá ghi chú, idempotency,
điều phối trạng thái xử lý AI (PROCESSING → READY/SKIPPED/FAILED).
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import AppError, Conflict, NotFound, PayloadTooLarge
from quickassist.business.common.idempotency import IdempotencyGuard, hash_request
from quickassist.business.notes.indexing_events import publish_note_changed
from quickassist.data.models.note import Folder, Note
from quickassist.data_access.repositories.folder_repository import FolderRepository
from quickassist.data_access.repositories.note_repository import NoteRepository
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class CreateNoteCommand:
    content: str
    url: str | None = None
    title: str | None = None
    folder_id: uuid.UUID | None = None


@dataclass(frozen=True)
class UpdateNoteCommand:
    version: int
    content: str | None = None
    title: str | None = None
    folder_id: uuid.UUID | None = None


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "").strip()
    limit = get_settings().max_note_chars
    if len(text) > limit:
        raise PayloadTooLarge(f"Nội dung vượt {limit} ký tự", code="NOTE_TOO_LONG")
    return text


def _encode_cursor(n: Note) -> str:
    return base64.urlsafe_b64encode(f"{n.updated_at.isoformat()}|{n.id}".encode()).decode()


def _decode_cursor(c: str) -> tuple[datetime, uuid.UUID]:
    try:
        ts, nid = base64.urlsafe_b64decode(c.encode()).decode().split("|")
        return datetime.fromisoformat(ts), uuid.UUID(nid)
    except Exception as e:
        raise AppError("Cursor không hợp lệ", code="CURSOR_INVALID") from e


def _check_version(note: Note, version: int) -> None:
    if note.version != version:
        raise Conflict("Ghi chú đã bị sửa ở nơi khác", code="NOTE_VERSION_CONFLICT",
                       details={"current_version": note.version})


class NotesService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session
        self.folders = FolderRepository(session)
        self.notes = NoteRepository(session)

    async def _resolve_folder(self, user_id: uuid.UUID, folder_id: uuid.UUID | None) -> Folder:
        if folder_id is None:
            return await self.folders.get_or_create_inbox(user_id)
        folder = await self.folders.get(user_id, folder_id)
        if folder is None:
            raise NotFound("Không tìm thấy thư mục", code="FOLDER_NOT_FOUND")
        return folder

    async def create(self, user_id: uuid.UUID, cmd: CreateNoteCommand, idempotency_key: str | None) -> Note:
        guard = None
        if idempotency_key:
            guard = IdempotencyGuard(self.s, user_id, idempotency_key, "notes.create",
                                     hash_request(cmd.__dict__))
            if (existing := await guard.existing_resource()) is not None:
                return await self.get(user_id, existing)

        folder = await self._resolve_folder(user_id, cmd.folder_id)
        note = await self.notes.add(Note(
            user_id=user_id, folder_id=folder.id, url=cmd.url,
            domain=urlparse(cmd.url).hostname if cmd.url else None,
            title=(cmd.title or "").strip() or None,
            content=_clean_text(cmd.content),
            index_status="PROCESSING",
        ))
        await publish_note_changed(self.s, note.id)  # cùng transaction với note
        if guard and not await guard.remember(note.id):
            await self.s.rollback()  # request song song cùng key đã thắng → trả bản của nó
            existing = await guard.existing_resource()
            assert existing is not None
            return await self.get(user_id, existing)
        await self.s.commit()
        log.info("note_created", extra={"note_id": str(note.id), "chars": len(note.content)})
        return note

    async def get(self, user_id: uuid.UUID, note_id: uuid.UUID) -> Note:
        note = await self.notes.get(user_id, note_id)
        if note is None:
            raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")
        return note

    async def list_page(
        self, user_id: uuid.UUID, *, folder_id: uuid.UUID | None, updated_since: datetime | None,
        cursor: str | None, limit: int,
    ) -> tuple[list[Note], str | None]:
        # Sync tăng dần (có updated_since) cần cả tombstone để client xoá bản local.
        rows = await self.notes.list_page(
            user_id, folder_id=folder_id, updated_since=updated_since,
            after=_decode_cursor(cursor) if cursor else None, limit=limit + 1,
            include_deleted=updated_since is not None,
        )
        next_cursor = _encode_cursor(rows[limit - 1]) if len(rows) > limit else None
        return rows[:limit], next_cursor

    async def update(self, user_id: uuid.UUID, note_id: uuid.UUID, cmd: UpdateNoteCommand) -> Note:
        note = await self.notes.get(user_id, note_id, for_update=True)
        if note is None:
            raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")
        _check_version(note, cmd.version)
        reindex = False
        if cmd.content is not None:
            new_content = _clean_text(cmd.content)
            if new_content != note.content:
                note.content, note.index_status, reindex = new_content, "PROCESSING", True
        if cmd.title is not None:
            note.title = cmd.title.strip() or None
        if cmd.folder_id is not None and cmd.folder_id != note.folder_id:
            note.folder_id = (await self._resolve_folder(user_id, cmd.folder_id)).id
            reindex = True  # cập nhật folder_id trong index để lọc theo thư mục
        note.version += 1
        if reindex:
            note.index_rev += 1
            await publish_note_changed(self.s, note.id)
        await self.s.commit()
        await self.s.refresh(note)
        return note

    async def save_summary(self, user_id: uuid.UUID, note_id: uuid.UUID, *, version: int,
                           summary_text: str) -> Note:
        """Lưu bản tóm tắt người dùng đã XÁC NHẬN (SDS §5.1.4)."""
        note = await self.notes.get(user_id, note_id, for_update=True)
        if note is None:
            raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")
        _check_version(note, version)
        note.summary_text, note.version = summary_text.strip(), note.version + 1
        await self.s.commit()
        await self.s.refresh(note)
        return note

    async def delete_many(self, user_id: uuid.UUID, ids: list[uuid.UUID]) -> int:
        deleted = await self.notes.soft_delete_many(user_id, list(dict.fromkeys(ids)))
        for nid in deleted:
            await publish_note_changed(self.s, nid)  # semantic_search xoá chunk
        await self.s.commit()
        return len(deleted)

    async def reindex(self, user_id: uuid.UUID, note_id: uuid.UUID) -> Note:
        """Người dùng bấm 'Thử lại' với note FAILED/SKIPPED."""
        note = await self.get(user_id, note_id)
        note.index_status, note.index_error = "PROCESSING", None
        note.index_rev += 1
        await publish_note_changed(self.s, note.id)
        await self.s.commit()
        return note
