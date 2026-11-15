"""Presentation Layer — DTO request/response (auth)."""

from typing import Literal

from pydantic import Field

from quickassist.presentation.schemas.common import ApiModel


class AuthConfigOut(ApiModel):
    """GET /auth/config (public) — extension đọc để biết có tự đăng nhập local không (ADR-0016 §4.8).
    KHÔNG trả email/local_auth_email — server tự quyết định, client không cần biết."""

    auth_mode: Literal["google", "local"]


class GoogleExchangeIn(ApiModel):
    code: str = Field(min_length=1, max_length=2048)
    code_verifier: str = Field(min_length=43, max_length=128)  # RFC 7636
    redirect_uri: str = Field(max_length=512)
    nonce: str = Field(min_length=16, max_length=128)


class DevLoginIn(ApiModel):
    email: str = Field(default="dev@quickassist.local", max_length=320)


class RefreshIn(ApiModel):
    refresh_token: str = Field(min_length=20, max_length=256)


class TokenPairOut(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    is_new_user: bool = False
