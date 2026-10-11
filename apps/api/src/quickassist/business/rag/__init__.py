"""Business Layer — RAG Service (SDS Hình 1 "RAGService", §5.1.6): hỏi đáp trên ghi chú, trả lời dạng stream.

Không sở hữu bảng nào: ngữ cảnh lấy qua SemanticSearchService, hạn mức qua QuotaService; lịch sử hội thoại
do client gửi kèm (ADR-0012).
"""

from quickassist.business.rag.rag_service import ChatEvent, ChatSource, PreparedChat, RAGService

__all__ = ["ChatEvent", "ChatSource", "PreparedChat", "RAGService"]
