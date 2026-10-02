"""Business Layer — Semantic Search Service (SDS Hình 1 "SemanticSearchService", §5.1.3).

Sở hữu bảng: note_chunks. Xử lý job SEMANTIC_SEARCH_INDEX_NOTE (indexing_job.py — được
worker.py nạp). Public API: chỉ import từ package này.
"""

from quickassist.business.semantic_search.semantic_search_service import SearchResult, SemanticSearchService

__all__ = ["SearchResult", "SemanticSearchService"]
