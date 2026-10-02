"""Semantic Search Service (SDS §5.1.3): embed truy vấn → hybrid retrieval trong
không gian dữ liệu của CHÍNH user → (tuỳ chọn) rerank → top-k kèm nguồn."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.core.config import get_settings
from quickassist.core.db import get_sessionmaker
from quickassist.core.errors import UpstreamError
from quickassist.core.logging import get_logger
from quickassist.modules.notes.public import get_briefs
from quickassist.modules.quota.public import QuotaService
from quickassist.modules.search.repository import ChunkHit, ChunkRepository
from quickassist.providers.ai.base import AIProvider, AIProviderError, estimate_tokens

log = get_logger(__name__)


@dataclass(frozen=True)
class SearchResult:
    chunk_id: uuid.UUID
    note_id: uuid.UUID
    text: str
    score: float
    note_title: str | None
    note_url: str | None
    folder_id: uuid.UUID


class SearchService:
    def __init__(self, session: AsyncSession, ai: AIProvider) -> None:
        self.s = session
        self.ai = ai
        self.chunks = ChunkRepository(session)

    async def retrieve(
        self, user_id: uuid.UUID, query: str, *, folder_id: uuid.UUID | None = None,
        top_k: int | None = None, quota_operation: str = "search",
    ) -> list[SearchResult]:
        cfg = get_settings()
        k = top_k or cfg.search_top_k
        request_id = f"{quota_operation}:{uuid.uuid4()}"

        async with get_sessionmaker()() as qs:  # session riêng cho quota (xem quota/public.py)
            quota = QuotaService(qs)
            lease = await quota.reserve(user_id, quota_operation, estimate_tokens(query), request_id)
            try:
                emb = await self.ai.embed([query])
            except AIProviderError as e:
                await quota.release(lease)
                raise UpstreamError("Dịch vụ AI tạm thời không khả dụng", code="AI_UNAVAILABLE") from e
            await quota.commit(lease, emb.usage.total)

        hits: list[ChunkHit] = await self.chunks.hybrid_search(
            user_id, query, emb.vectors[0], folder_id=folder_id, k=k * 2, candidate_k=cfg.search_candidate_k,
        )
        # TODO(R02 - Vinh): rerank khi cfg.search_rerank_enabled; timeout → fallback thứ tự RRF.

        # Ghép thông tin nguồn qua public API của notes; note đã xoá → tự loại.
        briefs = await get_briefs(self.s, user_id, list({h.note_id for h in hits}))
        results = [
            SearchResult(h.chunk_id, h.note_id, h.text, h.score,
                         briefs[h.note_id].title, briefs[h.note_id].url, briefs[h.note_id].folder_id)
            for h in hits if h.note_id in briefs
        ][:k]
        log.info("search_done", extra={"hits": len(results), "query_chars": len(query)})
        return results
