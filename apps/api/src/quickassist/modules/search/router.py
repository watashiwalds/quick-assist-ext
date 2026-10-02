from dataclasses import asdict

from fastapi import APIRouter

from quickassist.core.auth_context import CurrentUserId
from quickassist.core.db import DbSession
from quickassist.modules.search.schemas import SearchHitOut, SearchIn, SearchOut
from quickassist.modules.search.service import SearchService
from quickassist.providers.ai import AIProviderDep

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchOut)
async def search(body: SearchIn, user_id: CurrentUserId, session: DbSession, ai: AIProviderDep) -> SearchOut:
    results = await SearchService(session, ai).retrieve(
        user_id, body.query, folder_id=body.folder_id, top_k=body.top_k
    )
    return SearchOut(items=[SearchHitOut(**asdict(r)) for r in results])
