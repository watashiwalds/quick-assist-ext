"""Business Layer — quản lý tài khoản QuickAssist (thuộc Google OAuth Service, SDS §4.3).

"Xử lý đăng nhập Google, xác minh thông tin người dùng và tạo hoặc khôi phục tài khoản."
Xoá tài khoản (SDS §5.1.5) cũng đặt ở đây vì service này SỞ HỮU bảng users.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import NotFound
from quickassist.data.models.user import User
from quickassist.data_access.repositories.user_repository import UserRepository
from quickassist.infrastructure.logging import get_logger

log = get_logger(__name__)


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session
        self.users = UserRepository(session)

    async def upsert_google_user(
        self, *, sub: str, email: str, name: str | None, picture: str | None
    ) -> tuple[User, bool]:
        user = await self.users.get_by_google_sub(sub)
        if user:
            user.email, user.display_name, user.avatar_url = email, name, picture
            await self.users.touch(user.id)
            return user, False
        user = await self.users.add(User(google_sub=sub, email=email, display_name=name, avatar_url=picture))
        log.info("user_created", extra={"user_id": str(user.id)})
        return user, True

    async def get_profile(self, user_id: uuid.UUID) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFound("Không tìm thấy tài khoản", code="USER_NOT_FOUND")
        return user

    async def delete_account(self, user_id: uuid.UUID) -> None:
        """SDS §5.1.5 — MỘT transaction; FK ON DELETE CASCADE dọn sessions, folders, notes,
        chunks/vectors, quota. Lỗi giữa chừng → rollback toàn bộ."""
        try:
            if await self.users.delete(user_id) == 0:
                raise NotFound("Không tìm thấy tài khoản", code="USER_NOT_FOUND")
            await self.s.commit()
        except Exception:
            await self.s.rollback()
            raise
        log.info("account_deleted", extra={"user_id": str(user_id)})
