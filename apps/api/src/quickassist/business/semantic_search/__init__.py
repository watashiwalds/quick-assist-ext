"""Business Layer — Semantic Search Service (SDS Hình 1 "SemanticSearchService", §5.1.3).

Sở hữu bảng: note_chunks. Xử lý job SEMANTIC_SEARCH_INDEX_NOTE (indexing_job.py — được
worker.py nạp). Public API: chỉ import từ package này.
"""

from quickassist.business.semantic_search.contracts import SearchResult
from quickassist.business.semantic_search.grouping import ScoredNote, ScoredSource, group_by_source
from quickassist.business.semantic_search.rebuild import RebuildPlan, start_rebuild
from quickassist.business.semantic_search.semantic_search_service import SemanticSearchService

__all__ = [
    "RebuildPlan", "ScoredNote", "ScoredSource", "SearchResult", "SemanticSearchService",
    "group_by_source", "start_rebuild",
]
