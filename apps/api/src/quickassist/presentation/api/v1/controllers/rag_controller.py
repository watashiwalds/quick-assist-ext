"""API Controller — hỏi đáp RAG trên ghi chú cá nhân (SDS §5.1.6), trả lời dạng SSE (ADR-0009).

Sự kiện (mỗi sự kiện: `event: <tên>` + `data: <json>`):
  sources  [{index, note_id, chunk_id, title, url, snippet}]  — luôn là sự kiện đầu tiên
  delta    {"text": "..."}                                    — từng phần câu trả lời
  done     {"tokens_used": n}                                 — kết thúc bình thường
  error    {"code": "...", "message": "..."}                  — AI lỗi giữa chừng (đã chốt quota phần đã sinh)
Lỗi trước khi stream (hết quota, quá tần suất, đầu vào sai) trả JSON lỗi chuẩn với mã HTTP tương ứng.
Client ngắt kết nối (nút Dừng) → server dừng sinh và chỉ trừ quota phần đã sinh.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from quickassist.business.rag import ChatEvent, RAGService
from quickassist.presentation.api.deps import AIProviderDep, CurrentUserId, DbSession, rate_limit
from quickassist.presentation.schemas.rag import ChatIn

router = APIRouter(prefix="/ai/chat", tags=["rag"])


def _sse(event: ChatEvent) -> str:
    data = {"text": event.data} if event.type == "delta" else event.data
    return f"event: {event.type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _encode(events: AsyncIterator[ChatEvent]) -> AsyncIterator[str]:
    try:
        async for e in events:
            yield _sse(e)
    finally:
        # Đóng generator nghiệp vụ ngay khi client ngắt → khối finally của nó chốt quota liền.
        aclose = getattr(events, "aclose", None)
        if aclose is not None:
            await aclose()


@router.post("", response_class=StreamingResponse,
             dependencies=[Depends(rate_limit("ai", "rate_limit_ai_per_minute"))],
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Luồng SSE: sources → delta… → done | error"},
                        402: {"description": "Hết quota AI"}, 413: {"description": "Câu hỏi quá dài"},
                        429: {"description": "Quá tần suất (Retry-After)"}, 502: {"description": "AI lỗi"}})
async def chat(
    body: ChatIn, user_id: CurrentUserId, session: DbSession, ai: AIProviderDep
) -> StreamingResponse:
    svc = RAGService(session, ai)
    prepared = await svc.prepare(user_id, body.question, folder_id=body.folder_id,
                                 history=[(t.role, t.content) for t in body.history])
    return StreamingResponse(
        _encode(svc.stream(prepared)), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
