"""§4 — Hàm đánh giá hiệu suất (chất lượng + hiệu năng).

Toàn bộ hàm ở đây là THUẦN (không I/O, không gọi mạng): vào là bản ghi case
(dataclass bên dưới), ra là chỉ số. Tách riêng để:
  - dễ test/unit-test phần "cách chấm" không lẫn phần "cách gọi hệ thống";
  - trình bày minh chứng: mỗi metric có đúng một nơi định nghĩa.

Quy ước:
  - Mọi so khớp văn bản đi qua normalize_text() (bỏ dấu tiếng Việt, gồm đ→d).
  - Chất lượng: chấm theo nhãn gold trong dataset (không tự sinh nhãn).
  - Hiệu năng: độ trễ đo ở lớp HTTP thật (không phải vòng lặp in-process).

METRICS_VERSION = 3 — thay đổi so với bản smoke đầu tiên:
  - Search: API mới trả kết quả NHÓM THEO NGUỒN (``sources[].notes[]``) thay
    vì ``items[]`` phẳng; top-k được định nghĩa là k NOTE đầu sau khi phẳng
    theo thứ hạng nguồn rồi note trong nguồn (API_REFERENCE §9.1).
  - numbers_of(): bỏ citation [n], chuẩn hoá số (1,5 → 1.5; 1.000 → 1000;
    âm 18 → -18), không lấy chữ số dính trong mã (CO2).
  - token_f1(): đếm đa tập (Counter) thay vì giao tập.
  - _pct(): nearest-rank đúng (ceil(n*q)).
  - RAG: mẫu số citation là mọi câu answerable hoàn thành; câu không trích dẫn
    = 0; lỗi AI tách khỏi chất lượng (không còn bị tính là "trả lời bừa").
  - PageMatch: tách quality/fallback, top-k, Span Coverage theo ký tự,
    Full-page F1; không còn thưởng "trả cả trang" như precision 1.0.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from difflib import SequenceMatcher

METRICS_VERSION = 3
RAW_SCHEMA_VERSION = 3

# ============================================================ Chuẩn hoá văn bản


def normalize_text(text: str) -> str:
    """Chuẩn hoá so khớp tiếng Việt: đ→d, bỏ dấu, lower, gọn khoảng trắng."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def tokenize(text: str) -> list[str]:
    return [w for w in re.split(r"\W+", normalize_text(text)) if w]


# ============================================================ Số & trích dẫn

# Số có thể đứng riêng: không lấy chữ số nằm trong mã chữ-số (CO2, H2O, PET2)
# và không lấy chữ số dính liền đơn vị chữ (5kg) — tránh nhiễu "số bịa".
_NUMBER_RE = re.compile(r"(?<![\wÀ-ỹ])[-−]?\d+(?:[.,]\d+)*(?![\wÀ-ỹ])")
# Citation có thể là [1], [1,2], [1; 2] — backend hiện dùng [n] nhưng nhận rộng.
_CITATION_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
_MINUS_PREFIX_RE = re.compile(r"\b(?:âm|am|trừ|tru)\s+(?=\d)", re.IGNORECASE)


def _canonical_number(token: str) -> str:
    """Chuẩn hoá một chuỗi số về dạng so sánh được (không phụ thuộc dấu phân cách)."""
    negative = token.startswith(("-", "−"))
    t = token.lstrip("-−")

    if not t:
        return "0"

    # Có cả ',' và '.': dấu xuất hiện sau cùng là dấu thập phân.
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        groups = t.split(",")
        # 1,000,000 → hàng nghìn; 1,5 → thập phân (chuẩn tiếng Việt).
        if len(groups) > 2 and all(len(g) == 3 for g in groups[1:]):
            t = "".join(groups)
        else:
            t = t.replace(",", ".")
    elif "." in t:
        groups = t.split(".")
        # 1.000 / 2.000.000 → hàng nghìn; 3.2 / 0.125 → thập phân.
        if len(groups) > 2 and all(len(g) == 3 for g in groups[1:]):
            t = "".join(groups)
        elif (len(groups) == 2 and len(groups[1]) == 3 and 1 <= len(groups[0]) <= 3
              and groups[0] != "0"):
            t = "".join(groups)

    if "." in t:
        t = t.rstrip("0").rstrip(".")
    if not t:
        t = "0"
    return f"-{t}" if negative and t != "0" else t


def numbers_of(text: str) -> set[str]:
    """Tập số đã chuẩn hoá trong văn bản — cơ sở kiểm tra số không có trong ngữ cảnh.

    Không trả citation ``[n]`` (đó là chỉ số nguồn, không phải số liệu) và không
    lấy chữ số trong mã như ``CO2``. Đây vẫn là proxy chuỗi, không phải kiểm
    chứng ngữ nghĩa: tên metric tương ứng là "số không tìm thấy trong ngữ cảnh".
    """
    cleaned = _CITATION_RE.sub(" ", text)
    cleaned = _MINUS_PREFIX_RE.sub("-", cleaned)
    return {_canonical_number(m) for m in _NUMBER_RE.findall(cleaned)}


def citation_indices(answer: str) -> list[int]:
    """Các chỉ số nguồn [n] xuất hiện trong câu trả lời (hỗ trợ [1,2], [1; 2])."""
    indices: list[int] = []
    for group in _CITATION_RE.findall(answer):
        indices.extend(int(part) for part in re.split(r"\s*[,;]\s*", group) if part)
    return indices


# Mẫu từ chối — so với văn bản ĐÃ normalize (không dấu). Gồm cả dạng gián tiếp
# ("không đề cập", "không được đề cập", "không cung cấp") vì cùng một hành vi.
_REFUSAL_MARKERS = (
    "khong tim thay ghi chu",
    "khong tim thay thong tin",
    "khong co thong tin",
    "chua co thong tin",
    "khong co du lieu",
    "chua co du lieu",
    "khong du can cu",
    "khong du thong tin",
    "khong the tra loi",
    "khong de cap",
    "khong duoc de cap",
    "chua duoc de cap",
    "khong nhac den",
    "khong cung cap",
    "khong neu",
    "khong bao gom",
    "khong chua thong tin",
    "tai lieu khong",
    "nguon khong",
)


def looks_like_refusal(answer: str) -> bool:
    """Heuristic từ chối: marker nằm ở câu đầu (không quét cả câu trả lời dài).

    Đây vẫn là heuristic chuỗi; report ghi rõ. Tín hiệu có cấu trúc
    ``n_sources == 0`` được lưu riêng ở case và báo cáo thành ``no_source_rate``.
    """
    norm = normalize_text(answer)
    if not norm:
        return False
    first_sentence = re.split(r"[.!?;\n]", norm, maxsplit=1)[0]
    return any(marker in first_sentence for marker in _REFUSAL_MARKERS)


# ============================================================ Token-F1


def token_f1(pred: str, ref: str) -> float:
    """Token-F1 đa tập giữa câu trả lời và văn bản tham chiếu (0 khi một bên rỗng).

    Đây là metric phụ (trùng từ), không phải độ đúng ngữ nghĩa. Khi dataset có
    ``reference_answer``, aggregate báo thêm F1 so với reference answer.
    """
    p, r = tokenize(pred), tokenize(ref)
    if not p or not r:
        return 0.0
    common = sum((Counter(p) & Counter(r)).values())
    if not common:
        return 0.0
    precision = common / len(p)
    recall = common / len(r)
    return 2 * precision * recall / (precision + recall)


# ============================================================ Bản ghi case (raw)


@dataclass
class IngestCase:
    """Một file nguồn được nạp thành ghi chú và chờ đánh chỉ mục."""

    file: str
    note_id: str
    index_status: str  # READY | FAILED | SKIPPED | TIMEOUT | ERROR
    content_chars: int
    truncated: bool
    create_ms: float
    wait_index_ms: float
    created: bool = False       # True = POST /notes tạo mới; False = idempotent replay
    folder_id: str | None = None
    error: str | None = None


@dataclass
class SearchCase:
    """Một truy vấn POST /search — gold là ghi chú tạo từ file nguồn của câu hỏi.

    ``ranked_note_ids`` là note đã phẳng theo thứ hạng nguồn rồi note trong
    nguồn (contract nhóm theo nguồn); ``items`` giữ nguyên các note đã phẳng
    kèm ``source_rank``/``source_domain`` để làm bằng chứng thô.
    """

    qid: str
    query: str
    gold_note_id: str
    ranked_note_ids: list[str]  # đã khử trùng lặp, theo thứ hạng tốt nhất
    answer_hit: bool            # gold text nguyên văn nằm trong top-k note
    latency_ms: float
    items: list[dict] = field(default_factory=list)  # note đã phẳng: note_id/snippet/score/…
    folder_id: str | None = None
    error: str | None = None
    n_sources: int = 0
    max_sources: int = 0
    sources: list[dict] = field(default_factory=list)  # response nhóm thô của /search


@dataclass
class RagCase:
    """Một câu hỏi POST /ai/chat (SSE) — giữ nguyên câu trả lời để đối chiếu."""

    qid: str
    question: str
    answerable: bool
    gold_text: str
    answer: str
    source_note_ids: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)  # source thô: index/chunk_id/snippet/…
    n_sources: int = 0
    citations_ok: bool | None = None  # None = không đánh giá (lỗi); False = không trích dẫn
    citation_count: int = 0
    number_violations: list[str] = field(default_factory=list)
    tokens_used: int = 0
    first_event_ms: float = 0.0
    total_ms: float = 0.0
    context_note_count: int = 0
    context_chars: int = 0
    no_context: bool = False
    reference_answer: str = ""
    error: str | None = None


@dataclass
class PageMatchCase:
    """Một cặp (câu hỏi, file) POST /ai/page-match."""

    qid: str
    source_file: str
    answerable: bool
    gold_text: str
    block_texts: list[str] = field(default_factory=list)
    verified: list[bool] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)  # response thô: id/occ/text/score/verified
    mode: str = ""
    warning: str | None = None
    match_ratio: float = 0.0
    truncated: bool = False
    total_chars: int = 0
    full_text: str | None = None
    source_text: str = ""       # văn bản nguồn — chỉ dùng cho Full-page F1
    total_ms: float = 0.0
    error: str | None = None


# ============================================================ Tổng hợp chỉ số


def _pct(values: list[float], q: float) -> float:
    """Phân vị kiểu nearest-rank: ceil(n*q), kẹp về [1, n]."""
    xs = sorted(values)
    if not xs:
        return 0.0
    rank = min(max(math.ceil(len(xs) * q), 1), len(xs))
    return round(xs[rank - 1], 2)


def _mean(values: list[float | None]) -> float:
    clean = [float(v) for v in values if v is not None]
    return round(sum(clean) / len(clean), 4) if clean else 0.0


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _longest_common_substring_len(a: str, b: str) -> int:
    if not a or not b:
        return 0
    match = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return match.size


def _citation_fields(case: RagCase) -> tuple[int, bool | None]:
    """Trả (số citation, hợp lệ?). Không citation = 0/False, lỗi = None."""
    if case.error:
        return len(citation_indices(case.answer)), None
    count = case.citation_count or len(citation_indices(case.answer))
    valid = case.citations_ok
    if valid is None:
        cites = citation_indices(case.answer)
        valid = bool(cites) and all(1 <= i <= case.n_sources for i in cites)
    return count, bool(valid)


def aggregate_ingest(cases: list[IngestCase]) -> dict:
    by_status: dict[str, int] = {}
    for c in cases:
        by_status[c.index_status] = by_status.get(c.index_status, 0) + 1
    return {
        "files": len(cases),
        "by_status": by_status,
        "ready_rate": _rate(by_status.get("READY", 0), len(cases)),
        "created": sum(1 for c in cases if c.created),
        "reused": sum(1 for c in cases if not c.created and not c.error),
        "errors": sum(1 for c in cases if c.error),
        "create_ms_p50": _pct([c.create_ms for c in cases], 0.5),
        "wait_index_ms_p50": _pct([c.wait_index_ms for c in cases], 0.5),
        "wait_index_ms_p95": _pct([c.wait_index_ms for c in cases], 0.95),
        "truncated_files": sum(1 for c in cases if c.truncated),
    }


def aggregate_search(cases: list[SearchCase], top_k: int, corpus_notes: int) -> dict:
    """Chấm top-``top_k`` NOTE sau khi phẳng danh sách nguồn đã nhóm.

    API chỉ trả tối đa ``max_sources`` nguồn (mỗi nguồn tối đa 10 note), nên
    phải cắt theo top_k trước khi tính hạng: nếu không, note ở vị trí 6..50
    sẽ bị tính là "Recall@5" dù nằm ngoài top-5.
    """
    completed = [c for c in cases if not c.error]
    k = max(0, int(top_k))
    ranks = []
    for c in completed:
        ranked = c.ranked_note_ids[:k]
        ranks.append(next((i for i, nid in enumerate(ranked, 1)
                           if nid == c.gold_note_id), None))
    n = len(completed)
    return {
        "queries": len(cases),
        "completed": n,
        "errors": len(cases) - n,
        "error_rate": _rate(len(cases) - n, len(cases)),
        "recall_at_k": _rate(sum(1 for r in ranks if r), n),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 4) if n else None,
        "answer_hit_rate": _rate(sum(1 for c in completed if c.answer_hit), n),
        "sources_avg": round(_mean([float(c.n_sources) for c in completed]), 2),
        "notes_returned_avg": round(
            _mean([float(len(c.items)) for c in completed]), 2),
        "empty_rate": _rate(sum(1 for c in completed if not c.items), n),
        "latency_ms_p50": _pct([c.latency_ms for c in completed], 0.5),
        "latency_ms_p95": _pct([c.latency_ms for c in completed], 0.95),
        # Sàn cấu trúc: kho càng nhỏ, top-k càng dễ trúng — đi kèm để đọc đúng ý nghĩa.
        "random_floor": round(min(1.0, k / max(1, corpus_notes)), 4),
        "corpus_notes": corpus_notes,
        "top_k": k,
        "max_sources": max((c.max_sources for c in cases), default=0),
    }


def aggregate_rag(cases: list[RagCase]) -> dict:
    ans = [c for c in cases if c.answerable]
    un = [c for c in cases if not c.answerable]

    def completed(group: list[RagCase]) -> list[RagCase]:
        # Chỉ loại ca có lỗi tường minh; câu trả lời rỗng không lỗi vẫn tính là thất bại.
        return [c for c in group if not c.error]

    ans_ok = completed(ans)
    un_ok = completed(un)
    citations = [_citation_fields(c) for c in ans_ok]
    cited = [pair for pair in citations if pair[0] > 0]
    valid = [pair for pair in citations if pair[1]]
    ref_cases = [c for c in ans_ok if c.reference_answer.strip()]
    refusals = sum(1 for c in un_ok if looks_like_refusal(c.answer))

    return {
        "answerable": {
            "questions": len(ans),
            "completed": len(ans_ok),
            "errors": len(ans) - len(ans_ok),
            "error_rate": _rate(len(ans) - len(ans_ok), len(ans)),
            # F1 trùng từ với đoạn gold — metric phụ, không phải "độ đúng".
            "answer_token_f1_gold_avg": (
                _mean([token_f1(c.answer, c.gold_text) for c in ans_ok])
                if ans_ok else None),
            "answer_token_f1_reference_avg": (
                _mean([token_f1(c.answer, c.reference_answer) for c in ref_cases])
                if ref_cases else None),
            "reference_answer_cases": len(ref_cases),
            # Mẫu số là MỌI câu trả lời hoàn thành; không trích dẫn = 0 (không loại khỏi mẫu số).
            "citation_valid_rate": _rate(len(valid), len(ans_ok)),
            "citation_presence_rate": _rate(len(cited), len(ans_ok)),
            "no_citation_rate": (_rate(len(ans_ok) - len(cited), len(ans_ok))
                                 if ans_ok else None),
            "number_violation_rate": _rate(
                sum(1 for c in ans_ok if c.number_violations), len(ans_ok)),
            "no_source_rate": _rate(sum(1 for c in ans_ok if c.n_sources == 0), len(ans_ok)),
            "no_context_rate": _rate(sum(1 for c in ans_ok if c.no_context), len(ans_ok)),
            "context_chars_avg": round(
                _mean([float(c.context_chars) for c in ans_ok]), 1) if ans_ok else None,
            "tokens_used_avg": round(
                _mean([float(c.tokens_used) for c in ans_ok]), 1) if ans_ok else None,
            "first_event_ms_p50": _pct([c.first_event_ms for c in ans_ok], 0.5),
            "total_ms_p50": _pct([c.total_ms for c in ans_ok], 0.5),
            "total_ms_p95": _pct([c.total_ms for c in ans_ok], 0.95),
        },
        "unanswerable": {
            "questions": len(un),
            "completed": len(un_ok),
            "errors": len(un) - len(un_ok),
            "error_rate": _rate(len(un) - len(un_ok), len(un)),
            # Lỗi AI bị loại khỏi mẫu số — không còn bị tính là "trả lời bừa".
            "refusal_rate": _rate(refusals, len(un_ok)),
            "false_answer_rate": (_rate(len(un_ok) - refusals, len(un_ok))
                                  if un_ok else None),
            "number_violation_rate": _rate(
                sum(1 for c in un_ok if c.number_violations), len(un_ok)),
            "no_source_rate": _rate(sum(1 for c in un_ok if c.n_sources == 0), len(un_ok)),
        },
    }


def _pagematch_items(case: PageMatchCase, top_k: int) -> list[dict]:
    if case.items:
        return case.items[:top_k]
    return [{"text": text, "verified": verified}
            for text, verified in zip(case.block_texts, case.verified)][:top_k]


def _score_pagematch_case(case: PageMatchCase, top_k: int) -> dict:
    """Chấm một ca PageMatch trên top-k block; trả dict dẫn xuất (không mutate case)."""
    items = _pagematch_items(case, top_k)
    blocks = [normalize_text(str(item.get("text", ""))) for item in items]
    norm_gold = normalize_text(case.gold_text)
    out = {
        "items": len(blocks),
        "hit": False,
        "exact_hit": False,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "coverage": 0.0,
        "span_precision": 0.0,
        "span_f1": 0.0,
        "full_page_f1": None,
    }
    if not norm_gold or not blocks:
        return out

    coverages = [_longest_common_substring_len(norm_gold, block) / len(norm_gold)
                 for block in blocks]
    exact = [norm_gold in block for block in blocks]
    # Gold có thể bị chia giữa hai block liền kề → xét cả chuỗi block nối.
    joined_coverage = (_longest_common_substring_len(norm_gold, " ".join(blocks))
                       / len(norm_gold))
    # Block liên quan nếu chứa gold hoặc phủ ≥ 50% đoạn gold (gold có thể bị chia khối).
    relevant = [exact[i] or coverages[i] >= 0.5 for i in range(len(blocks))]
    best = max([*coverages, joined_coverage])
    hit = any(exact) or joined_coverage >= 0.8
    precision = sum(relevant) / len(blocks)
    recall = 1.0 if hit else 0.0
    # Precision theo ký tự: trả cả trang trong một block sẽ bị phạt mạnh.
    returned_chars = sum(len(block) for block in blocks)
    span_precision = min(1.0, len(norm_gold) / returned_chars) if returned_chars else 0.0
    out.update({
        "hit": hit,
        "exact_hit": any(exact),
        "precision": round(precision, 4),
        "recall": recall,
        "f1": round(2 * precision * recall / (precision + recall), 4)
        if (precision + recall) else 0.0,
        "coverage": round(best, 4),
        "span_precision": round(span_precision, 4),
        "span_f1": round(2 * span_precision * best / (span_precision + best), 4)
        if (span_precision + best) else 0.0,
    })

    if case.mode == "full_page" and case.full_text and case.source_text:
        # Full-page F1: gợi ý "lưu cả trang" có tái tạo đúng nội dung nguồn không.
        src_tokens, full_tokens = tokenize(case.source_text), tokenize(case.full_text)
        common = sum((Counter(full_tokens) & Counter(src_tokens)).values())
        p = common / len(full_tokens) if full_tokens else 0.0
        r = common / len(src_tokens) if src_tokens else 0.0
        out["full_page_f1"] = round(2 * p * r / (p + r), 4) if (p + r) else 0.0
    return out


def aggregate_pagematch(cases: list[PageMatchCase], top_k: int = 5) -> dict:
    pos = [c for c in cases if c.answerable]
    neg = [c for c in cases if not c.answerable]

    def quality(group: list[PageMatchCase]) -> list[PageMatchCase]:
        return [c for c in group if not c.error and not c.warning]

    def fallback(group: list[PageMatchCase]) -> list[PageMatchCase]:
        return [c for c in group if not c.error and c.warning]

    def summarize_pos(group: list[PageMatchCase]) -> dict:
        scores = [_score_pagematch_case(c, top_k) for c in group]
        return {
            "cases": len(group),
            "hit_rate": _rate(sum(1 for s in scores if s["hit"]), len(group)),
            "exact_hit_rate": _rate(sum(1 for s in scores if s["exact_hit"]), len(group)),
            "precision_at_k": (
                round(sum(s["precision"] for s in scores) / len(scores), 4)
                if scores else None),
            "recall_at_k": _rate(sum(1 for s in scores if s["recall"]), len(group)),
            "f1_at_k_avg": round(sum(s["f1"] for s in scores) / len(scores), 4) if scores else None,
            "span_coverage_avg": (
                round(sum(s["coverage"] for s in scores) / len(scores), 4) if scores else None),
            "span_precision_avg": (
                round(sum(s["span_precision"] for s in scores) / len(scores), 4)
                if scores else None),
            "span_f1_avg": (
                round(sum(s["span_f1"] for s in scores) / len(scores), 4) if scores else None),
            "full_page_cases": sum(1 for s in scores if s["full_page_f1"] is not None),
            "full_page_f1_avg": (
                round(sum(s["full_page_f1"] for s in scores
                          if s["full_page_f1"] is not None)
                      / sum(1 for s in scores if s["full_page_f1"] is not None), 4)
                if any(s["full_page_f1"] is not None for s in scores) else None),
        }

    def summarize_neg(group: list[PageMatchCase]) -> dict:
        return {
            "cases": len(group),
            # FPR: ca âm tính nhưng hệ thống vẫn đề xuất ≥ 1 block.
            "fpr": _rate(sum(1 for c in group if _pagematch_items(c, top_k)), len(group)),
            "verified_fpr": _rate(
                sum(1 for c in group
                    if any(bool(i.get("verified")) for i in _pagematch_items(c, top_k))),
                len(group)),
        }

    pos_quality, pos_fallback = quality(pos), fallback(pos)
    neg_quality, neg_fallback = quality(neg), fallback(neg)

    # Tách full_page khỏi segments: một block "cả trang" không được thưởng precision
    # như một đoạn chính xác (H3 trong review).
    qseg_pos = [c for c in pos_quality if c.mode != "full_page"]
    qfull_pos = [c for c in pos_quality if c.mode == "full_page"]
    qseg_neg = [c for c in neg_quality if c.mode != "full_page"]
    qfull_neg = [c for c in neg_quality if c.mode == "full_page"]
    fseg_pos = [c for c in pos_fallback if c.mode != "full_page"]
    ffull_pos = [c for c in pos_fallback if c.mode == "full_page"]
    fseg_neg = [c for c in neg_fallback if c.mode != "full_page"]
    ffull_neg = [c for c in neg_fallback if c.mode == "full_page"]

    errors = sum(1 for c in cases if c.error)
    return {
        "top_k": top_k,
        "cases": len(cases),
        "errors": errors,
        "error_rate": _rate(errors, len(cases)),
        "quality": {
            # `positive`/`negative` = ca segments (metric chất lượng chính).
            "positive": summarize_pos(qseg_pos),
            "negative": summarize_neg(qseg_neg),
            "full_page": {
                "positive": summarize_pos(qfull_pos),
                "negative": summarize_neg(qfull_neg),
            },
            "latency_ms_p50": _pct([c.total_ms for c in pos_quality + neg_quality], 0.5),
            "latency_ms_p95": _pct([c.total_ms for c in pos_quality + neg_quality], 0.95),
        },
        "fallback": {
            "cases": len(pos_fallback) + len(neg_fallback),
            "positive": summarize_pos(fseg_pos),
            "negative": summarize_neg(fseg_neg),
            "full_page": {
                "positive": summarize_pos(ffull_pos),
                "negative": summarize_neg(ffull_neg),
            },
            "latency_ms_p50": _pct([c.total_ms for c in pos_fallback + neg_fallback], 0.5),
            "latency_ms_p95": _pct([c.total_ms for c in pos_fallback + neg_fallback], 0.95),
        },
        "verify_unavailable_rate": _rate(
            sum(1 for c in cases if c.warning), len(cases)),
        "full_page_mode_rate": _rate(
            sum(1 for c in cases if c.mode == "full_page"), len(cases)),
        "truncated_rate": _rate(sum(1 for c in cases if c.truncated), len(cases)),
        "latency_ms_p50": _pct([c.total_ms for c in cases], 0.5),
        "latency_ms_p95": _pct([c.total_ms for c in cases], 0.95),
    }


# ============================================================ Serialize / recompute


def case_to_jsonl(module: str, obj) -> dict:
    return {"module": module, "schema_version": RAW_SCHEMA_VERSION, **asdict(obj)}


def case_from_dict(cls, data: dict):
    """Dựng lại case từ raw JSONL, bỏ qua khóa lạ (tương thích raw bản cũ)."""
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})