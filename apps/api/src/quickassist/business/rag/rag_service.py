"""Business Layer — RAGService (SDS Hình 1, §5.1.6) — Nice-to-have, task X01.

Khung thực hiện (giữ đúng tầng):
  1. Lấy tối đa 5 cặp hỏi–đáp gần nhất → cần entity ChatSession/ChatMessage ở data/models
     + ChatRepository ở data_access/repositories (service này sở hữu).
  2. SemanticSearchService.retrieve(...) lấy ngữ cảnh (quota_operation="rag_retrieve").
  3. QuotaService.reserve → ai.stream(...) → yield từng delta cho controller (SSE, ADR-0009).
  4. Kết thúc hoặc bị ngắt (Stop) → quota.commit(usage thật) + lưu lịch sử kèm nguồn.
"""

import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import NotImplementedYet
from quickassist.infrastructure.openai.base import AIProvider


class RAGService:
    def __init__(self, session: AsyncSession, ai: AIProvider) -> None:
        self.s = session
        self.ai = ai

    async def stream_answer(self, user_id: uuid.UUID, question: str) -> AsyncIterator[str]:
        raise NotImplementedYet("Chat RAG chưa được triển khai", code="CHAT_NOT_IMPLEMENTED")
        yield ""  # pragma: no cover — giữ chữ ký async generator
