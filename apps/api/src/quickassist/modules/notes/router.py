import uuid
from datetime import datetime

from fastapi import APIRouter, Header, Query, status
from fastapi.responses import JSONResponse

from quickassist.core.auth_context import CurrentUserId
from quickassist.core.db import DbSession
from quickassist.core.errors import NotFound
from quickassist.core.schemas import Page
from quickassist.modules.notes.schemas import (
    BulkDeleteIn,
    BulkDeleteOut,
    FolderCreateIn,
    FolderOut,
    FolderUpdateIn,
    NoteCreateIn,
    NoteOut,
    NoteSummaryIn,
    NoteUpdateIn,
)
from quickassist.modules.notes.service import FolderService, NoteService

router = APIRouter(tags=["notes"])


# ---------------- Folders ----------------
@router.get("/folders", response_model=list[FolderOut])
async def list_folders(user_id: CurrentUserId, session: DbSession) -> list[FolderOut]:
    return [FolderOut.model_validate(f) for f in await FolderService(session).list_all(user_id)]


@router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(body: FolderCreateIn, user_id: CurrentUserId, session: DbSession) -> FolderOut:
    return FolderOut.model_validate(await FolderService(session).create(user_id, body.name))


@router.patch("/folders/{folder_id}", response_model=FolderOut)
async def rename_folder(
    folder_id: uuid.UUID, body: FolderUpdateIn, user_id: CurrentUserId, session: DbSession
) -> FolderOut:
    return FolderOut.model_validate(await FolderService(session).rename(user_id, folder_id, body.name))


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(folder_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> None:
    await FolderService(session).delete(user_id, folder_id)


# ---------------- Notes ----------------
@router.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED,
             responses={409: {"description": "Idempotency-Key dùng cho request khác"}})
async def create_note(
    body: NoteCreateIn,
    user_id: CurrentUserId,
    session: DbSession,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
) -> JSONResponse:
    code, payload = await NoteService(session).create(user_id, body, idempotency_key)
    return JSONResponse(payload, status_code=code)


@router.get("/notes", response_model=Page[NoteOut])
async def list_notes(
    user_id: CurrentUserId,
    session: DbSession,
    folder_id: uuid.UUID | None = None,
    updated_since: datetime | None = Query(default=None, description="Sync tăng dần; có kèm tombstone"),
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[NoteOut]:
    items, nxt = await NoteService(session).list_page(
        user_id, folder_id=folder_id, updated_since=updated_since, cursor=cursor, limit=limit
    )
    return Page[NoteOut](items=[NoteOut.model_validate(n) for n in items], next_cursor=nxt)


@router.get("/notes/{note_id}", response_model=NoteOut)
async def get_note(note_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> NoteOut:
    return NoteOut.model_validate(await NoteService(session).get(user_id, note_id))


@router.patch("/notes/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: uuid.UUID, body: NoteUpdateIn, user_id: CurrentUserId, session: DbSession
) -> NoteOut:
    return NoteOut.model_validate(await NoteService(session).update(user_id, note_id, body))


@router.put("/notes/{note_id}/summary", response_model=NoteOut)
async def save_summary(
    note_id: uuid.UUID, body: NoteSummaryIn, user_id: CurrentUserId, session: DbSession
) -> NoteOut:
    return NoteOut.model_validate(await NoteService(session).save_summary(user_id, note_id, body))


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> None:
    if await NoteService(session).delete_many(user_id, [note_id]) == 0:
        raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")


@router.post("/notes/bulk-delete", response_model=BulkDeleteOut)
async def bulk_delete(body: BulkDeleteIn, user_id: CurrentUserId, session: DbSession) -> BulkDeleteOut:
    return BulkDeleteOut(deleted=await NoteService(session).delete_many(user_id, body.ids))


@router.post("/notes/{note_id}/reindex", response_model=NoteOut, status_code=status.HTTP_202_ACCEPTED)
async def reindex_note(note_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> NoteOut:
    return NoteOut.model_validate(await NoteService(session).reindex(user_id, note_id))
