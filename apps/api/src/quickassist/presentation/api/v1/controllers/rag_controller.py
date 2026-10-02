"""API Controller — hỏi đáp RAG trên ghi chú cá nhân (SDS §5.1.6, Nice-to-have). Sẽ trả SSE."""

from fastapi import APIRouter

from quickassist.business.rag import RAGService
from quickassist.presentation.api.deps import AIProviderDep, CurrentUserId, DbSession

router = APIRouter(prefix="/ai/chat", tags=["rag"])


@router.post("")
async def chat(user_id: CurrentUserId, session: DbSession, ai: AIProviderDep) -> None:
    # TODO(X01): StreamingResponse(media_type="text/event-stream") bọc RAGService.stream_answer
    async for _ in RAGService(session, ai).stream_answer(user_id, ""):
        pass
