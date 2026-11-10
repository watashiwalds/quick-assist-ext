"""API Controller — AutoChunk: tìm đoạn khớp truy vấn trên trang hiện tại, trả PREVIEW (ADR-0013).

Stateless (không ghi DB) → không cần Idempotency-Key. Lưu kết quả: POST /notes như note thường.
"""

from fastapi import APIRouter, Depends

from quickassist.business.page_match import PageMatchService
from quickassist.presentation.api.deps import AIProviderDep, CurrentUserId, rate_limit
from quickassist.presentation.schemas.page_match import PageMatchIn, PageMatchItemOut, PageMatchOut

router = APIRouter(prefix="/ai/page-match", tags=["page-match"])


@router.post("", response_model=PageMatchOut,
             dependencies=[Depends(rate_limit("page_match", "rate_limit_page_match_per_minute"))],
             responses={402: {"description": "Hết quota AI (QUOTA_EXCEEDED)"},
                        413: {"description": "HTML trang vượt giới hạn (PAGE_TOO_LONG)"},
                        422: {"description": "Trang không có nội dung chính (PAGE_NO_CONTENT) / dữ liệu sai"},
                        429: {"description": "Quá tần suất (Retry-After)"},
                        502: {"description": "AI embed lỗi (AI_UNAVAILABLE)"}})
async def page_match(body: PageMatchIn, user_id: CurrentUserId, ai: AIProviderDep) -> PageMatchOut:
    r = await PageMatchService(ai).match(user_id, query=body.query, html=body.html, url=body.url)
    return PageMatchOut(
        mode=r.mode, match_ratio=r.match_ratio, warning=r.warning,  # type: ignore[arg-type]
        items=[PageMatchItemOut(id=i.id, occ=i.occ, text=i.text, score=i.score, verified=i.verified)
               for i in r.items],
        total_chars=r.total_chars, truncated=r.truncated, full_text=r.full_text,
    )
