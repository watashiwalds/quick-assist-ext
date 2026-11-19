"""API Controller — AutoChunk: tìm đoạn khớp truy vấn trên trang hiện tại, trả PREVIEW (ADR-0013).

Stateless (không ghi DB) → không cần Idempotency-Key. Lưu kết quả: POST /notes như note thường.

Phase 3 có hai endpoint dùng CHUNG một service:
  - `POST /ai/page-match`         JSON một lần (tương thích cũ, client không cần tiến độ).
  - `POST /ai/page-match/stream`  SSE tiến độ: extract → batch i/n → verify → done | error.
Lỗi đồng bộ trước khi stream (sai truy vấn, HTML quá lớn, nội dung dán rỗng) vẫn là JSON + mã HTTP chuẩn;
lỗi phát sinh trong stream (quota/AI/không trích được nội dung) là event `error` để UI báo đúng chỗ.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from quickassist.business.common.exceptions import AppError
from quickassist.business.page_match import (
    MatchProgress,
    PageMatchResult,
    PageMatchService,
    validate_request,
)
from quickassist.infrastructure.logging import get_logger
from quickassist.presentation.api.deps import AIProviderDep, CurrentUserId, rate_limit
from quickassist.presentation.schemas.page_match import PageMatchIn, PageMatchItemOut, PageMatchOut

router = APIRouter(prefix="/ai/page-match", tags=["page-match"])
log = get_logger(__name__)

_RESPONSES = {
    402: {"description": "Hết quota AI (QUOTA_EXCEEDED)"},
    413: {"description": "HTML trang vượt giới hạn (PAGE_TOO_LONG)"},
    422: {"description": "Trang không có nội dung chính (PAGE_NO_CONTENT) / dữ liệu sai"},
    429: {"description": "Quá tần suất (Retry-After)"},
    502: {"description": "AI embed lỗi (AI_UNAVAILABLE)"},
}


def _to_out(r: PageMatchResult) -> PageMatchOut:
    return PageMatchOut(
        mode=r.mode, match_ratio=r.match_ratio, warning=r.warning,  # type: ignore[arg-type]
        items=[PageMatchItemOut(id=i.id, occ=i.occ, text=i.text, score=i.score,
                                confidence=i.confidence, verified=i.verified)
               for i in r.items],
        total_chars=r.total_chars, truncated=r.truncated, full_text=r.full_text,
    )


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _encode(events: AsyncIterator[MatchProgress | PageMatchResult]) -> AsyncIterator[str]:
    try:
        async for item in events:
            if isinstance(item, MatchProgress):
                yield _sse("progress", {
                    "phase": item.phase, "index": item.index, "total": item.total,
                })
            else:
                yield _sse("done", _to_out(item).model_dump(mode="json"))
    except AppError as e:
        yield _sse("error", {"code": e.code, "message": e.message, "status": e.status_code})
    except Exception as e:  # noqa: BLE001 — stream đã mở, không thể đổi mã HTTP
        log.exception("page_match_stream_failed", extra={"error_type": type(e).__name__})
        yield _sse("error", {"code": "AI_UNAVAILABLE",
                             "message": "Không quét được trang lúc này", "status": 502})
    finally:
        # Client đóng kết nối / huỷ → đóng generator nghiệp vụ ngay, khối `async with` của lease
        # giải phóng quota giữ chỗ (release) thay vì treo tới release_stale.
        aclose = getattr(events, "aclose", None)
        if aclose is not None:
            await aclose()


@router.post("", response_model=PageMatchOut,
             dependencies=[Depends(rate_limit("page_match", "rate_limit_page_match_per_minute"))],
             responses=_RESPONSES)
async def page_match(body: PageMatchIn, user_id: CurrentUserId, ai: AIProviderDep) -> PageMatchOut:
    r = await PageMatchService(ai).match(
        user_id, query=body.query, html=body.html, text=body.text, url=body.url,
        scan_all=body.scan_all,
    )
    return _to_out(r)


@router.post("/stream", response_class=StreamingResponse,
             dependencies=[Depends(rate_limit("page_match", "rate_limit_page_match_per_minute"))],
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Luồng SSE: progress (extract/batch/verify) → done | error"},
                        **_RESPONSES})
async def page_match_stream(
    body: PageMatchIn, user_id: CurrentUserId, ai: AIProviderDep,
) -> StreamingResponse:
    # Kiểm tra đồng bộ trước khi mở stream → lỗi 413/422 vẫn có mã HTTP chuẩn cho UI.
    validate_request(query=body.query, html=body.html, text=body.text)
    svc = PageMatchService(ai)
    events = svc.stream(user_id, query=body.query, html=body.html, text=body.text, url=body.url,
                        scan_all=body.scan_all)
    return StreamingResponse(
        _encode(events), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
