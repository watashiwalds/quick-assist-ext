"""API Controller — thư mục ghi chú (Inbox mặc định)."""

import uuid

from fastapi import APIRouter, status

from quickassist.business.notes import FolderService
from quickassist.presentation.api.deps import CurrentUserId, DbSession
from quickassist.presentation.schemas.notes import FolderCreateIn, FolderOut, FolderUpdateIn

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("", response_model=list[FolderOut])
async def list_folders(user_id: CurrentUserId, session: DbSession) -> list[FolderOut]:
    return [FolderOut.model_validate(f) for f in await FolderService(session).list_all(user_id)]


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(body: FolderCreateIn, user_id: CurrentUserId, session: DbSession) -> FolderOut:
    return FolderOut.model_validate(await FolderService(session).create(user_id, body.name))


@router.patch("/{folder_id}", response_model=FolderOut)
async def rename_folder(folder_id: uuid.UUID, body: FolderUpdateIn, user_id: CurrentUserId,
                        session: DbSession) -> FolderOut:
    return FolderOut.model_validate(await FolderService(session).rename(user_id, folder_id, body.name))


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(folder_id: uuid.UUID, user_id: CurrentUserId, session: DbSession) -> None:
    await FolderService(session).delete(user_id, folder_id)
