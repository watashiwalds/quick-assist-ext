"""Phase 1 — grouping source-first: gom domain, ngưỡng OR, xếp hạng nguồn, top-N, cap note/nguồn.

Thuần logic (grouping.py không I/O) → chạy không cần DB.
"""

import uuid

from quickassist.business.semantic_search.contracts import SearchResult
from quickassist.business.semantic_search.grouping import UNKNOWN_LABEL, group_by_source

FOLDER = uuid.uuid4()


def hit(note_id: uuid.UUID, *, domain: str | None = "a.example", similarity: float = 0.0,
        score: float = 0.0, text: str = "nội dung chunk", title: str | None = "Tiêu đề",
        chunk_id: uuid.UUID | None = None) -> SearchResult:
    return SearchResult(chunk_id or uuid.uuid4(), note_id, text, score, title,
                        f"https://{domain}/x" if domain else None, FOLDER,
                        similarity, domain, None)


def by_label(sources, label: str):
    return next(s for s in sources if s.label == label)


def test_group_notes_by_domain_and_rank_sources_by_best_similarity() -> None:
    n1, n2, n3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    results = [
        hit(n1, domain="a.example", similarity=0.4, score=0.02),
        hit(n1, domain="a.example", similarity=0.7, score=0.05),  # chunk tốt nhất của n1
        hit(n2, domain="a.example", similarity=0.6, score=0.04),
        hit(n3, domain="b.example", similarity=0.9, score=0.01),
    ]
    sources = group_by_source(results, max_sources=5, notes_per_source=10,
                              min_similarity=0.5, min_score=0.03)
    assert [s.domain for s in sources] == ["b.example", "a.example"]  # b có sim max 0.9
    a = by_label(sources, "a.example")
    assert a.source_rank == 2 and a.note_count == 2
    assert a.notes[0].note_id == n1 and a.notes[0].similarity == 0.7  # chunk tốt nhất thắng
    assert a.notes[0].score == 0.05  # max RRF độc lập với chunk đại diện
    assert "nội dung chunk" in a.notes[0].snippet


def test_note_passes_threshold_with_or_not_and() -> None:
    n_sim, n_rrf, n_none = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    results = [
        hit(n_sim, similarity=0.55, score=0.01),   # chỉ cosine đạt → ĐẠT
        hit(n_rrf, similarity=0.20, score=0.04),   # chỉ RRF đạt → ĐẠT
        hit(n_none, similarity=0.49, score=0.029),  # cả hai dưới ngưỡng → LOẠI
    ]
    sources = group_by_source(results, max_sources=5, notes_per_source=10,
                              min_similarity=0.5, min_score=0.03)
    got = {n.note_id for s in sources for n in s.notes}
    assert got == {n_sim, n_rrf} and n_none not in got


def test_notes_without_domain_group_last_with_label() -> None:
    n1, n2 = uuid.uuid4(), uuid.uuid4()
    results = [
        hit(n1, domain=None, similarity=0.9, score=0.05),  # sim cao nhất nhưng không rõ nguồn
        hit(n2, domain="b.example", similarity=0.6, score=0.04),
    ]
    sources = group_by_source(results, max_sources=5, notes_per_source=10,
                              min_similarity=0.5, min_score=0.03)
    assert [s.label for s in sources] == ["b.example", UNKNOWN_LABEL]
    assert sources[-1].domain is None and sources[-1].notes[0].note_id == n1


def test_tie_break_by_rrf_then_by_passing_note_count() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    results = [
        hit(a, domain="a.example", similarity=0.6, score=0.02),
        hit(b, domain="b.example", similarity=0.6, score=0.05),  # hoà sim → RRF cao thắng
        hit(c, domain="c.example", similarity=0.6, score=0.05),
        hit(uuid.uuid4(), domain="c.example", similarity=0.6, score=0.04),  # hoá nữa → nhiều note thắng
    ]
    sources = group_by_source(results, max_sources=5, notes_per_source=10,
                              min_similarity=0.5, min_score=0.03)
    assert [s.domain for s in sources] == ["c.example", "b.example", "a.example"]


def test_top_sources_and_per_source_cap() -> None:
    ids = [uuid.uuid4() for _ in range(8)]
    results = [hit(ids[i], domain=f"d{i}.example", similarity=0.5 + i * 0.01, score=0.04)
               for i in range(8)]  # 8 nguồn, sim tăng dần theo i
    sources = group_by_source(results, max_sources=5, notes_per_source=3,
                              min_similarity=0.5, min_score=0.03)
    assert len(sources) == 5
    assert [s.domain for s in sources] == [f"d{i}.example" for i in range(7, 2, -1)]
    assert [s.source_rank for s in sources] == [1, 2, 3, 4, 5]


def test_note_count_is_total_before_trim() -> None:
    n1 = uuid.uuid4()
    same_domain = "one.example"
    results = [hit(n1, domain=same_domain, similarity=0.6, score=0.05, text=f"chunk {i}")
               for i in range(10)]  # 1 note nhiều chunk → note_count tính NOTE, không phải chunk
    extra = [hit(uuid.uuid4(), domain=same_domain, similarity=0.55, score=0.04)
             for _ in range(7)]  # 7 note nữa cùng nguồn
    sources = group_by_source(results + extra, max_sources=5, notes_per_source=3,
                              min_similarity=0.5, min_score=0.03)
    s = sources[0]
    assert s.note_count == 8 and len(s.notes) == 3  # trả 3 note, tổng 8


def test_empty_input_returns_empty_list() -> None:
    assert group_by_source([], max_sources=5, notes_per_source=3,
                           min_similarity=0.5, min_score=0.03) == []


def test_single_hit_forms_single_source() -> None:
    # Note đã xoá bị loại ở service (không có brief) — grouping chỉ nhận kết quả đã lọc.
    assert group_by_source([hit(uuid.uuid4(), similarity=0.9)], max_sources=5, notes_per_source=3,
                           min_similarity=0.5, min_score=0.03)[0].note_count == 1


def test_snippet_is_whitespace_normalized_and_trimmed() -> None:
    n = uuid.uuid4()
    long = " ".join(["từ"] * 500)
    sources = group_by_source([hit(n, similarity=0.6, text=long)], max_sources=5,
                              notes_per_source=3, min_similarity=0.5, min_score=0.03)
    snippet = sources[0].notes[0].snippet
    assert len(snippet) == 240 and "  " not in snippet
