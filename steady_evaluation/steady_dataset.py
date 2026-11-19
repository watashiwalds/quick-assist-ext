"""§2 — Nạp dataset: file nguồn (HTML/TXT) + cặp hỏi–đáp gold (CSV).

Hợp đồng dataset:
  dataset/sources/*.{html,htm,txt}  — file gốc. HTML test luồng Trafilatura
                                      (POST /ai/page-match với field `html`),
                                      TXT test luồng văn bản dán (field `text`).
  dataset/qa_pairs.csv              — source_file,question,gold_text,answerable
                                      (answerable ∈ {yes,no}; gold_text là NGUYÊN VĂN
                                      một đoạn trong file nguồn, văn bản hiển thị
                                      với HTML — không chứa thẻ).
                                      Cột tùy chọn: reference_answer (câu trả lời
                                      chuẩn ngắn) để báo F1 tham chiếu.

Kiểm chứng fail-fast trước khi chạy (mọi lỗi gom vào bundle.issues):
  - source_file phải tồn tại trong sources/
  - question/gold_text không được rỗng
  - gold_text phải tìm thấy nguyên văn (sau chuẩn hoá) trong file nguồn
  - question ≤ 500 ký tự (giới hạn chặt nhất — page-match), answerable hợp lệ
  - HTML ≤ 2 MB (PAGE_MATCH_MAX_HTML_BYTES); nội dung nạp note > 20.000 ký tự
    sẽ bị cắt ở §3 và ghi dấu truncated (đúng hành vi extension)

Runner chỉ chạy khi ``issues`` rỗng, trừ khi người dùng chủ động ``--allow-partial``.
"""

from __future__ import annotations

import csv
import hashlib
import html.parser
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from steady_metrics import normalize_text


# ============================================================ Trích text từ HTML


class _VisibleText(html.parser.HTMLParser):
    """Trích văn bản hiển thị — bỏ script/style/noscript/template/svg (stdlib, tất định)."""

    _SKIP = {"script", "style", "noscript", "template", "svg", "head"}
    _BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "br", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)


def html_to_text(html_source: str) -> str:
    parser = _VisibleText()
    parser.feed(html_source)
    return "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines()).strip()


# ============================================================ Mô hình dữ liệu


@dataclass
class SourceFile:
    name: str          # tên file (khớp cột source_file trong CSV)
    path: Path
    kind: str          # "html" | "text"
    raw: str           # nội dung gốc — gửi cho page-match (html) / dán (text)
    plain: str         # văn bản hiển thị — nội dung nạp thành ghi chú


@dataclass
class QAPair:
    qid: str
    source_file: str
    question: str
    gold_text: str
    answerable: bool
    reference_answer: str = ""


@dataclass
class DatasetBundle:
    sources: list[SourceFile] = field(default_factory=list)
    pairs: list[QAPair] = field(default_factory=list)
    source_by_name: dict[str, SourceFile] = field(default_factory=dict)
    fingerprint: str = ""
    issues: list[str] = field(default_factory=list)
    excluded_rows: int = 0
    excluded_reasons: list[str] = field(default_factory=list)

    @property
    def stats(self) -> dict:
        lens = [len(s.plain) for s in self.sources]
        n_ans = sum(1 for p in self.pairs if p.answerable)
        return {
            "source_files": len(self.sources),
            "html_files": sum(1 for s in self.sources if s.kind == "html"),
            "text_files": sum(1 for s in self.sources if s.kind == "text"),
            "qa_pairs": len(self.pairs),
            "answerable": n_ans,
            "unanswerable": len(self.pairs) - n_ans,
            "reference_answers": sum(1 for p in self.pairs if p.reference_answer),
            "excluded_rows": self.excluded_rows,
            "plain_chars_min": min(lens) if lens else 0,
            "plain_chars_median": int(statistics.median(lens)) if lens else 0,
            "plain_chars_max": max(lens) if lens else 0,
            "files_over_chunk_size": sum(1 for n in lens if n > 1200),
        }


# ============================================================ Loader


def load_sources(sources_dir: Path, cfg) -> tuple[list[SourceFile], list[str]]:
    """Đọc mọi file .html/.htm/.txt trong sources/, kiểm tra giới hạn backend."""
    issues: list[str] = []
    sources: list[SourceFile] = []
    for path in sorted(list(sources_dir.glob("*.html")) + list(sources_dir.glob("*.htm"))
                       + list(sources_dir.glob("*.txt"))):
        raw = path.read_text(encoding="utf-8", errors="replace")
        kind = "html" if path.suffix.lower() in {".html", ".htm"} else "text"
        if kind == "html" and len(raw.encode("utf-8")) > cfg.max_html_bytes:
            issues.append(f"[sources] {path.name}: HTML {len(raw)} bytes > {cfg.max_html_bytes} — bỏ file")
            continue
        plain = html_to_text(raw) if kind == "html" else raw
        if not plain.strip():
            issues.append(f"[sources] {path.name}: không trích được văn bản nào — bỏ file")
            continue
        sources.append(SourceFile(name=path.name, path=path, kind=kind, raw=raw, plain=plain))
    if not sources:
        issues.append(f"[sources] Không có file nguồn nào trong {sources_dir}")
    return sources, issues


def load_qa_pairs(csv_path: Path, sources: list[SourceFile]
                  ) -> tuple[list[QAPair], list[str], list[str]]:
    """Đọc CSV; chỉ nhận cặp gold hợp lệ. Trả (pairs, issues, lý do loại)."""
    issues: list[str] = []
    excluded: list[str] = []
    by_name = {s.name: s for s in sources}
    pairs: list[QAPair] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"source_file", "question", "gold_text", "answerable"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            issues.append(f"[qa_pairs.csv] Thiếu cột: {sorted(missing)} — cần {sorted(required)}")
            return pairs, issues, excluded
        for i, row in enumerate(reader, start=2):  # dòng 1 là header
            source_name = (row.get("source_file") or "").strip()
            question = (row.get("question") or "").strip()
            gold = (row.get("gold_text") or "").strip()
            answerable_raw = (row.get("answerable") or "").strip().lower()
            reference = (row.get("reference_answer") or "").strip()

            if answerable_raw not in {"yes", "no", "y", "n", "true", "false"}:
                reason = f"answerable='{answerable_raw}' không hợp lệ"
                issues.append(f"[qa_pairs.csv:{i}] {reason} — bỏ")
                excluded.append(reason)
                continue
            if not question:
                reason = "question rỗng"
                issues.append(f"[qa_pairs.csv:{i}] {reason} — bỏ")
                excluded.append(reason)
                continue
            if not gold:
                reason = "gold_text rỗng"
                issues.append(f"[qa_pairs.csv:{i}] {reason} — bỏ")
                excluded.append(reason)
                continue
            if source_name not in by_name:
                reason = f"source_file='{source_name}' không có trong sources/"
                issues.append(f"[qa_pairs.csv:{i}] {reason} — bỏ")
                excluded.append(reason)
                continue
            if len(question) > 500:
                reason = f"question {len(question)} ký tự > 500"
                issues.append(f"[qa_pairs.csv:{i}] {reason} — bỏ")
                excluded.append(reason)
                continue
            answerable = answerable_raw in {"yes", "y", "true"}
            src = by_name[source_name]
            haystack = src.plain if src.kind == "html" else src.raw
            if answerable and normalize_text(gold) not in normalize_text(haystack):
                reason = f"gold_text KHÔNG nguyên văn trong {source_name}"
                issues.append(f"[qa_pairs.csv:{i}] {reason} — bỏ")
                excluded.append(reason)
                continue
            pairs.append(QAPair(qid=f"QA-{i - 1:03d}", source_file=source_name,
                                question=question, gold_text=gold,
                                answerable=answerable, reference_answer=reference))
    return pairs, issues, excluded


def load_dataset(cfg) -> DatasetBundle:
    """Điểm vào §2 — nạp toàn bộ dataset + fingerprint để ghi vào manifest."""
    sources_dir = cfg.dataset_dir / "sources"
    csv_path = cfg.dataset_dir / "qa_pairs.csv"
    sources, issues = load_sources(sources_dir, cfg)
    pairs: list[QAPair] = []
    excluded: list[str] = []
    if not csv_path.exists():
        issues.append(f"[dataset] Không tìm thấy {csv_path}")
    elif sources:
        pairs, qa_issues, excluded = load_qa_pairs(csv_path, sources)
        issues += qa_issues
    if not pairs:
        issues.append("[dataset] Không còn cặp hỏi–đáp hợp lệ nào — kiểm tra issues")

    hasher = hashlib.sha256()
    for s in sources:
        hasher.update(s.name.encode() + s.raw.encode())
    if csv_path.exists():
        hasher.update(csv_path.read_bytes())
    hasher.update(b"\n".join(f"{p.qid}|{p.reference_answer}".encode() for p in pairs))
    return DatasetBundle(sources=sources, pairs=pairs,
                         source_by_name={s.name: s for s in sources},
                         fingerprint=hasher.hexdigest()[:16], issues=issues,
                         excluded_rows=len(excluded), excluded_reasons=excluded)


class DatasetError(RuntimeError):
    """Dataset không đạt cổng kiểm chứng — runner dừng trước khi gọi backend."""


def validate_bundle(bundle: DatasetBundle, allow_partial: bool = False) -> None:
    """Fail-fast: có issue nào cũng dừng, trừ khi người dùng chọn --allow-partial."""
    if not bundle.pairs:
        raise DatasetError("Dataset không có cặp hỏi–đáp hợp lệ nào.")
    if bundle.issues and not allow_partial:
        detail = "\n".join(f"  - {issue}" for issue in bundle.issues)
        raise DatasetError(
            f"Dataset có {len(bundle.issues)} vấn đề; sửa hết rồi chạy lại "
            f"(hoặc dùng --allow-partial để chấp nhận tập bị rút gọn):\n{detail}")


def print_dataset_report(bundle: DatasetBundle) -> None:
    """Báo cáo dataset — dùng được cho --validate (chạy §2 mà không cần backend)."""
    print("=== DATASET ===")
    for key, value in bundle.stats.items():
        print(f"  {key}: {value}")
    if bundle.issues:
        print(f"  ⚠ {len(bundle.issues)} vấn đề:")
        for issue in bundle.issues:
            print(f"    - {issue}")
        if bundle.excluded_reasons:
            print(f"  Đã loại {bundle.excluded_rows} dòng; runner sẽ dừng trừ khi --allow-partial")
    else:
        print("  ✓ Không có vấn đề kiểm chứng nào")
