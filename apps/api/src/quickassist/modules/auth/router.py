from functools import lru_cache

from fastapi import APIRouter, Request, status

from quickassist.core.config import get_settings
from quickassist.core.db import DbSession
from quickassist.modules.auth.schemas import DevLoginIn, GoogleExchangeIn, RefreshIn, TokenPairOut
from quickassist.modules.auth.service import AuthService
from quickassist.providers.google.oidc import GoogleOIDCClient

router = APIRouter(prefix="/auth", tags=["auth"])


@lru_cache
def _oidc() -> GoogleOIDCClient:
    return GoogleOIDCClient(get_settings())


@router.post("/google/exchange", response_model=TokenPairOut)
async def google_exchange(body: GoogleExchangeIn, request: Request, session: DbSession) -> TokenPairOut:
    return await AuthService(session).login_with_google(
        _oidc(), code=body.code, code_verifier=body.code_verifier,
        redirect_uri=body.redirect_uri, nonce=body.nonce,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh", response_model=TokenPairOut)
async def refresh(body: RefreshIn, request: Request, session: DbSession) -> TokenPairOut:
    return await AuthService(session).refresh(body.refresh_token, request.headers.get("user-agent"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshIn, session: DbSession) -> None:
    await AuthService(session).logout(body.refresh_token)


@router.post("/dev-login", response_model=TokenPairOut, include_in_schema=False)
async def dev_login(body: DevLoginIn, request: Request, session: DbSession) -> TokenPairOut:
    """Chỉ hoạt động khi APP_ENV=dev|test và ENABLE_DEV_LOGIN=true."""
    return await AuthService(session).dev_login(body.email, request.headers.get("user-agent"))
