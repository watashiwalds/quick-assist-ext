"""API Controller — xem hạn mức AI còn lại; đặt lại số liệu cho demo hoặc user BYOK (ADR-0016 D6)."""

from fastapi import APIRouter

from quickassist.business.ai_settings import AISettingsService
from quickassist.business.quota import QuotaService, QuotaStatus
from quickassist.presentation.api.deps import CurrentUserId, DbSession
from quickassist.presentation.schemas.quota import QuotaOut

router = APIRouter(prefix="/me/quota", tags=["quota"])


def _out(st: QuotaStatus, *, byok: bool) -> QuotaOut:
    return QuotaOut(limit_tokens=st.limit_tokens, used_tokens=st.used_tokens,
                    reserved_tokens=st.reserved_tokens, remaining_tokens=st.remaining,
                    billing_mode="byok" if byok else "server")


@router.get("", response_model=QuotaOut)
async def get_quota(user_id: CurrentUserId, session: DbSession) -> QuotaOut:
    st = await QuotaService(session).status(user_id)
    return _out(st, byok=await AISettingsService(session).is_byok(user_id))


@router.post("/reset", response_model=QuotaOut)
async def reset_quota(user_id: CurrentUserId, session: DbSession) -> QuotaOut:
    """Đặt lại số liệu: demo/dev hoặc user BYOK (AI của user tự trả). User inherit ở prod bị 403."""
    st = await QuotaService(session).reset_usage(user_id)
    return _out(st, byok=await AISettingsService(session).is_byok(user_id))
