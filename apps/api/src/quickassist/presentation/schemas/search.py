"""Presentation Layer — DTO request/response (search).

Contract source-first (Phase 1, UX plan §6.1): kết quả gom theo NGUỒN (domain),
mỗi nguồn chứa các ghi chú đã đạt ngưỡng tin cậy OR (similarity >= 0.5 HOẶC RRF >= 0.03).
"""

import uuid

from pydantic import Field

from quickassist.presentation.schemas.common import ApiModel


class SearchIn(ApiModel):
    query: str = Field(min_length=1, max_length=1000)
    folder_id: uuid.UUID | None = None
    # Số nguồn (domain) tối đa trả về — mặc định 5; mỗi nguồn trả tối đa
    # search_notes_per_source note (Thư viện hiển thị 3 + "Xem thêm").
    max_sources: int = Field(default=5, ge=1, le=20)


class SearchNoteOut(ApiModel):
    note_id: uuid.UUID
    title: str | None
    url: str | None
    summary: str | None  # tóm tắt AI đã lưu của note (nếu có) — summary-first
    snippet: str  # chunk tốt nhất của note, đã chuẩn hoá khoảng trắng
    score: float  # RRF tốt nhất của note (khớp cả vector lẫn từ khoá)
    similarity: float  # cosine 0..1 tốt nhất của note (khớp ngữ nghĩa)
    # D2 — vị trí part trong tài liệu dài (note cũ: 0/1).
    part_index: int
    part_count: int


class SearchSourceOut(ApiModel):
    domain: str | None  # None = nhóm "Không rõ nguồn" (note không có URL), luôn xếp cuối
    label: str  # domain, title tài liệu, hoặc "Không rõ nguồn"
    source_rank: int  # 1..N theo thứ hạng nguồn
    note_count: int  # tổng số note/part đạt ngưỡng trong nguồn (trước khi cắt notes_per_source)
    notes: list[SearchNoteOut]
    # D2 — nguồn là tài liệu (gom theo document_id) hay note web cũ (gom theo domain).
    document_id: uuid.UUID | None
    source_type: str  # selection | document


class SearchOut(ApiModel):
    sources: list[SearchSourceOut]
