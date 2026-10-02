"""API Controller — ghi chú: tạo (idempotent), liệt kê/sync, xem, sửa, xoá, lưu tóm tắt, index lại."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Header, Query, status

from quickassist.business.common.exceptions import NotFound
from quickassist.business.notes import CreateNoteCommand, NotesService, UpdateNoteCommand
from quickassist.presentation.api.deps import CurrentUserId, DbSession
from quickassist.presentation.schemas.common import Page
from quickassist.presentation.schemas.notes import (
    BulkDeleteIn,
    BulkDeleteOut,
    NoteCreateIn,
    NoteOut,
    NoteSummaryIn,
    NoteUpdateIn,
)

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED,
             responses={409: {"description": "Idempotency-Key đã dùng cho request khác"}})
async def create_note(
    body: NoteCreateIn, user_id: CurrentUserId, session: DbSession,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
) -> NoteOut:
    cmd = CreateNoteCommand(content=body.content, url=str(body.url) if body.url else None,
                            title=body.title, folder_id=body.folder_id)
    return NoteOut.model_validate(await NotesService(session).create(user_id, cmd, idempotency_key))


@router.get("", response_model=Page[NoteOut])
async def list_notes(
    user_id: CurrentUserId, session: DbSession,
    folder_id: uuid.UUID | None = None,
    updated_since: datetime | None = Query(default=None, description="Sync tăng dần; có kèm tombstone"),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[NoteOut]:
    items, nxt = await NotesService(session).list_page(
        user_id, folder_id=folder_id, updated_since=updated_since, cursor=cursor, limit=limit)
    return Page[NoteOut](items=[NoteOut.model_validate(n) for n in items], next_cursor=nxt)


@router.get("/{note_id}", response_model=NoteOut)
async def get_note(note_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> NoteOut:
    return NoteOut.model_validate(await NotesService(session).get(user_id, note_id))


@router.patch("/{note_id}", response_model=NoteOut)
async def update_note(note_id: uuid.UUID, body: NoteUpdateIn, user_id: CurrentUserId,
                      session: DbSession) -> NoteOut:
    cmd = UpdateNoteCommand(version=body.version, content=body.content, title=body.title,
                            folder_id=body.folder_id)
    return NoteOut.model_validate(await NotesService(session).update(user_id, note_id, cmd))


@router.put("/{note_id}/summary", response_model=NoteOut)
async def save_summary(note_id: uuid.UUID, body: NoteSummaryIn, user_id: CurrentUserId,
                       session: DbSession) -> NoteOut:
    return NoteOut.model_validate(await NotesService(session).save_summary(
        user_id, note_id, version=body.version, summary_text=body.summary_text))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> None:
    if await NotesService(session).delete_many(user_id, [note_id]) == 0:
        raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")


@router.post("/bulk-delete", response_model=BulkDeleteOut)
async def bulk_delete(body: BulkDeleteIn, user_id: CurrentUserId, session: DbSession) -> BulkDeleteOut:
    return BulkDeleteOut(deleted=await NotesService(session).delete_many(user_id, body.ids))


@router.post("/{note_id}/reindex", response_model=NoteOut, status_code=status.HTTP_202_ACCEPTED)
async def reindex_note(note_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> NoteOut:
    return NoteOut.model_validate(await NotesService(session).reindex(user_id, note_id))
