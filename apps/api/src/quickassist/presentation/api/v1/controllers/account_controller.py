"""API Controller — tài khoản: xem hồ sơ, xoá tài khoản + toàn bộ dữ liệu (SDS §5.1.5)."""

from fastapi import APIRouter, status

from quickassist.business.auth import AccountService
from quickassist.presentation.api.deps import CurrentUserId, DbSession
from quickassist.presentation.schemas.account import UserOut

router = APIRouter(prefix="/me", tags=["account"])


@router.get("", response_model=UserOut)
async def get_me(user_id: CurrentUserId, session: DbSession) -> UserOut:
    return UserOut.model_validate(await AccountService(session).get_profile(user_id))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user_id: CurrentUserId, session: DbSession) -> None:
    """Xoá tài khoản và TOÀN BỘ dữ liệu liên quan (không khôi phục được)."""
    await AccountService(session).delete_account(user_id)
