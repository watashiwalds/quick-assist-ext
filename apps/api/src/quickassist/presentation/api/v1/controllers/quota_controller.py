"""API Controller — xem hạn mức AI còn lại."""

from fastapi import APIRouter

from quickassist.business.quota import QuotaService
from quickassist.presentation.api.deps import CurrentUserId, DbSession
from quickassist.presentation.schemas.quota import QuotaOut

router = APIRouter(prefix="/me/quota", tags=["quota"])


@router.get("", response_model=QuotaOut)
async def get_quota(user_id: CurrentUserId, session: DbSession) -> QuotaOut:
    st = await QuotaService(session).status(user_id)
    return QuotaOut(limit_tokens=st.limit_tokens, used_tokens=st.used_tokens,
                    reserved_tokens=st.reserved_tokens, remaining_tokens=st.remaining)
