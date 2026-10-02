"""Primitive bảo mật dùng chung: JWT app access token + refresh token.

Access token: JWT HS256 ngắn hạn (mặc định 15'), stateless → API scale ngang được.
Refresh token: chuỗi ngẫu nhiên; DB chỉ lưu SHA-256 của nó (module auth quản lý).
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from quickassist.core.config import get_settings
from quickassist.core.errors import Unauthorized

_ALGO = "HS256"


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iss": s.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=s.access_token_ttl_seconds)).timestamp()),
        "typ": "access",
    }
    token = jwt.encode(payload, s.jwt_secret.get_secret_value(), algorithm=_ALGO)
    return token, s.access_token_ttl_seconds


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        claims = jwt.decode(
            token,
            s.jwt_secret.get_secret_value(),
            algorithms=[_ALGO],
            issuer=s.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("Phiên đăng nhập đã hết hạn", code="TOKEN_EXPIRED") from e
    except jwt.PyJWTError as e:
        raise Unauthorized("Token không hợp lệ", code="TOKEN_INVALID") from e
    if claims.get("typ") != "access":
        raise Unauthorized("Token không hợp lệ", code="TOKEN_INVALID")
    return claims


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
