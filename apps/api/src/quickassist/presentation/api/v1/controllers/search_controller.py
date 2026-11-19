"""API Controller — tìm kiếm ngữ nghĩa, kết quả gom theo nguồn (SDS §5.1.3, Phase 1)."""

from fastapi import APIRouter, Depends

from quickassist.business.semantic_search import SemanticSearchService
from quickassist.presentation.api.deps import AIProviderDep, CurrentUserId, DbSession, rate_limit
from quickassist.presentation.schemas.search import SearchIn, SearchNoteOut, SearchOut, SearchSourceOut

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchOut,
             dependencies=[Depends(rate_limit("search", "rate_limit_search_per_minute"))],
             responses={402: {"description": "Hết quota AI"},
                        429: {"description": "Quá tần suất (Retry-After)"}})
async def search(body: SearchIn, user_id: CurrentUserId, session: DbSession, ai: AIProviderDep) -> SearchOut:
    sources = await SemanticSearchService(session, ai).search_sources(
        user_id, body.query, folder_id=body.folder_id, max_sources=body.max_sources)
    return SearchOut(sources=[
        SearchSourceOut(
            domain=s.domain, label=s.label, source_rank=s.source_rank, note_count=s.note_count,
            notes=[SearchNoteOut(note_id=n.note_id, title=n.title, url=n.url, summary=n.summary,
                                 snippet=n.snippet, score=n.score, similarity=n.similarity)
                   for n in s.notes],
        ) for s in sources])
