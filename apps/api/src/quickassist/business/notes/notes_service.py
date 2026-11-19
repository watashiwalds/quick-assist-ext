"""Business Layer — NotesService (SDS Hình 1, §5.2): tạo/xem/sửa/xoá ghi chú, idempotency,
điều phối trạng thái xử lý AI (PROCESSING → READY/SKIPPED/FAILED).
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import (
    AppError,
    Conflict,
    NotFound,
    PayloadTooLarge,
    Unprocessable,
)
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
    content: str | None = None
    url: str | None = None
    title: str | None = None
    folder_id: uuid.UUID | None = None
    # D2 — đường tạo tài liệu dài: nhiều part ≤ MAX_NOTE_CHARS, cùng document_id client sinh.
    document_id: uuid.UUID | None = None
    parts: tuple[str, ...] | None = None


@dataclass(frozen=True)
class UpdateNoteCommand:
    version: int
    content: str | None = None
    title: str | None = None
    url: str | None = None
    folder_id: uuid.UUID | None = None


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "").strip()
    limit = get_settings().max_note_chars
    if len(text) > limit:
        raise PayloadTooLarge(f"Nội dung vượt {limit} ký tự", code="NOTE_TOO_LONG")
    return text


def _clean_parts(parts: tuple[str, ...]) -> list[str]:
    """Chuẩn hoá từng part; part rỗng sau khi bỏ NUL/khoảng trắng → 422 chỉ rõ vị trí."""
    cleaned: list[str] = []
    for index, part in enumerate(parts):
        text = _clean_text(part)
        if not text:
            raise Unprocessable(
                "Phần nội dung không được để trống",
                code="NOTE_PART_EMPTY",
                details={"part_index": index},
            )
        cleaned.append(text)
    return cleaned


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

        # Idempotent theo document_id: kiểm tra TRƯỚC khi resolve folder để retry vẫn trả bản
        # đã tạo kể cả khi thư mục đích đã bị xoá ở máy khác.
        if cmd.parts is not None:
            assert cmd.document_id is not None
            existing = await self._existing_document(user_id, cmd.document_id, len(cmd.parts))
            if existing is not None:
                return existing
        elif cmd.document_id is not None:
            if (existing := await self._existing_document(
                user_id, cmd.document_id, part_count=1
            )) is not None:
                return existing

        folder = await self._resolve_folder(user_id, cmd.folder_id)
        if cmd.parts is not None:
            return await self._create_document(user_id, cmd, folder, guard)

        # Đường cũ: một note. Nếu client gắn document_id thì đây là tài liệu một part.
        content = _clean_text(cmd.content or "")
        document_id = cmd.document_id
        try:
            note = await self.notes.add(Note(
                user_id=user_id, folder_id=folder.id, url=cmd.url,
                domain=urlparse(cmd.url).hostname if cmd.url else None,
                title=(cmd.title or "").strip() or None,
                content=content,
                document_id=document_id,
                original_chars=len(content) if document_id else None,
                source_type="document" if document_id else "selection",
                index_status="PROCESSING",
            ))
        except IntegrityError:
            if document_id is None:
                raise
            await self.s.rollback()  # retry song song cùng document_id → trả bản đã thắng
            existing = await self._existing_document(user_id, document_id, part_count=1)
            if existing is None:
                raise
            return existing
        await publish_note_changed(self.s, note.id)  # cùng transaction với note
        if guard and not await guard.remember(note.id):
            await self.s.rollback()  # request song song cùng key đã thắng → trả bản của nó
            existing = await guard.existing_resource()
            assert existing is not None
            return await self.get(user_id, existing)
        await self.s.commit()
        log.info("note_created", extra={"note_id": str(note.id), "chars": len(note.content)})
        return note

    async def _create_document(
        self, user_id: uuid.UUID, cmd: CreateNoteCommand, folder: Folder,
        guard: IdempotencyGuard | None,
    ) -> Note:
        """Tạo toàn bộ part của một tài liệu trong MỘT transaction (D2)."""
        assert cmd.parts is not None and cmd.document_id is not None
        cleaned = _clean_parts(cmd.parts)
        part_count = len(cleaned)
        original_chars = sum(map(len, cleaned))
        existing = await self._existing_document(user_id, cmd.document_id, part_count)
        if existing is not None:
            return existing

        title = (cmd.title or "").strip() or None
        domain = urlparse(cmd.url).hostname if cmd.url else None
        notes = [
            Note(
                user_id=user_id, folder_id=folder.id, url=cmd.url, domain=domain, title=title,
                content=text, index_status="PROCESSING", document_id=cmd.document_id,
                part_index=index, part_count=part_count, original_chars=original_chars,
                source_type="document",
            )
            for index, text in enumerate(cleaned)
        ]
        try:
            await self.notes.add_many(notes)
        except IntegrityError:
            # Retry song song cùng document_id: bản kia đã thắng → trả part 0 của bản đó.
            await self.s.rollback()
            existing = await self._existing_document(user_id, cmd.document_id, part_count)
            if existing is not None:
                return existing
            raise
        for note in notes:
            await publish_note_changed(self.s, note.id)
        if guard and not await guard.remember(notes[0].id):
            await self.s.rollback()
            existing_id = await guard.existing_resource()
            assert existing_id is not None
            return await self.get(user_id, existing_id)
        await self.s.commit()
        await self.s.refresh(notes[0])
        log.info("document_created", extra={
            "document_id": str(cmd.document_id), "parts": part_count, "chars": original_chars})
        return notes[0]

    async def _existing_document(
        self, user_id: uuid.UUID, document_id: uuid.UUID, part_count: int,
    ) -> Note | None:
        """Idempotent theo document_id: trả part 0 nếu đã có đúng số part; lệch → 409."""
        parts = await self.notes.list_document_parts(user_id, document_id, include_deleted=True)
        if not parts:
            return None
        if any(p.deleted_at is not None for p in parts):
            raise Conflict(
                "document_id đã được dùng bởi tài liệu đã xoá",
                code="DOCUMENT_ID_CONFLICT",
            )
        if parts[0].part_count != part_count:
            raise Conflict(
                "document_id đã tồn tại với số phần khác",
                code="DOCUMENT_ID_CONFLICT",
                details={"existing_part_count": parts[0].part_count, "part_count": part_count},
            )
        return parts[0]

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

    async def list_document_parts(self, user_id: uuid.UUID, document_id: uuid.UUID) -> list[Note]:
        """Các part của tài liệu, theo part_index; tài liệu không tồn tại → danh sách rỗng."""
        return await self.notes.list_document_parts(user_id, document_id)

    async def update(self, user_id: uuid.UUID, note_id: uuid.UUID, cmd: UpdateNoteCommand) -> Note:
        note = await self.notes.get(user_id, note_id, for_update=True)
        if note is None:
            raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")
        _check_version(note, cmd.version)
        # Metadata (title/url/folder) thuộc DOCUMENT: sửa một part → lan sang mọi part cùng document.
        parts = [note]
        if note.document_id is not None:
            parts = await self.notes.list_document_parts(user_id, note.document_id, for_update=True)

        content_changed = False
        if cmd.content is not None:
            new_content = _clean_text(cmd.content)
            if new_content != note.content:
                note.content, note.index_status = new_content, "PROCESSING"
                content_changed = True

        meta_changed = False
        if cmd.title is not None:
            new_title = cmd.title.strip() or None
            if any(p.title != new_title for p in parts):
                for p in parts:
                    p.title = new_title
                meta_changed = True
        if cmd.url is not None:  # None = không đổi; hiện chưa hỗ trợ xoá URL
            new_domain = urlparse(cmd.url).hostname if cmd.url else None
            if any(p.url != cmd.url or p.domain != new_domain for p in parts):
                for p in parts:
                    p.url, p.domain = cmd.url, new_domain
                meta_changed = True

        folder_changed = False
        if cmd.folder_id is not None:
            target_folder = (await self._resolve_folder(user_id, cmd.folder_id)).id
            if any(p.folder_id != target_folder for p in parts):
                for p in parts:
                    p.folder_id = target_folder
                folder_changed = True

        for p in parts:
            if p.id == note.id or meta_changed or folder_changed:
                p.version += 1

        reindex_ids: set[uuid.UUID] = set()
        if content_changed:
            reindex_ids.add(note.id)
        if folder_changed:  # cập nhật folder_id trong index để lọc theo thư mục
            reindex_ids.update(p.id for p in parts)
        for p in parts:
            if p.id in reindex_ids:
                p.index_rev += 1
                await publish_note_changed(self.s, p.id)
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

    async def move_many(
        self, user_id: uuid.UUID, ids: list[uuid.UUID], folder_id: uuid.UUID | None,
    ) -> tuple[int, list[uuid.UUID]]:
        """Chuyển các ghi chú ĐÃ CHỌN sang thư mục đích (None → Inbox).

        Chỉ note của chính user và chưa xoá mới được cập nhật; id lạ/không sở hữu trả ở
        ``missing``. Ghi ``folder_id`` + enqueue job index trong CÙNG transaction với note
        (outbox ADR-0003) → nếu commit lỗi cả hai cùng rollback; job cập nhật
        ``NoteChunk.folder_id`` (business của semantic_search sở hữu bảng chunk).
        """
        folder = await self._resolve_folder(user_id, folder_id)
        unique = list(dict.fromkeys(ids))
        moved = await self.notes.move_many(user_id, unique, folder.id)
        for nid in moved:
            await publish_note_changed(self.s, nid)
        await self.s.commit()
        moved_set = set(moved)
        return len(moved), [nid for nid in unique if nid not in moved_set]

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
        await self.s.refresh(note)
        return note
