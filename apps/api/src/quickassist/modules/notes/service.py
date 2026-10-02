"""Nghiệp vụ ghi chú & thư mục — MODULE MẪU (reference slice).

Các module khác làm theo đúng khuôn này:
  router (HTTP) → service (nghiệp vụ, transaction, phát job) → repository (SQL)
"""

import base64
import uuid
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.core import idempotency
from quickassist.core.config import get_settings
from quickassist.core.errors import AppError, Conflict, NotFound, PayloadTooLarge
from quickassist.core.job_kinds import SEARCH_INDEX_NOTE
from quickassist.core.jobs import enqueue
from quickassist.core.logging import get_logger
from quickassist.modules.notes.models import Folder, Note
from quickassist.modules.notes.repository import FolderRepository, NoteRepository
from quickassist.modules.notes.schemas import (
    FolderOut,
    NoteCreateIn,
    NoteOut,
    NoteSummaryIn,
    NoteUpdateIn,
)

log = get_logger(__name__)


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "").strip()
    if len(text) > get_settings().max_note_chars:
        raise PayloadTooLarge(
            f"Nội dung vượt {get_settings().max_note_chars} ký tự", code="NOTE_TOO_LONG"
        )
    return text


def encode_cursor(n: Note) -> str:
    return base64.urlsafe_b64encode(f"{n.updated_at.isoformat()}|{n.id}".encode()).decode()


def decode_cursor(c: str) -> tuple[datetime, uuid.UUID]:
    try:
        ts, nid = base64.urlsafe_b64decode(c.encode()).decode().split("|")
        return datetime.fromisoformat(ts), uuid.UUID(nid)
    except Exception as e:
        raise AppError("Cursor không hợp lệ", code="CURSOR_INVALID") from e


async def _enqueue_index(session: AsyncSession, note_id: uuid.UUID) -> None:
    await enqueue(session, SEARCH_INDEX_NOTE, {"note_id": str(note_id)},
                  dedupe_key=f"{SEARCH_INDEX_NOTE}:{note_id}")


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
        folder = await self.folders.get(user_id, folder_id)
        if folder is None:
            raise NotFound("Không tìm thấy thư mục", code="FOLDER_NOT_FOUND")
        if folder.is_default:
            raise Conflict("Không đổi tên thư mục mặc định", code="FOLDER_IS_DEFAULT")
        folder.name = name.strip()
        try:
            await self.s.commit()
        except IntegrityError as e:
            await self.s.rollback()
            raise Conflict("Thư mục đã tồn tại", code="FOLDER_EXISTS") from e
        return folder

    async def delete(self, user_id: uuid.UUID, folder_id: uuid.UUID) -> None:
        """Xoá thư mục → chuyển toàn bộ note về Inbox (không mất dữ liệu)."""
        folder = await self.folders.get(user_id, folder_id)
        if folder is None:
            raise NotFound("Không tìm thấy thư mục", code="FOLDER_NOT_FOUND")
        if folder.is_default:
            raise Conflict("Không xoá thư mục mặc định", code="FOLDER_IS_DEFAULT")
        inbox = await self.folders.get_or_create_inbox(user_id)
        moved = await self.notes.move_all(user_id, folder.id, inbox.id)
        for nid in moved:  # search giữ bản sao folder_id → cần cập nhật
            await _enqueue_index(self.s, nid)
        await self.folders.delete(folder)
        await self.s.commit()


class NoteService:
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

    async def create(
        self, user_id: uuid.UUID, data: NoteCreateIn, idempotency_key: str | None
    ) -> tuple[int, dict]:
        """Trả (status_code, body) để router trả nguyên văn — kể cả khi replay idempotent."""
        scope = "notes.create"
        req_hash = idempotency.hash_request(data.model_dump(mode="json"))
        if idempotency_key:
            cached = await idempotency.lookup(self.s, user_id, idempotency_key, scope, req_hash)
            if cached:
                return cached

        folder = await self._resolve_folder(user_id, data.folder_id)
        url = str(data.url) if data.url else None
        note = await self.notes.add(Note(
            user_id=user_id, folder_id=folder.id, url=url,
            domain=urlparse(url).hostname if url else None,
            title=(data.title or "").strip() or None,
            content=_clean_text(data.content),
            index_status="PROCESSING",
        ))
        # Outbox: job index nằm CÙNG transaction với note → không bao giờ có note "mồ côi".
        await _enqueue_index(self.s, note.id)
        body = NoteOut.model_validate(note).model_dump(mode="json")
        if idempotency_key and not await idempotency.remember(
            self.s, user_id, idempotency_key, scope, req_hash, 201, body
        ):
            # Request song song cùng key đã thắng → huỷ bản của mình, trả bản đã lưu.
            await self.s.rollback()
            cached = await idempotency.lookup(self.s, user_id, idempotency_key, scope, req_hash)
            assert cached is not None
            return cached
        await self.s.commit()
        log.info("note_created", extra={"note_id": str(note.id), "chars": len(note.content)})
        return 201, body

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
            after=decode_cursor(cursor) if cursor else None, limit=limit + 1,
            include_deleted=updated_since is not None,
        )
        next_cursor = encode_cursor(rows[limit - 1]) if len(rows) > limit else None
        return rows[:limit], next_cursor

    async def update(self, user_id: uuid.UUID, note_id: uuid.UUID, data: NoteUpdateIn) -> Note:
        note = await self.notes.get(user_id, note_id, for_update=True)
        if note is None:
            raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")
        if note.version != data.version:
            raise Conflict("Ghi chú đã bị sửa ở nơi khác", code="NOTE_VERSION_CONFLICT",
                           details={"current_version": note.version})
        reindex = False
        if data.content is not None:
            new_content = _clean_text(data.content)
            if new_content != note.content:
                note.content, note.index_status, reindex = new_content, "PROCESSING", True
        if data.title is not None:
            note.title = data.title.strip() or None
        if data.folder_id is not None and data.folder_id != note.folder_id:
            note.folder_id = (await self._resolve_folder(user_id, data.folder_id)).id
            reindex = True  # cập nhật folder_id trong index để lọc theo thư mục
        note.version += 1
        if reindex:
            note.index_rev += 1
            await _enqueue_index(self.s, note.id)
        await self.s.commit()
        await self.s.refresh(note)
        return note

    async def save_summary(self, user_id: uuid.UUID, note_id: uuid.UUID, data: NoteSummaryIn) -> Note:
        note = await self.notes.get(user_id, note_id, for_update=True)
        if note is None:
            raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")
        if note.version != data.version:
            raise Conflict("Ghi chú đã bị sửa ở nơi khác", code="NOTE_VERSION_CONFLICT",
                           details={"current_version": note.version})
        note.summary_text, note.version = data.summary_text.strip(), note.version + 1
        await self.s.commit()
        await self.s.refresh(note)
        return note

    async def delete_many(self, user_id: uuid.UUID, ids: list[uuid.UUID]) -> int:
        deleted = await self.notes.soft_delete_many(user_id, list(dict.fromkeys(ids)))
        for nid in deleted:
            await _enqueue_index(self.s, nid)  # search xoá chunk của note đã xoá
        await self.s.commit()
        return len(deleted)

    async def reindex(self, user_id: uuid.UUID, note_id: uuid.UUID) -> Note:
        """Người dùng bấm 'Thử lại' với note FAILED/SKIPPED."""
        note = await self.get(user_id, note_id)
        note.index_status, note.index_error = "PROCESSING", None
        note.index_rev += 1
        await _enqueue_index(self.s, note.id)
        await self.s.commit()
        return note


def folder_out(f: Folder) -> FolderOut:
    return FolderOut.model_validate(f)
