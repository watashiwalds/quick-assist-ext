"""Infrastructure Layer — primitive bảo mật: JWT app access token, băm refresh token.

Access token: JWT HS256 ngắn hạn (15'), stateless → API scale ngang được (ADR-0005).
Refresh token: chuỗi ngẫu nhiên; DB chỉ lưu SHA-256.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.errors import TokenError

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
    return jwt.encode(payload, s.jwt_secret.get_secret_value(), algorithm=_ALGO), s.access_token_ttl_seconds


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        claims = jwt.decode(
            token, s.jwt_secret.get_secret_value(), algorithms=[_ALGO], issuer=s.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenError("TOKEN_EXPIRED", "Phiên đăng nhập đã hết hạn") from e
    except jwt.PyJWTError as e:
        raise TokenError("TOKEN_INVALID", "Token không hợp lệ") from e
    if claims.get("typ") != "access":
        raise TokenError("TOKEN_INVALID", "Token không hợp lệ")
    return claims


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
