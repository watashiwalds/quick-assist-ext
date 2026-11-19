"""Business Layer — SemanticSearchService (SDS Hình 1, §5.1.3): embed truy vấn → hybrid retrieval trong
không gian dữ liệu của CHÍNH user → (tuỳ chọn) rerank → top-k kèm nguồn."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import UpstreamError
from quickassist.business.notes import get_briefs
from quickassist.business.quota import QuotaService
from quickassist.business.semantic_search.contracts import SearchResult
from quickassist.business.semantic_search.grouping import ScoredSource, group_by_source
from quickassist.data_access.repositories.note_chunk_repository import ChunkHit, NoteChunkRepository
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.logging import get_logger
from quickassist.infrastructure.openai.base import AIProvider, AIProviderError, estimate_tokens

log = get_logger(__name__)


class SemanticSearchService:
    def __init__(self, session: AsyncSession, ai: AIProvider) -> None:
        self.s = session
        self.ai = ai
        self.chunks = NoteChunkRepository(session)

    async def search_sources(
        self, user_id: uuid.UUID, query: str, *, folder_id: uuid.UUID | None = None,
        max_sources: int | None = None, notes_per_source: int | None = None,
        quota_operation: str = "search",
    ) -> list[ScoredSource]:
        """Hợp đồng truy xuất DÙNG CHUNG (Phase 1): top nguồn theo domain, ngưỡng OR.

        Thư viện và RAG cùng gọi hàm này để không có hai luồng lọc/nhóm lệch nhau.
        """
        cfg = get_settings()
        max_sources = cfg.search_max_sources if max_sources is None else max_sources
        notes_per_source = cfg.search_notes_per_source if notes_per_source is None else notes_per_source
        # Nới sâu fetch: mỗi note có thể có nhiều chunk → cần dư để đủ note/nguồn sau grouping.
        k = min(max_sources * notes_per_source * 3, cfg.search_candidate_k * 2)
        results = await self._fetch(user_id, query, folder_id=folder_id, k=k,
                                    quota_operation=quota_operation)
        grouped = group_by_source(
            results, max_sources=max_sources, notes_per_source=notes_per_source,
            min_similarity=cfg.search_min_similarity, min_score=cfg.search_min_rrf)
        log.info("search_grouped", extra={
            "sources": len(grouped), "notes": sum(len(s.notes) for s in grouped),
            "query_chars": len(query)})
        return grouped

    async def _fetch(
        self, user_id: uuid.UUID, query: str, *, folder_id: uuid.UUID | None, k: int,
        quota_operation: str,
    ) -> list[SearchResult]:
        cfg = get_settings()
        request_id = f"{quota_operation}:{uuid.uuid4()}"

        async with QuotaService.open() as quota, \
                quota.leased(user_id, quota_operation, estimate_tokens(query), request_id) as lease:
            try:
                emb = await self.ai.embed([query])
            except AIProviderError as e:
                raise UpstreamError("Dịch vụ AI tạm thời không khả dụng", code="AI_UNAVAILABLE") from e
            await quota.commit(lease, emb.usage.total)

        hits: list[ChunkHit] = await self.chunks.hybrid_search(
            user_id, query, emb.vectors[0], folder_id=folder_id, k=k * 2, candidate_k=cfg.search_candidate_k,
        )
        # TODO(R02): rerank khi cfg.search_rerank_enabled; timeout → fallback thứ tự RRF.

        # Ghép thông tin nguồn qua hợp đồng của Notes Service; note đã xoá → tự loại.
        briefs = await get_briefs(self.s, user_id, list({h.note_id for h in hits}))
        results = [
            SearchResult(h.chunk_id, h.note_id, h.text, h.score,
                         briefs[h.note_id].title, briefs[h.note_id].url, briefs[h.note_id].folder_id,
                         h.similarity, briefs[h.note_id].domain, briefs[h.note_id].summary_text)
            for h in hits if h.note_id in briefs
        ][:k]
        log.info("search_done", extra={"hits": len(results), "query_chars": len(query)})
        return results
