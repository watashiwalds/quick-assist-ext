"""Dependency xác thực dùng cho MỌI router cần đăng nhập.

Đặt ở core (không phải trong module auth) để các module không phụ thuộc
lẫn nhau: notes/search/ai/... chỉ cần `CurrentUserId`, không import module auth.

QUY TẮC OWNERSHIP: user_id CHỈ được lấy từ đây, không bao giờ từ body/query.
"""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from quickassist.core.errors import Unauthorized
from quickassist.core.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized("Thiếu access token", code="TOKEN_MISSING")
    claims = decode_access_token(creds.credentials)
    try:
        return uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as e:
        raise Unauthorized("Token không hợp lệ", code="TOKEN_INVALID") from e


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
