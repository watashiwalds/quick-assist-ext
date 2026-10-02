"""API Controller — tìm kiếm ngữ nghĩa (SDS §5.1.3)."""

from dataclasses import asdict

from fastapi import APIRouter

from quickassist.business.semantic_search import SemanticSearchService
from quickassist.presentation.api.deps import AIProviderDep, CurrentUserId, DbSession
from quickassist.presentation.schemas.search import SearchHitOut, SearchIn, SearchOut

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchOut)
async def search(body: SearchIn, user_id: CurrentUserId, session: DbSession, ai: AIProviderDep) -> SearchOut:
    results = await SemanticSearchService(session, ai).retrieve(
        user_id, body.query, folder_id=body.folder_id, top_k=body.top_k)
    return SearchOut(items=[SearchHitOut(**asdict(r)) for r in results])
