"""Business Layer — Semantic Search Service: job index ghi chú (chunk → embed → lưu pgvector) — SDS §5.1.2.

Bảng quyết định:
  note không tồn tại / đã xoá  → xoá chunk
  nội dung không đổi           → chỉ cập nhật folder_id, READY (không tốn quota)
  hết quota                    → SKIPPED (không trừ quota — "silent skip")
  AI lỗi tạm thời              → giải phóng quota, raise để job retry (giữ PROCESSING)
  AI lỗi vĩnh viễn / hết lượt  → FAILED (người dùng bấm "Thử lại" → /notes/{id}/reindex)
"""

import hashlib
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import QuotaExceeded
from quickassist.business.notes import get_note_for_indexing, set_index_status
from quickassist.business.quota import QuotaService
from quickassist.business.semantic_search.chunking import chunk_text
from quickassist.data.models.note_chunk import NoteChunk
from quickassist.data_access.repositories.note_chunk_repository import NoteChunkRepository
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.jobs import SEMANTIC_SEARCH_INDEX_NOTE, job_handler
from quickassist.infrastructure.logging import get_logger
from quickassist.infrastructure.openai import get_ai_provider
from quickassist.infrastructure.openai.base import AIProviderError, estimate_tokens

log = get_logger(__name__)


@job_handler(SEMANTIC_SEARCH_INDEX_NOTE)
async def index_note(session: AsyncSession, payload: dict[str, Any]) -> None:
    note_id = uuid.UUID(payload["note_id"])
    is_last_attempt = payload.get("_attempt", 1) >= payload.get("_max_attempts", 1)
    repo = NoteChunkRepository(session)

    note = await get_note_for_indexing(session, note_id)
    if note is None or note.is_deleted:
        await repo.delete_for_note(note_id)
        return

    content_hash = hashlib.sha256(note.content.encode()).hexdigest()
    if await repo.content_hash_of(note_id) == content_hash:
        await repo.set_folder(note_id, note.folder_id)
        await set_index_status(session, note_id, status="READY", index_rev=note.index_rev)
        return

    cfg = get_settings()
    pieces = chunk_text(note.content, size=cfg.chunk_size_chars, overlap=cfg.chunk_overlap_chars)
    ai = get_ai_provider()

    async with QuotaService.open() as quota:
        try:
            lease = await quota.reserve(
                note.user_id, "embed_note", sum(estimate_tokens(p) for p in pieces),
                request_id=f"embed_note:{note_id}:{note.index_rev}",
            )
        except QuotaExceeded:
            await set_index_status(session, note_id, status="SKIPPED", index_rev=note.index_rev,
                                   error="QUOTA_EXCEEDED")
            return
        try:
            emb = await ai.embed(pieces)
        except AIProviderError as e:
            await quota.release(lease)
            if e.retryable and not is_last_attempt:
                raise  # worker retry với backoff; note vẫn PROCESSING
            await set_index_status(session, note_id, status="FAILED", index_rev=note.index_rev,
                                   error="AI_PROVIDER_ERROR")
            return

        await repo.replace_for_note(
            [NoteChunk(note_id=note_id, user_id=note.user_id, folder_id=note.folder_id, ordinal=i,
                       text=t, content_hash=content_hash, embedding=v, model=emb.model)
             for i, (t, v) in enumerate(zip(pieces, emb.vectors, strict=True))],
            note_id,
        )
        await set_index_status(session, note_id, status="READY", index_rev=note.index_rev)
        await session.commit()  # chunk + trạng thái bền vững TRƯỚC khi chốt quota
        await quota.commit(lease, emb.usage.total)
    log.info("note_indexed", extra={"note_id": str(note_id), "chunks": len(pieces)})
