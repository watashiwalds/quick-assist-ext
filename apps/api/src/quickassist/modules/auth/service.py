"""Đăng nhập Google → phát app session; refresh xoay vòng; logout.

Phát hiện tái sử dụng refresh token: nếu token đã bị xoay/revoke mà vẫn được
gửi lên → khả năng bị đánh cắp → revoke mọi session của user.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.core.config import get_settings
from quickassist.core.errors import Forbidden, Unauthorized
from quickassist.core.logging import get_logger
from quickassist.core.security import create_access_token, hash_token, new_refresh_token
from quickassist.modules.accounts.public import AccountService
from quickassist.modules.auth.models import AuthSession
from quickassist.modules.auth.repository import AuthSessionRepository
from quickassist.modules.auth.schemas import TokenPairOut
from quickassist.providers.google.oidc import GoogleOIDCClient

log = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session
        self.sessions = AuthSessionRepository(session)
        self.accounts = AccountService(session)

    async def _issue(self, user_id: uuid.UUID, user_agent: str | None, is_new: bool) -> TokenPairOut:
        refresh = new_refresh_token()
        row = await self.sessions.add(AuthSession(
            user_id=user_id,
            refresh_token_hash=hash_token(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_ttl_days),
            user_agent=(user_agent or "")[:255] or None,
        ))
        access, ttl = create_access_token(user_id, row.id)
        return TokenPairOut(access_token=access, refresh_token=refresh, expires_in=ttl,
                            is_new_user=is_new)

    async def login_with_google(
        self, oidc: GoogleOIDCClient, *, code: str, code_verifier: str, redirect_uri: str,
        nonce: str, user_agent: str | None,
    ) -> TokenPairOut:
        id_token = await oidc.exchange_code(code=code, code_verifier=code_verifier,
                                           redirect_uri=redirect_uri)
        ident = await asyncio.to_thread(oidc.verify_id_token, id_token, nonce=nonce)  # JWKS fetch
        user, is_new = await self.accounts.upsert_google_user(
            sub=ident.sub, email=ident.email, name=ident.name, picture=ident.picture
        )
        pair = await self._issue(user.id, user_agent, is_new)
        await self.s.commit()
        log.info("login_success", extra={"user_id": str(user.id), "new_user": is_new})
        return pair

    async def dev_login(self, email: str, user_agent: str | None) -> TokenPairOut:
        if not get_settings().is_dev_login_allowed:
            raise Forbidden("Dev login bị tắt", code="DEV_LOGIN_DISABLED")
        user, is_new = await self.accounts.upsert_google_user(
            sub=f"dev:{email}", email=email, name="Dev User", picture=None
        )
        pair = await self._issue(user.id, user_agent, is_new)
        await self.s.commit()
        return pair

    async def refresh(self, refresh_token: str, user_agent: str | None) -> TokenPairOut:
        row = await self.sessions.get_by_hash_for_update(hash_token(refresh_token))
        now = datetime.now(UTC)
        if row is None:
            raise Unauthorized("Refresh token không hợp lệ", code="REFRESH_INVALID")
        if row.revoked_at is not None:
            await self.sessions.revoke_all_for_user(row.user_id)
            await self.s.commit()
            log.warning("refresh_token_reuse", extra={"user_id": str(row.user_id)})
            raise Unauthorized("Phiên đã bị thu hồi, vui lòng đăng nhập lại", code="REFRESH_REUSED")
        if row.expires_at <= now:
            raise Unauthorized("Phiên đăng nhập đã hết hạn", code="REFRESH_EXPIRED")
        pair = await self._issue(row.user_id, user_agent, False)
        row.revoked_at = now
        await self.s.commit()
        return pair

    async def logout(self, refresh_token: str) -> None:
        row = await self.sessions.get_by_hash_for_update(hash_token(refresh_token))
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
        await self.s.commit()
