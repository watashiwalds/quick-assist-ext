"""Business Layer — DTO của SemanticSearchService dùng chéo giữa các module trong package
(tránh import vòng service ↔ grouping). Trả dữ liệu bất biến, không trả entity ORM."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """Một chunk truy xuất được, đã ghép thông tin note (brief) để grouping/API dùng."""

    chunk_id: uuid.UUID
    note_id: uuid.UUID
    text: str
    score: float
    note_title: str | None
    note_url: str | None
    folder_id: uuid.UUID
    similarity: float  # cosine 0..1 của chunk này với truy vấn
    note_domain: str | None  # nguồn gốc ghi chú (hostname của URL); None = không rõ nguồn
    note_summary: str | None  # tóm tắt AI đã lưu của note (nếu có)
