from fastapi import APIRouter

from quickassist.core.auth_context import CurrentUserId
from quickassist.core.db import DbSession
from quickassist.core.schemas import ApiModel
from quickassist.modules.quota.service import QuotaService

router = APIRouter(prefix="/me/quota", tags=["quota"])


class QuotaOut(ApiModel):
    limit_tokens: int
    used_tokens: int
    reserved_tokens: int
    remaining_tokens: int


@router.get("", response_model=QuotaOut)
async def get_quota(user_id: CurrentUserId, session: DbSession) -> QuotaOut:
    st = await QuotaService(session).status(user_id)
    return QuotaOut(limit_tokens=st.limit_tokens, used_tokens=st.used_tokens,
                    reserved_tokens=st.reserved_tokens, remaining_tokens=st.remaining)
