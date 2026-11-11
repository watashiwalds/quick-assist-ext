"""Business Layer — PageMatchService (AutoChunk, ADR-0013): tìm các đoạn trên trang hiện tại khớp
ý định người dùng. Operation STATELESS trả preview — không ghi DB; lưu bằng POST /notes như note thường.

    HTML ─► Trafilatura (process pool) ─► blocks ─► embed([query, *blocks]) 1 batch (quota lease 1)
         ─► cosine ─► lọc min_score / top_candidates ─► LLM thẩm định JSON (quota lease 2)
         ─► match_ratio ─► mode "segments" | "full_page"

LLM lỗi / quá giờ / JSON hỏng / hết quota ở bước thẩm định → degrade có kiểm soát: trả ứng viên theo
điểm với verified=false + warning="VERIFY_UNAVAILABLE" (tính năng không chết khi AI thẩm định lỗi).
Log chỉ metadata — KHÔNG log nội dung trang hay truy vấn.
"""

import asyncio
import math
import time
import uuid
from dataclasses import dataclass
from typing import Literal

from quickassist.business.common.exceptions import (
    PayloadTooLarge,
    QuotaExceeded,
    Unprocessable,
    UpstreamError,
)
from quickassist.business.page_match.extractor import Block, ExtractError, extract_blocks
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
    verified: bool


@dataclass(frozen=True)
class PageMatchResult:
    mode: Literal["segments", "full_page"]
    match_ratio: float
    warning: str | None
    items: list[MatchItem]
    total_chars: int
    truncated: bool
    full_text: str | None  # chỉ có khi mode="full_page" — nội dung cả trang để "Lưu cả trang"


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


class PageMatchService:
    def __init__(self, ai: AIProvider) -> None:
        self.ai = ai

    async def match(
        self, user_id: uuid.UUID, *, query: str, html: str, url: str | None = None,
    ) -> PageMatchResult:
        cfg = get_settings()
        started = time.perf_counter()
        query = " ".join(query.replace("\x00", "").split())
        if not query or len(query) > MAX_QUERY_CHARS:
            raise Unprocessable("Truy vấn phải có 1–500 ký tự", code="PAGE_MATCH_QUERY_INVALID")
        html_bytes = len(html.encode("utf-8", errors="ignore"))
        if html_bytes > cfg.page_match_max_html_bytes:
            raise PayloadTooLarge("Trang quá dài để quét", code="PAGE_TOO_LONG",
                                  details={"max_bytes": cfg.page_match_max_html_bytes})

        try:
            extraction = await extract_blocks(
                html, timeout_seconds=cfg.page_match_extract_timeout_seconds,
                max_block_chars=cfg.page_match_max_block_chars, max_chars=cfg.page_match_max_chars,
            )
        except ExtractError as e:
            raise Unprocessable("Không trích được nội dung chính của trang", code="PAGE_NO_CONTENT",
                                details={"reason": e.reason}) from e
        blocks = extraction.blocks

        # --- Lease 1: embed truy vấn + mọi khối trong MỘT batch
        texts = [query, *(b.text for b in blocks)]
        async with QuotaService.open() as quota, \
                quota.leased(user_id, "page_match_embed", sum(estimate_tokens(t) for t in texts),
                             f"page_match_embed:{uuid.uuid4()}") as lease:
            try:
                emb = await self.ai.embed(texts)
            except AIProviderError as e:
                raise UpstreamError("Dịch vụ AI tạm thời không khả dụng", code="AI_UNAVAILABLE") from e
            await quota.commit(lease, emb.usage.total)

        qv, bvs = emb.vectors[0], emb.vectors[1:]
        scores = [cosine(qv, v) for v in bvs]
        eligible = [i for i, s in enumerate(scores) if s >= cfg.page_match_min_score]
        top = sorted(eligible, key=lambda i: scores[i], reverse=True)[: cfg.page_match_top_candidates]
        candidates = sorted(top)  # thứ tự trang

        warning: str | None = None
        verified_ids: set[str] = set()
        if candidates:
            verified_ids, warning = await self._verify(user_id, query, [blocks[i] for i in candidates])

        if warning:
            chosen = candidates  # fallback: theo điểm, chưa xác nhận
        else:
            chosen = [i for i in candidates if blocks[i].id in verified_ids]
        items = [MatchItem(blocks[i].id, blocks[i].occ, blocks[i].text, round(scores[i], 4),
                           verified=not warning) for i in chosen]

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
            "html_bytes": html_bytes, "blocks": len(blocks), "chars": extraction.total_chars,
            "truncated": extraction.truncated, "candidates": len(candidates), "matched": len(items),
            "mode": mode, "match_ratio": ratio, "warning": warning, "has_url": bool(url),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        })
        return PageMatchResult(mode, ratio, warning, items, extraction.total_chars, extraction.truncated,
                               full_text)

    async def _verify(
        self, user_id: uuid.UUID, query: str, candidates: list[Block],
    ) -> tuple[set[str], str | None]:
        """Lease 2: LLM thẩm định. Trả (id được xác nhận, warning). Mọi lỗi → (∅, VERIFY_UNAVAILABLE)."""
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
                    return set(), VERIFY_UNAVAILABLE
                await quota.commit(lease, result.usage.total)
        except QuotaExceeded:  # chỉ reserve() trong leased() ném lỗi này
            log.info("page_match_verify_skipped", extra={"reason": "quota"})
            return set(), VERIFY_UNAVAILABLE
        try:
            return parse_verdicts(result.text, {b.id for b in candidates}), None
        except VerdictParseError as e:
            log.warning("page_match_verify_unparsable", extra={"reason": str(e)})
            return set(), VERIFY_UNAVAILABLE
