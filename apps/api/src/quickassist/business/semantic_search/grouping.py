"""Business Layer — gom kết quả truy xuất theo NGUỒN (source-first, Phase 1 + D2).

"nguồn" = ``document_id`` nếu note thuộc tài liệu nhiều part, ngược lại là website/domain
gốc của ghi chú (``Note.domain``, hostname của URL). Ghi chú cũ không có document_id vẫn
gom theo domain như trước; ghi chú không có domain vào nhóm "Không rõ nguồn", luôn xếp cuối.

Hợp đồng dùng chung cho Thư viện và RAG (tránh hai luồng lọc/nhóm lệch nhau):
  1. Gom chunk theo note — similarity/RRF của note = tốt nhất trong các chunk của note.
  2. Lọc note theo ngưỡng OR: ``similarity >= min_similarity`` (cosine, khớp ngữ nghĩa)
     HOẶC ``score >= min_score`` (RRF, khớp cả vector lẫn từ khoá). Không dùng AND:
     RRF một mình loại câu hỏi diễn đạt lại chỉ khớp ngữ nghĩa; cosine một mình loại
     khớp từ khoá chính xác.
  3. Xếp hạng nguồn: ``source_score = max(similarity của các note)``, tie-break bằng
     max(RRF), rồi số note đạt ngưỡng.
  4. Lấy top ``max_sources`` nguồn, mỗi nguồn tối đa ``notes_per_source`` note/part.

Thuần logic, không I/O → unit test độc lập với DB.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace

from quickassist.business.semantic_search.contracts import SearchResult

UNKNOWN_LABEL = "Không rõ nguồn"
DOCUMENT_LABEL = "Tài liệu"
SNIPPET_CHARS = 240


@dataclass(frozen=True)
class ScoredNote:
    """Một ghi chú/part đã chấm điểm sau grouping — đại diện bởi chunk tốt nhất của nó."""

    note_id: uuid.UUID
    title: str | None
    url: str | None
    summary: str | None
    snippet: str  # chunk tốt nhất, đã chuẩn hoá khoảng trắng
    score: float  # RRF tốt nhất trong các chunk của note
    similarity: float  # cosine tốt nhất trong các chunk của note
    # Dữ liệu nội bộ cho RAG (không nằm trong contract API):
    chunk_id: uuid.UUID
    chunk_text: str  # toàn văn chunk tốt nhất
    folder_id: uuid.UUID
    # D2 — part của tài liệu dài (note cũ: None / 0 / 1 / selection).
    document_id: uuid.UUID | None = None
    part_index: int = 0
    part_count: int = 1
    source_type: str = "selection"


@dataclass(frozen=True)
class ScoredSource:
    domain: str | None
    label: str  # domain, title tài liệu, hoặc "Không rõ nguồn"
    source_rank: int  # 1..N theo thứ hạng nguồn
    note_count: int  # số note/part đạt ngưỡng trong nguồn (trước khi cắt notes_per_source)
    notes: list[ScoredNote]  # đã xếp hạng, đã cắt theo notes_per_source
    document_id: uuid.UUID | None = None
    source_type: str = "selection"


def group_by_source(
    results: Sequence[SearchResult], *, max_sources: int, notes_per_source: int,
    min_similarity: float, min_score: float, snippet_chars: int = SNIPPET_CHARS,
) -> list[ScoredSource]:
    """Gom kết quả truy xuất phẳng thành danh sách nguồn đã xếp hạng (xem docstring module)."""
    # 1. Gom chunk theo note, giữ max(similarity), max(RRF) và chunk đại diện tốt nhất.
    notes: dict[uuid.UUID, _NoteAccumulator] = {}
    for r in results:
        acc = notes.get(r.note_id)
        if acc is None:
            acc = notes[r.note_id] = _NoteAccumulator(r)
        acc.offer(r)

    # 2. Ngưỡng OR ở mức note + 3. gom theo document_id nếu có, fallback domain.
    sources: dict[tuple[uuid.UUID | None, str | None], list[ScoredNote]] = {}
    for note_id, acc in notes.items():
        if acc.max_similarity < min_similarity and acc.max_score < min_score:
            continue  # không đạt ngưỡng tin cậy → loại
        chunk = acc.best_chunk()
        sources.setdefault((acc.document_id, acc.domain), []).append(ScoredNote(
            note_id, acc.title, acc.url, acc.summary,
            " ".join(chunk.text.split())[:snippet_chars],
            acc.max_score, acc.max_similarity, chunk.chunk_id, chunk.text, acc.folder_id,
            document_id=acc.document_id, part_index=acc.part_index,
            part_count=acc.part_count, source_type=acc.source_type,
        ))

    out: list[ScoredSource] = []
    for (document_id, domain), group in sources.items():
        group.sort(key=lambda n: (-n.similarity, -n.score, n.part_index, str(n.note_id)))
        is_document = document_id is not None
        # Tên tài liệu nằm ở mọi part (metadata lan sang document) → lấy title đầu tiên có.
        label = (
            next((n.title for n in group if n.title), DOCUMENT_LABEL)
            if is_document else (domain or UNKNOWN_LABEL)
        )
        out.append(ScoredSource(
            domain=domain,
            label=label,
            source_rank=0,  # gán sau khi xếp hạng
            note_count=len(group),
            notes=group[:max(1, notes_per_source)],
            document_id=document_id,
            source_type="document" if is_document else "selection",
        ))

    # 4. Xếp hạng nguồn: max similarity → max RRF → số note đạt; "Không rõ nguồn" cũ luôn cuối.
    def source_key(s: ScoredSource) -> tuple[int, float, float, int, str, str]:
        legacy_unknown = s.document_id is None and s.domain is None
        return (
            1 if legacy_unknown else 0,
            -max(n.similarity for n in s.notes),
            -max(n.score for n in s.notes),
            -s.note_count,
            s.label,
            str(s.document_id or ""),  # deterministic khi mọi tiêu chí hoà
        )

    ranked = sorted(out, key=source_key)[:max(1, max_sources)]
    return [replace(source, source_rank=rank) for rank, source in enumerate(ranked, start=1)]


class _NoteAccumulator:
    """Gom các chunk của cùng một note: max 2 thang điểm + chunk đại diện (sim → RRF)."""

    __slots__ = ("domain", "title", "url", "summary", "folder_id", "document_id", "part_index",
                 "part_count", "source_type", "max_similarity", "max_score", "_best")

    def __init__(self, first: SearchResult) -> None:
        self.domain = first.note_domain
        self.title = first.note_title
        self.url = first.note_url
        self.summary = first.note_summary
        self.folder_id = first.folder_id
        self.document_id = first.note_document_id
        self.part_index = first.note_part_index
        self.part_count = first.note_part_count
        self.source_type = first.note_source_type
        self.max_similarity = first.similarity
        self.max_score = first.score
        self._best = first

    def offer(self, r: SearchResult) -> None:
        self.max_similarity = max(self.max_similarity, r.similarity)
        self.max_score = max(self.max_score, r.score)
        if (r.similarity, r.score) > (self._best.similarity, self._best.score):
            self._best = r

    def best_chunk(self) -> SearchResult:
        return self._best
