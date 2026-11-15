"""Rebuild chỉ mục ngữ nghĩa của một user khi fingerprint embedding đổi (ADR-0016 §4.6).

KHÔNG xoá chunk cũ hàng loạt (quyết định 14/11/2026): nhánh từ khoá của hybrid search cũng
đọc bảng note_chunks → xoá hết = MẤT search hoàn toàn trong lúc rebuild, mâu thuẫn với
dialog xác nhận. Thay vào đó:
  1. notes chuyển PROCESSING + index_rev+1 (job cũ không ghi đè trạng thái);
  2. enqueue job index_note cho từng note, payload kèm embedding_fingerprint MỚI;
  3. fingerprint guard trong indexing_job bỏ job của cấu hình cũ;
  4. chunk cũ của từng note được thay khi job tới lượt (replace_for_note xoá+ghi nguyên tử).
Search vẫn trả kết quả trong lúc rebuild (chunk cũ còn đó, tự thay dần theo note).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.notes import mark_user_notes_processing
from quickassist.infrastructure.jobs import SEMANTIC_SEARCH_INDEX_NOTE, enqueue_many
from quickassist.infrastructure.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class RebuildPlan:
    notes: int
    fingerprint: str


async def start_rebuild(session: AsyncSession, user_id: uuid.UUID, *, fingerprint: str) -> RebuildPlan:
    """Đánh dấu + enqueue lại toàn bộ note của user với fingerprint mới. Commit tại đây
    (mark + enqueue phải cùng transaction — outbox pattern)."""
    note_ids = await mark_user_notes_processing(session, user_id)
    await enqueue_many(
        session, SEMANTIC_SEARCH_INDEX_NOTE,
        [{"note_id": str(nid), "embedding_fingerprint": fingerprint} for nid in note_ids],
        dedupe_keys=[f"{SEMANTIC_SEARCH_INDEX_NOTE}:{nid}:{fingerprint[:12]}" for nid in note_ids],
    )
    # Chunk cũ của user KHÔNG bị xoá ở đây — giữ để search không bị gián đoạn (xem docstring).
    await session.commit()
    log.info("rebuild_started", extra={"user_id": str(user_id), "notes": len(note_ids)})
    return RebuildPlan(notes=len(note_ids), fingerprint=fingerprint)
