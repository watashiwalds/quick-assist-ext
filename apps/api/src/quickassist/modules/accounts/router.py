from fastapi import APIRouter, status

from quickassist.core.auth_context import CurrentUserId
from quickassist.core.db import DbSession
from quickassist.modules.accounts.schemas import UserOut
from quickassist.modules.accounts.service import AccountService

router = APIRouter(prefix="/me", tags=["accounts"])


@router.get("", response_model=UserOut)
async def get_me(user_id: CurrentUserId, session: DbSession) -> UserOut:
    return UserOut.model_validate(await AccountService(session).get_profile(user_id))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user_id: CurrentUserId, session: DbSession) -> None:
    """Xoá tài khoản và TOÀN BỘ dữ liệu liên quan (không khôi phục được)."""
    await AccountService(session).delete_account(user_id)
