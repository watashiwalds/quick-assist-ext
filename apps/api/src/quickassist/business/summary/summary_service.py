"""Business Layer — SummaryService (SDS Hình 1, §5.1.4): tóm tắt văn bản/ghi chú bằng AI.

Trả về PREVIEW — không ghi DB. Người dùng xác nhận → client gọi PUT /notes/{id}/summary
(Notes Service sở hữu cột summary_text).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import AppError, NotFound, PayloadTooLarge, UpstreamError
from quickassist.business.notes import get_note_content
from quickassist.business.quota import QuotaService
from quickassist.business.summary.prompts import summary_messages
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.logging import get_logger
from quickassist.infrastructure.openai.base import AIProvider, AIProviderError, estimate_tokens

log = get_logger(__name__)

SUMMARY_MAX_OUTPUT_TOKENS = 600


@dataclass(frozen=True)
class SummaryPreview:
    summary: str
    tokens_used: int
    request_id: str


class SummaryService:
    def __init__(self, session: AsyncSession, ai: AIProvider) -> None:
        self.s = session
        self.ai = ai

    async def summarize(
        self, user_id: uuid.UUID, *, text: str | None, note_id: uuid.UUID | None, request_id: str
    ) -> SummaryPreview:
        if (text is None) == (note_id is None):
            raise AppError("Cần đúng một trong hai: text hoặc note_id", code="SUMMARY_INPUT_INVALID")
        if note_id is not None:
            text = await get_note_content(self.s, user_id, note_id)
            if text is None:
                raise NotFound("Không tìm thấy ghi chú", code="NOTE_NOT_FOUND")
        assert text is not None
        if len(text) > get_settings().max_summary_input_chars:
            raise PayloadTooLarge("Văn bản quá dài để tóm tắt", code="SUMMARY_INPUT_TOO_LONG")

        messages = summary_messages(text)
        estimate = sum(estimate_tokens(m.content) for m in messages) + SUMMARY_MAX_OUTPUT_TOKENS
        async with QuotaService.open() as quota:
            lease = await quota.reserve(user_id, "summary", estimate, f"summary:{request_id}")
            try:
                result = await self.ai.complete(messages, max_tokens=SUMMARY_MAX_OUTPUT_TOKENS)
            except AIProviderError as e:
                await quota.release(lease)
                raise UpstreamError("Dịch vụ AI tạm thời không khả dụng", code="AI_UNAVAILABLE") from e
            await quota.commit(lease, result.usage.total)
        log.info("summary_done", extra={"tokens": result.usage.total})
        return SummaryPreview(result.text.strip(), result.usage.total, request_id)
