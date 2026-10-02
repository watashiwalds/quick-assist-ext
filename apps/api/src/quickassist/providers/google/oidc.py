"""Adapter Google OAuth 2.0 / OpenID Connect (ADR-0005).

Luồng: extension chạy chrome.identity.launchWebAuthFlow với PKCE → nhận `code`
→ gửi {code, code_verifier, redirect_uri, nonce} lên server → server đổi code lấy
id_token (dùng client_secret chỉ server giữ) → xác minh chữ ký JWKS, iss, aud,
exp, nonce, email_verified.
"""

from dataclasses import dataclass

import httpx
import jwt
from jwt import PyJWKClient

from quickassist.core.config import Settings
from quickassist.core.errors import Unauthorized, UpstreamError

TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


class GoogleOIDCClient:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._jwks = PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)

    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> str:
        if redirect_uri not in self._s.oauth_allowed_redirect_uris:
            raise Unauthorized("redirect_uri không được phép", code="OAUTH_REDIRECT_INVALID")
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.post(TOKEN_URL, data={
                    "code": code,
                    "code_verifier": code_verifier,
                    "client_id": self._s.google_client_id,
                    "client_secret": self._s.google_client_secret.get_secret_value(),
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                })
            except httpx.HTTPError as e:
                raise UpstreamError("Không kết nối được Google", code="OAUTH_UPSTREAM") from e
        if r.status_code != 200:
            raise Unauthorized("Mã đăng nhập không hợp lệ hoặc đã hết hạn", code="OAUTH_CODE_INVALID")
        id_token = r.json().get("id_token")
        if not id_token:
            raise Unauthorized("Google không trả id_token", code="OAUTH_CODE_INVALID")
        return id_token

    def verify_id_token(self, id_token: str, *, nonce: str) -> GoogleIdentity:
        try:
            key = self._jwks.get_signing_key_from_jwt(id_token).key
            claims = jwt.decode(
                id_token, key, algorithms=["RS256"], audience=self._s.google_client_id,
                options={"require": ["iss", "aud", "exp", "sub", "nonce"]},
            )
        except jwt.PyJWTError as e:
            raise Unauthorized("id_token không hợp lệ", code="OAUTH_ID_TOKEN_INVALID") from e
        if claims.get("iss") not in ISSUERS:
            raise Unauthorized("issuer không hợp lệ", code="OAUTH_ID_TOKEN_INVALID")
        if claims.get("nonce") != nonce:
            raise Unauthorized("nonce không khớp", code="OAUTH_NONCE_MISMATCH")
        if not claims.get("email_verified"):
            raise Unauthorized("Email Google chưa xác minh", code="OAUTH_EMAIL_UNVERIFIED")
        return GoogleIdentity(
            sub=claims["sub"], email=claims["email"], email_verified=True,
            name=claims.get("name"), picture=claims.get("picture"),
        )
