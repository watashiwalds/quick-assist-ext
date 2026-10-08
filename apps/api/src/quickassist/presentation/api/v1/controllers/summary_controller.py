"""API Controller — tóm tắt bằng AI, trả PREVIEW (SDS §5.1.4). Lưu: PUT /notes/{id}/summary."""

import uuid

from fastapi import APIRouter, Depends, Header

from quickassist.business.summary import SummaryService
from quickassist.presentation.api.deps import AIProviderDep, CurrentUserId, DbSession, rate_limit
from quickassist.presentation.schemas.summary import SummaryIn, SummaryOut

router = APIRouter(prefix="/ai/summaries", tags=["summary"])


@router.post("", response_model=SummaryOut,
             dependencies=[Depends(rate_limit("ai", "rate_limit_ai_per_minute"))],
             responses={402: {"description": "Hết quota AI"}, 413: {"description": "Văn bản quá dài"},
                        429: {"description": "Quá tần suất (Retry-After)"}, 502: {"description": "AI lỗi"}})
async def summarize(
    body: SummaryIn, user_id: CurrentUserId, session: DbSession, ai: AIProviderDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
) -> SummaryOut:
    p = await SummaryService(session, ai).summarize(
        user_id, text=body.text, note_id=body.note_id, request_id=idempotency_key or uuid.uuid4().hex)
    return SummaryOut(summary=p.summary, tokens_used=p.tokens_used, request_id=p.request_id)
