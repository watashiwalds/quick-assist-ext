"""Business Layer — RAGService (SDS Hình 1, §5.1.6): hỏi đáp trên ghi chú cá nhân, trả lời từng phần (stream).

Luồng (task X01):
  1. prepare(): kiểm tra đầu vào → SemanticSearchService.search_sources() lấy ngữ cảnh theo hợp đồng
     source-first của CHÍNH user (5 nguồn × notes_per_source note × 1 chunk tốt nhất/note,
     quota_operation="rag_retrieve") → dựng prompt (system + tối đa 5 cặp hỏi–đáp gần nhất + nguồn)
     → QuotaService.reserve ước lượng "chat".
     Lỗi ở bước này (hết quota, đầu vào sai) trả HTTP lỗi bình thường.
  2. stream(): phát sự kiện `sources` → các `delta` → `done` (hoặc `error`). Kết thúc, lỗi giữa chừng hay bị
     ngắt (người dùng bấm Dừng → client huỷ request) đều chốt quota theo phần ĐÃ sinh (ADR-0009).

Lịch sử hội thoại do client gửi kèm mỗi lần hỏi (ADR-0012) → server không lưu nội dung chat.
stream() KHÔNG dùng session của request: StreamingResponse chạy sau khi handler trả về.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from quickassist.business.common.exceptions import AppError, PayloadTooLarge
from quickassist.business.quota import QuotaLease, QuotaService
from quickassist.business.rag.prompts import NO_CONTEXT_ANSWER, chat_messages
from quickassist.business.semantic_search import ScoredNote, ScoredSource, SemanticSearchService
from quickassist.infrastructure.config import get_settings
from quickassist.infrastructure.logging import get_logger
from quickassist.infrastructure.openai.base import AIProvider, ChatMessage, estimate_tokens

log = get_logger(__name__)

CHAT_MAX_OUTPUT_TOKENS = 800
# RAG cố định 5 nguồn (UX plan §5.2.4); số note/nguồn theo cấu hình (mặc định 3).
CHAT_MAX_SOURCES = 5
MAX_QUESTION_CHARS = 2_000
MAX_HISTORY_PAIRS = 5
MAX_HISTORY_MESSAGE_CHARS = 2_000
SNIPPET_CHARS = 240


@dataclass(frozen=True)
class ChatSource:
    index: int  # số trích dẫn [n] trong câu trả lời — đánh số LIÊN TỤC theo note
    source_index: int  # nhóm nguồn 1..5 (source_rank của nguồn chứa note này)
    source_domain: str | None  # domain của nguồn; None = "Không rõ nguồn"
    note_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str | None
    url: str | None
    snippet: str


@dataclass(frozen=True)
class ChatEvent:
    type: str  # sources | delta | done | error
    data: Any


@dataclass(frozen=True)
class PreparedChat:
    user_id: uuid.UUID
    messages: list[ChatMessage]
    sources: list[ChatSource]
    lease: QuotaLease | None  # None = không có ngữ cảnh → không gọi LLM, không giữ quota
    prompt_tokens_estimate: int = 0


def clean_history(history: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Giữ tối đa 5 cặp hỏi–đáp gần nhất, bỏ lượt rỗng/vai trò lạ, cắt nội dung quá dài.

    Lượt "assistant" do client gửi chỉ ảnh hưởng hội thoại của chính người đó → không cần tin cậy hơn thế.
    """
    turns = [(r, c.replace("\x00", "").strip()[:MAX_HISTORY_MESSAGE_CHARS])
             for r, c in history if r in ("user", "assistant")]
    turns = [(r, c) for r, c in turns if c]
    turns = turns[-MAX_HISTORY_PAIRS * 2:]
    while turns and turns[0][0] != "user":  # bắt đầu bằng lượt người dùng
        turns.pop(0)
    return turns


def clip_context(notes: Sequence[tuple[ScoredSource, ScoredNote]], max_chars: int,
                 ) -> list[tuple[ScoredSource, ScoredNote]]:
    """Trần ngữ cảnh (CHAT_CONTEXT_MAX_CHARS): giữ note xếp CAO trước; vượt → bỏ các note thấp.

    Note tốt nhất luôn được giữ (chunk ≤ ~1200 ký tự nên không thể vượt trần một mình).
    """
    kept: list[tuple[ScoredSource, ScoredNote]] = []
    used = 0
    for i, (src, note) in enumerate(notes):
        if i > 0 and used + len(note.chunk_text) > max_chars:
            break
        kept.append((src, note))
        used += len(note.chunk_text)
    return kept


class RAGService:
    def __init__(self, session: AsyncSession, ai: AIProvider) -> None:
        self.s = session
        self.ai = ai

    async def prepare(
        self, user_id: uuid.UUID, question: str, *, history: Sequence[tuple[str, str]] = (),
        folder_id: uuid.UUID | None = None,
    ) -> PreparedChat:
        question = question.replace("\x00", "").strip()
        if not question:
            raise AppError("Câu hỏi trống", code="CHAT_INPUT_INVALID")
        if len(question) > MAX_QUESTION_CHARS:
            raise PayloadTooLarge("Câu hỏi quá dài", code="CHAT_INPUT_TOO_LONG")

        cfg = get_settings()
        grouped = await SemanticSearchService(self.s, self.ai).search_sources(
            user_id, question, folder_id=folder_id, max_sources=CHAT_MAX_SOURCES,
            notes_per_source=cfg.rag_notes_per_source, quota_operation="rag_retrieve")
        # Phẳng theo thứ hạng: (nguồn, note) theo nguồn rồi note trong nguồn; mỗi note 1 chunk tốt nhất.
        ranked = [(src, n) for src in grouped for n in src.notes]
        ranked = clip_context(ranked, cfg.chat_context_max_chars)
        sources = [
            ChatSource(i, src.source_rank, src.domain, n.note_id, n.chunk_id, n.title, n.url, n.snippet)
            for i, (src, n) in enumerate(ranked, start=1)
        ]
        if not sources:
            return PreparedChat(user_id, [], [], None)

        # Prompt gom theo nguồn, giữ thứ hạng: [(domain, [(số [n], tiêu đề, toàn văn chunk)])]
        domain_by_rank = {src.source_rank: src.domain for src, _ in ranked}
        by_rank: dict[int, list[tuple[int, str | None, str]]] = {}
        for s, (_, n) in zip(sources, ranked, strict=True):
            by_rank.setdefault(s.source_index, []).append((s.index, s.title, n.chunk_text))
        source_groups = [(domain_by_rank[rank], by_rank[rank]) for rank in sorted(by_rank)]
        messages = chat_messages(question, clean_history(history), source_groups)
        prompt_tokens = sum(estimate_tokens(m.content) for m in messages)
        async with QuotaService.open() as quota:
            lease = await quota.reserve(user_id, "chat", prompt_tokens + CHAT_MAX_OUTPUT_TOKENS,
                                        f"chat:{user_id}:{uuid.uuid4()}")
        return PreparedChat(user_id, messages, sources, lease, prompt_tokens)

    async def stream(self, prepared: PreparedChat) -> AsyncIterator[ChatEvent]:
        yield ChatEvent("sources", [
            {"index": s.index, "source_index": s.source_index, "source_domain": s.source_domain,
             "note_id": str(s.note_id), "chunk_id": str(s.chunk_id),
             "title": s.title, "url": s.url, "snippet": s.snippet}
            for s in prepared.sources
        ])
        if prepared.lease is None:
            yield ChatEvent("delta", NO_CONTEXT_ANSWER)
            yield ChatEvent("done", {"tokens_used": 0})
            return

        generated: list[str] = []
        usage_total: int | None = None
        failed: Exception | None = None
        try:
            async for chunk in self.ai.stream(prepared.messages, max_tokens=CHAT_MAX_OUTPUT_TOKENS):
                if chunk.usage is not None:
                    usage_total = chunk.usage.total
                if chunk.delta:
                    generated.append(chunk.delta)
                    yield ChatEvent("delta", chunk.delta)
        # AIProviderError hoặc lỗi mạng giữa chừng. Huỷ/ngắt là BaseException → không bị bắt ở đây.
        except Exception as e:
            failed = e
        finally:
            # Chạy cả khi client ngắt kết nối (Dừng) → generator bị huỷ/đóng giữa chừng.
            tokens = self._tokens_used(prepared, generated, usage_total)
            with anyio.CancelScope(shield=True):
                await self._settle(prepared.lease, tokens)
            log.info("chat_done", extra={"tokens": tokens, "sources": len(prepared.sources),
                                         "completed": usage_total is not None, "failed": failed is not None})

        if failed is not None:
            yield ChatEvent("error", {"code": "AI_UNAVAILABLE",
                                      "message": "Dịch vụ AI tạm thời không khả dụng, hãy thử lại sau"})
            return
        yield ChatEvent("done", {"tokens_used": tokens})

    @staticmethod
    def _tokens_used(prepared: PreparedChat, generated: list[str], usage_total: int | None) -> int:
        if usage_total is not None:
            return usage_total
        if not generated:  # lỗi/ngắt trước khi sinh chữ nào → không trừ
            return 0
        # Bị ngắt giữa chừng: provider chưa kịp báo usage → ước lượng prompt + phần đã sinh.
        return prepared.prompt_tokens_estimate + estimate_tokens("".join(generated))

    @staticmethod
    async def _settle(lease: QuotaLease, tokens: int) -> None:
        async with QuotaService.open() as quota:
            if tokens > 0:
                await quota.commit(lease, tokens)
            else:
                await quota.release(lease)
