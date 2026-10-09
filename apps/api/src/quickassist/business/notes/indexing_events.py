"""Business Layer — Notes Service báo cho Semantic Search Service rằng note đã đổi.

Giao tiếp qua job (không import semantic_search) → không phụ thuộc vòng giữa 2 service.
Job được ghi CÙNG transaction với thay đổi note (outbox, ADR-0003).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.infrastructure.jobs import SEMANTIC_SEARCH_INDEX_NOTE, enqueue


async def publish_note_changed(session: AsyncSession, note_id: uuid.UUID) -> None:
    await enqueue(session, SEMANTIC_SEARCH_INDEX_NOTE, {"note_id": str(note_id)},
                  dedupe_key=f"{SEMANTIC_SEARCH_INDEX_NOTE}:{note_id}")
