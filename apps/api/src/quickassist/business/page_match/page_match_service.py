"""Business Layer — PageMatchService (AutoChunk, ADR-0013): tìm các đoạn trên trang hiện tại khớp
ý định người dùng. Operation STATELESS trả preview — không ghi DB; lưu bằng POST /notes như note thường.

    HTML ─► Trafilatura (process pool) ──────────► blocks ─► embed theo lô (quota lease 1)
    text ─► split_paragraphs (reflow + gộp) ────► blocks ─┘
         ─► cosine ─► lọc min_score / top_candidates ─► LLM thẩm định confidence 0..1 (quota lease 2)
         ─► confidence ≥ min_confidence ─► match_ratio ─► mode "segments" | "full_page"

Phase 3: `scan_all=True` bỏ trần `page_match_max_chars`; block được embed theo lô
`page_match_embed_batch_blocks`, timeout TÍNH THEO LÔ. Một lease cho toàn bộ embed — commit tổng usage
khi xong, context manager tự release khi lỗi/huỷ giữa chừng. `stream()` phát tiến độ từng bước cho
endpoint SSE; `match()` giữ nguyên contract JSON cũ.

LLM lỗi / quá giờ / JSON hỏng / hết quota ở bước thẩm định → degrade có kiểm soát: trả ứng viên cosine
≥ `page_match_fallback_min_similarity` với verified=false + warning="VERIFY_UNAVAILABLE" (tính năng không
chết khi AI thẩm định lỗi). Log chỉ metadata — KHÔNG log nội dung trang hay truy vấn.
"""

import asyncio
import math
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from quickassist.business.common.exceptions import (
    PayloadTooLarge,
    QuotaExceeded,
    Unprocessable,
    UpstreamError,
)
from quickassist.business.page_match.extractor import (
    Block,
    ExtractError,
    extract_blocks,
    extract_text_blocks,
)
from quickassist.business.page_match.prompts import (
    VerdictParseError,
    page_match_messages,
    parse_verdicts,
)
from quickassist.business.quota import QuotaService
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.logging import get_logger
from quickassist.infrastructure.openai.base import AIProvider, AIProviderError, estimate_tokens

log = get_logger(__name__)

VERIFY_UNAVAILABLE = "VERIFY_UNAVAILABLE"
MAX_QUERY_CHARS = 500


@dataclass(frozen=True)
class MatchItem:
    id: str
    occ: int
    text: str
    score: float
    confidence: float
    verified: bool


@dataclass(frozen=True)
class MatchProgress:
    """Tiến độ một bước của lần quét — controller SSE chuyển thành event `progress`."""

    phase: Literal["extract", "batch", "verify"]
    index: int | None = None
    total: int | None = None


@dataclass(frozen=True)
class PageMatchResult:
    mode: Literal["segments", "full_page"]
    match_ratio: float
    warning: str | None
    items: list[MatchItem]
    total_chars: int
    truncated: bool
    full_text: str | None  # chỉ có khi mode="full_page" — nội dung cả trang để "Lưu cả trang"


PageMatchEvent = MatchProgress | PageMatchResult


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def compute_match_ratio(
    *, total_chars: int, eligible_chars: int, candidate_chars: int, matched_chars: int,
) -> float:
    """∑ ký tự đoạn khớp / ∑ ký tự trang.

    Chỉ tối đa `top_candidates` đoạn được thẩm định. Khi số đoạn vượt ngưỡng điểm (eligible) nhiều hơn số
    được thẩm định, ước lượng phần chưa thẩm định theo tỉ lệ được xác nhận trong nhóm đã thẩm định —
    nếu không, trang dài khớp gần hết sẽ không bao giờ đạt ngưỡng full_page.
    """
    if total_chars <= 0 or candidate_chars <= 0:
        return 0.0
    matched = matched_chars
    if eligible_chars > candidate_chars:
        matched = eligible_chars * (matched_chars / candidate_chars)
    return round(min(1.0, matched / total_chars), 4)


def batch_blocks(blocks: list[Block], size: int) -> list[list[Block]]:
    """Chia block thành lô cố định; size ≤ 0 → một lô duy nhất (an toàn khi cấu hình sai)."""
    if size <= 0:
        return [blocks] if blocks else []
    return [blocks[i:i + size] for i in range(0, len(blocks), size)]


def validate_request(*, query: str, html: str | None, text: str | None) -> str:
    """Kiểm tra đồng bộ trước khi mở stream → endpoint SSE vẫn trả JSON 413/422 đúng chuẩn.

    Trả truy vấn đã chuẩn hoá. Nội dung rỗng/không trích được vẫn được phát hiện sau khi extract.
    """
    cfg = get_settings()
    q = " ".join(query.replace("\x00", "").split())
    if not q or len(q) > MAX_QUERY_CHARS:
        raise Unprocessable("Truy vấn phải có 1–500 ký tự", code="PAGE_MATCH_QUERY_INVALID")
    if text is not None:
        if not text.strip():
            raise Unprocessable("Không có nội dung để quét", code="PAGE_NO_CONTENT",
                                details={"reason": "empty"})
        return q
    html = html or ""
    html_bytes = len(html.encode("utf-8", errors="ignore"))
    if html_bytes > cfg.page_match_max_html_bytes:
        raise PayloadTooLarge("Trang quá dài để quét", code="PAGE_TOO_LONG",
                              details={"max_bytes": cfg.page_match_max_html_bytes})
    return q


class PageMatchService:
    def __init__(self, ai: AIProvider) -> None:
        self.ai = ai

    async def match(
        self, user_id: uuid.UUID, *, query: str, html: str | None = None, text: str | None = None,
        url: str | None = None, scan_all: bool = False,
    ) -> PageMatchResult:
        """Contract JSON cũ: chạy trọn stream rồi trả kết quả cuối. Lỗi nghiệp vụ vẫn ném ra như trước."""
        async for event in self.stream(
            user_id, query=query, html=html, text=text, url=url, scan_all=scan_all,
        ):
            if isinstance(event, PageMatchResult):
                return event
        raise UpstreamError("Không có kết quả quét", code="AI_UNAVAILABLE")

    async def stream(
        self, user_id: uuid.UUID, *, query: str, html: str | None = None, text: str | None = None,
        url: str | None = None, scan_all: bool = False,
    ) -> AsyncIterator[PageMatchEvent]:
        """Một trong hai nguồn: `html` (trang hiện tại) hoặc `text` (nội dung dán). Schema đã bảo đảm
        đúng một nguồn; service ưu tiên `text` nếu cả hai cùng có mặt.

        Phát `MatchProgress` cho từng bước rồi `PageMatchResult`. Exceptions nghiệp vụ (413/422/402/502)
        được controller SSE chuyển thành event `error`; endpoint JSON dùng `match()` để giữ HTTP status.
        """
        cfg = get_settings()
        started = time.perf_counter()
        q = validate_request(query=query, html=html, text=text)
        max_chars = None if scan_all else cfg.page_match_max_chars

        yield MatchProgress("extract")
        if text is not None:
            source = "text"
            html_bytes = 0
            try:
                extraction = extract_text_blocks(
                    text, max_block_chars=cfg.page_match_max_block_chars,
                    max_chars=max_chars,
                    min_block_chars=cfg.page_match_min_block_chars,
                )
            except ExtractError as e:
                raise Unprocessable("Không có nội dung để quét", code="PAGE_NO_CONTENT",
                                    details={"reason": e.reason}) from e
        else:
            source = "html"
            html = html or ""
            html_bytes = len(html.encode("utf-8", errors="ignore"))
            try:
                extraction = await extract_blocks(
                    html, timeout_seconds=cfg.page_match_extract_timeout_seconds,
                    max_block_chars=cfg.page_match_max_block_chars, max_chars=max_chars,
                )
            except ExtractError as e:
                raise Unprocessable("Không trích được nội dung chính của trang", code="PAGE_NO_CONTENT",
                                    details={"reason": e.reason}) from e
        blocks = extraction.blocks

        # --- Lease 1: embed query một lần + mọi block theo lô (timeout từng lô), commit tổng usage.
        batches = batch_blocks(blocks, cfg.page_match_embed_batch_blocks)
        estimate = sum(estimate_tokens(t) for t in (q, *(b.text for b in blocks)))
        async with QuotaService.open() as quota, \
                quota.leased(user_id, "page_match_embed", estimate,
                             f"page_match_embed:{uuid.uuid4()}") as lease:
            try:
                query_emb = await asyncio.wait_for(
                    self.ai.embed([q]), timeout=cfg.page_match_embed_timeout_seconds)
            except (AIProviderError, TimeoutError) as e:
                log.warning("page_match_embed_failed", extra={
                    "batch": 0, "error_type": type(e).__name__})
                raise UpstreamError("Dịch vụ AI tạm thời không khả dụng", code="AI_UNAVAILABLE") from e
            used_tokens = query_emb.usage.total
            qv = query_emb.vectors[0]
            bvs: list[list[float]] = []
            for i, batch in enumerate(batches, 1):
                yield MatchProgress("batch", i, len(batches))
                try:
                    emb = await asyncio.wait_for(
                        self.ai.embed([b.text for b in batch]),
                        timeout=cfg.page_match_embed_timeout_seconds,
                    )
                except (AIProviderError, TimeoutError) as e:
                    log.warning("page_match_embed_failed", extra={
                        "batch": i, "total": len(batches), "error_type": type(e).__name__})
                    raise UpstreamError("Dịch vụ AI tạm thời không khả dụng", code="AI_UNAVAILABLE") from e
                used_tokens += emb.usage.total
                bvs.extend(emb.vectors)
            await quota.commit(lease, used_tokens)

        scores = [cosine(qv, v) for v in bvs]
        eligible = [i for i, s in enumerate(scores) if s >= cfg.page_match_min_score]
        top = sorted(eligible, key=lambda i: scores[i], reverse=True)[: cfg.page_match_top_candidates]
        candidates = sorted(top)  # thứ tự trang

        warning: str | None = None
        verdicts: dict[str, float] = {}
        if candidates:
            yield MatchProgress("verify")
            verdicts, warning = await self._verify(user_id, q, [blocks[i] for i in candidates])

        if warning:
            # Fallback: chỉ giữ đoạn đủ tương đồng cosine, đánh dấu chưa thẩm định.
            chosen = [i for i in candidates
                      if scores[i] >= cfg.page_match_fallback_min_similarity]
            items = [MatchItem(blocks[i].id, blocks[i].occ, blocks[i].text, round(scores[i], 4),
                               confidence=round(scores[i], 4), verified=False)
                     for i in chosen]
        else:
            chosen = [i for i in candidates
                      if verdicts.get(blocks[i].id, 0.0) >= cfg.page_match_min_confidence]
            items = [MatchItem(blocks[i].id, blocks[i].occ, blocks[i].text, round(scores[i], 4),
                               confidence=round(verdicts.get(blocks[i].id, 0.0), 4), verified=True)
                     for i in chosen]

        ratio = compute_match_ratio(
            total_chars=extraction.total_chars,
            eligible_chars=sum(len(blocks[i].text) for i in eligible),
            candidate_chars=sum(len(blocks[i].text) for i in candidates),
            matched_chars=sum(len(it.text) for it in items),
        )
        mode: Literal["segments", "full_page"] = (
            "full_page" if items and ratio >= cfg.page_match_full_page_ratio else "segments")
        full_text = "\n\n".join(b.text for b in blocks) if mode == "full_page" else None

        log.info("page_match_done", extra={
            "source": source, "html_bytes": html_bytes, "blocks": len(blocks),
            "batches": len(batches), "scan_all": scan_all,
            "chars": extraction.total_chars, "truncated": extraction.truncated,
            "candidates": len(candidates), "matched": len(items), "mode": mode,
            "match_ratio": ratio, "warning": warning, "has_url": bool(url),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        })
        yield PageMatchResult(mode, ratio, warning, items, extraction.total_chars,
                              extraction.truncated, full_text)

    async def _verify(
        self, user_id: uuid.UUID, query: str, candidates: list[Block],
    ) -> tuple[dict[str, float], str | None]:
        """Lease 2: LLM thẩm định confidence. Trả (id → confidence, warning).

        Mọi lỗi → (∅, VERIFY_UNAVAILABLE) — caller fallback theo cosine.
        """
        cfg = get_settings()
        max_out = cfg.page_match_verify_max_output_tokens
        messages = page_match_messages(query, [(b.id, b.text) for b in candidates])
        estimate = sum(estimate_tokens(m.content) for m in messages) + max_out
        try:
            async with QuotaService.open() as quota, \
                    quota.leased(user_id, "page_match_verify", estimate,
                                 f"page_match_verify:{uuid.uuid4()}") as lease:
                try:
                    result = await asyncio.wait_for(self.ai.complete(messages, max_tokens=max_out),
                                                    timeout=cfg.page_match_verify_timeout_seconds)
                except (AIProviderError, TimeoutError) as e:
                    await quota.release(lease)  # trả về bình thường (không ném) → tự release
                    log.warning("page_match_verify_failed", extra={"error_type": type(e).__name__})
                    return {}, VERIFY_UNAVAILABLE
                await quota.commit(lease, result.usage.total)
        except QuotaExceeded:  # chỉ reserve() trong leased() ném lỗi này
            log.info("page_match_verify_skipped", extra={"reason": "quota"})
            return {}, VERIFY_UNAVAILABLE
        try:
            return parse_verdicts(result.text, {b.id for b in candidates}), None
        except VerdictParseError as e:
            log.warning("page_match_verify_unparsable", extra={"reason": str(e)})
            return {}, VERIFY_UNAVAILABLE
