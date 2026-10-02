"""Presentation Layer — dependency dùng chung cho controller.

QUY TẮC OWNERSHIP: user_id CHỈ lấy từ access token ở đây, không bao giờ từ body/query.
"""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import Unauthorized
from quickassist.data.database import get_session
from quickassist.infrastructure.errors import TokenError
from quickassist.infrastructure.openai import get_ai_provider
from quickassist.infrastructure.openai.base import AIProvider
from quickassist.infrastructure.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> uuid.UUID:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized("Thiếu access token", code="TOKEN_MISSING")
    try:
        claims = decode_access_token(creds.credentials)
        return uuid.UUID(claims["sub"])
    except TokenError as e:
        raise Unauthorized(e.message, code=e.code) from e
    except (KeyError, ValueError) as e:
        raise Unauthorized("Token không hợp lệ", code="TOKEN_INVALID") from e


DbSession = Annotated[AsyncSession, Depends(get_session)]
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
AIProviderDep = Annotated[AIProvider, Depends(get_ai_provider)]
