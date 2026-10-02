import uuid

from fastapi import APIRouter, Header
from pydantic import Field

from quickassist.core.auth_context import CurrentUserId
from quickassist.core.db import DbSession
from quickassist.core.errors import NotImplementedYet
from quickassist.core.schemas import ApiModel
from quickassist.modules.ai.service import AIService
from quickassist.providers.ai import AIProviderDep

router = APIRouter(prefix="/ai", tags=["ai"])


class SummaryIn(ApiModel):
    text: str | None = Field(default=None, min_length=1)
    note_id: uuid.UUID | None = None


class SummaryOut(ApiModel):
    summary: str
    tokens_used: int
    request_id: str


@router.post("/summaries", response_model=SummaryOut)
async def summarize(
    body: SummaryIn, user_id: CurrentUserId, session: DbSession, ai: AIProviderDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
) -> SummaryOut:
    """Tạo bản tóm tắt PREVIEW. Lưu vào note: PUT /notes/{id}/summary."""
    rid = idempotency_key or uuid.uuid4().hex
    p = await AIService(session, ai).summarize(user_id, text=body.text, note_id=body.note_id,
                                               request_id=rid)
    return SummaryOut(summary=p.summary, tokens_used=p.tokens_used, request_id=p.request_id)


@router.post("/chat")
async def chat(user_id: CurrentUserId) -> None:
    """Nice-to-have (SDS §5.1.6). Sẽ trả text/event-stream. Xem TODO trong ai/service.py."""
    raise NotImplementedYet("Chat RAG chưa được triển khai", code="CHAT_NOT_IMPLEMENTED")
