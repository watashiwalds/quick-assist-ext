"""§5 — Điều phối pipeline & xuất kết quả (điểm vào duy nhất).

Luồng chạy:
  health → login → nạp dataset (§2, fail-fast) → tạo folder riêng của run
  → quota trước → ingest (§3.1, chỉ khi có search/rag) → gate READY
  → các module được chọn (§3.2–3.4) → chấm (§4) → artifact → quota sau.

Cách dùng:
  python3 run_evaluation.py --validate                      # kiểm chứng dataset (exit ≠ 0 nếu lỗi)
  python3 run_evaluation.py --model-label "bonsai9b+gte" --tag m1
  python3 run_evaluation.py --compare                       # bảng so sánh (nhóm theo dataset/config)
  python3 run_evaluation.py --recompute latest              # tái tạo metrics từ raw_results.jsonl

Mỗi lần chạy = MỘT tổ hợp model LLM + embedding (đổi ở backend/llama-server rồi
restart; pipeline không đổi model hộ — ghi nhãn tổ hợp vào manifest để --compare
dựng bảng so sánh). Hỗ trợ --modules để chạy một phần: search,rag,pagematch.

Artifact được ghi ngay khi từng case hoàn tất; lỗi giữa chừng vẫn để lại
raw_results.jsonl + metrics.json + report.md (kèm ``fatal_error``).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

from steady_backend import BackendClient, SteadyConfig, load_env
from steady_dataset import DatasetError, load_dataset, print_dataset_report, validate_bundle
from steady_flows import (IngestedDocument, ingest_sources, not_ready_files, run_pagematch,
                          run_rag, run_search)
from steady_metrics import (METRICS_VERSION, RAW_SCHEMA_VERSION, IngestCase, PageMatchCase,
                            RagCase, SearchCase, aggregate_ingest, aggregate_pagematch,
                            aggregate_rag, aggregate_search, case_from_dict, case_to_jsonl)

BASE_DIR = Path(__file__).resolve().parent
RUNS_DIR = BASE_DIR / "runs"
ALL_MODULES = ["search", "rag", "pagematch"]
MIN_QUALITY_PAIRS = 20  # dưới ngưỡng này chỉ là smoke, không đủ để kết luận chất lượng


# ============================================================ Tiện ích


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True, cwd=BASE_DIR).stdout.strip()
    except Exception:
        return "git-unavailable"


def eval_code_sha256() -> str:
    """Hash toàn bộ mã đánh giá — repo commit không bao gồm thư mục untracked này."""
    hasher = hashlib.sha256()
    for path in sorted(BASE_DIR.rglob("*.py")):
        if "__pycache__" in path.parts or "runs" in path.parts:
            continue
        hasher.update(str(path.relative_to(BASE_DIR)).encode() + b"\0")
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sanitize_id(value: str, fallback: str = "x") -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")[:80] or fallback


def resolve_evidence_type(cfg: SteadyConfig, bundle) -> str:
    if cfg.evidence_type and cfg.evidence_type != "auto":
        return cfg.evidence_type
    if len(bundle.pairs) >= MIN_QUALITY_PAIRS and cfg.model_label != "unlabeled":
        return "quality"
    return "smoke"


def _fmt(value) -> str:
    return "—" if value is None else str(value)


def _rate_count(rate, count, denominator) -> str:
    """``0.7632 (29/38)`` — giữ cả tỉ lệ và tử/mẫu để đối chiếu báo cáo."""
    return f"{_fmt(rate)} ({count}/{denominator})"


class RawWriter:
    """Ghi JSONL ngay sau mỗi case — lỗi giữa chừng không mất bằng chứng."""

    def __init__(self, path: Path):
        self.path = path
        self._file = open(path, "w", encoding="utf-8")

    def emit(self, module: str, case) -> None:
        self._file.write(json.dumps(case_to_jsonl(module, case), ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _safe_quota(client: BackendClient) -> dict:
    try:
        return client.quota()
    except Exception as exc:  # noqa: BLE001 — quota chỉ là metadata
        return {"error": f"{type(exc).__name__}: {exc}"}


# ============================================================ Báo cáo Markdown


def build_report_md(manifest: dict, metrics: dict, bundle_issues: list[str] | None = None,
                    samples: list[dict] | None = None,
                    bundle_stats: dict | None = None) -> str:
    """Sinh report cho MỌI tổ hợp module (không truy cập khóa vô điều kiện)."""
    m = metrics or {}
    manifest = manifest or {}
    bundle_issues = bundle_issues or manifest.get("dataset_issues") or []
    bundle_stats = bundle_stats or manifest.get("dataset_stats") or {}
    samples = samples or []
    label = manifest.get("model_label", "?")
    evidence = manifest.get("evidence_type", "unknown")

    lines = [
        f"# Báo cáo đánh giá steady — {manifest.get('run_id', '?')}",
        f"*Model: `{label}` · backend `{manifest.get('api_base_url', '?')}`"
        f" · dataset `{manifest.get('dataset_fingerprint', '?')}`"
        f" · git `{str(manifest.get('git_commit', '?'))[:9]}`"
        f" · eval-code `{str(manifest.get('eval_code_sha256', '?'))[:9]}`"
        f" · {manifest.get('date_utc', '?')}*",
        "",
        f"> **Loại bằng chứng: `{evidence}`** · metrics v{m.get('metrics_version', METRICS_VERSION)}"
        f" · module: `{', '.join(manifest.get('modules', [])) or '—'}`",
        "",
    ]
    if evidence != "quality":
        lines += [
            "> ⚠ **KHÔNG dùng các số dưới đây để kết luận chất lượng.** Dataset hiện tại chỉ "
            "kiểm chứng pipeline chạy được (smoke). Cần dataset đúng kích thước + nhãn chuẩn "
            "và `--evidence-type quality` trước khi báo cáo chất lượng.",
            "",
        ]

    lines += ["## 1. Dataset", ""]
    if bundle_stats:
        lines += [f"- {key}: {value}" for key, value in bundle_stats.items()]
    lines += [f"- included_pairs: {_fmt(manifest.get('included_pairs'))}"
              f" · excluded_rows: {_fmt(manifest.get('excluded_rows'))}", ""]
    if bundle_issues:
        lines += ["**Vấn đề kiểm chứng (đã được chấp nhận bằng --allow-partial):**"]
        lines += [f"- {issue}" for issue in bundle_issues]
        lines += [""]

    ing = m.get("ingest")
    if ing:
        lines += [
            "## 2. Ingest (nạp ghi chú + chờ index)",
            f"- {ing.get('files', 0)} file, trạng thái: {ing.get('by_status', {})}"
            f" · READY {_fmt(ing.get('ready_rate'))}"
            f" · tạo mới {ing.get('created', '—')} / replay {ing.get('reused', '—')}",
            f"- tài liệu dài: **{ing.get('documents', 0)} file → {ing.get('parts', 0)} part**"
            f" · part READY {ing.get('parts_ready', 0)}/{ing.get('parts', 0)}"
            f" ({_fmt(ing.get('parts_ready_rate'))})"
            f" · file đủ part READY {ing.get('documents_all_parts_ready', 0)}"
            f"/{ing.get('documents', 0)}",
            f"- ký tự đã index: **{ing.get('indexed_chars', 0):,} / {ing.get('total_chars', 0):,}**"
            f" ({_fmt(ing.get('indexed_chars_ratio'))})"
            f" · part lớn nhất {ing.get('max_part_chars', 0):,} ký tự"
            f" · file bị cắt: {ing.get('truncated_files', 0)}",
            f"- create p50 = **{ing.get('create_ms_p50', '—')} ms**"
            f" · chờ index p50 = **{ing.get('wait_index_ms_p50', '—')} ms**"
            f" · p95 = **{ing.get('wait_index_ms_p95', '—')} ms**",
            "",
        ]

    s = m.get("search")
    if s:
        lines += [
            "## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)",
            f"`POST /search` với `max_sources={manifest.get('max_sources', '—')}`; "
            f"Recall@{manifest.get('top_k', 'k')}/MRR tính trên **tài liệu** "
            f"(`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.",
            "",
            f"| Queries | Hoàn thành | Lỗi | Recall@{manifest.get('top_k', 'k')} "
            f"| Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max "
            f"| Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| {s.get('queries', 0)} | {s.get('completed', '—')} | {s.get('errors', 0)} "
            f"| {_fmt(s.get('recall_at_k'))} | {_fmt(s.get('recall_part_at_k'))} "
            f"| {_fmt(s.get('mrr'))} | {_fmt(s.get('answer_hit_rate'))} "
            f"| {_fmt(s.get('answer_hit_note_rate'))} | {_fmt(s.get('sources_avg'))} "
            f"| {s.get('max_sources_observed', '—')} | {_fmt(s.get('notes_returned_avg'))} "
            f"| {_fmt(s.get('empty_rate'))} | {s.get('latency_ms_p50', '—')} "
            f"| {s.get('latency_ms_p95', '—')} | {s.get('random_floor', '—')} |",
            "",
            f"- corpus: {s.get('corpus_notes', '—')} note / "
            f"{s.get('corpus_documents', '—')} tài liệu"
            f" · `max_sources` {'đúng' if s.get('max_sources_ok') else 'BỊ VƯỢT'}"
            f" (ca chạm trần: {_fmt(s.get('sources_at_cap_rate'))})"
            f" · gold vắt qua ranh giới part: {s.get('gold_spans_parts', 0)}",
            "",
        ]
        if isinstance(s.get("random_floor"), (int, float)) and s["random_floor"] >= 1.0:
            lines += [
                f"> ⚠ `random_floor = {s['random_floor']}` (top_k ≥ số tài liệu trong corpus): "
                "Recall@k bị chặn trần, không phản ánh chất lượng xếp hạng.",
                "",
            ]

    r = m.get("rag")
    if r:
        a, u = r.get("answerable", {}), r.get("unanswerable", {})
        f1 = a.get("answer_token_f1_gold_avg", a.get("answer_f1_gold_avg"))
        ref_f1 = a.get("answer_token_f1_reference_avg")
        lines += [
            "## 4. RAG hỏi đáp (SSE thật, quota thật)",
            f"| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference "
            f"| Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) "
            f"| total p50 (ms) |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| {a.get('questions', 0)} | {a.get('completed', '—')} | {a.get('errors', 0)} "
            f"| {_fmt(f1)} | {_fmt(ref_f1)} | {_fmt(a.get('citation_valid_rate'))} "
            f"| {_fmt(a.get('no_citation_rate'))} | {_fmt(a.get('number_violation_rate'))} "
            f"| {a.get('tokens_used_avg', '—')} | {a.get('total_ms_p50', '—')} |",
            "",
            f"- Không có nguồn: {_fmt(a.get('no_source_rate'))}"
            f" · không ngữ cảnh: {_fmt(a.get('no_context_rate'))}"
            f" · ngữ cảnh TB: {a.get('context_chars_avg', '—')} ký tự",
            "",
            "| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {u.get('questions', 0)} | {u.get('completed', '—')} | {u.get('errors', 0)} "
            f"| {_fmt(u.get('refusal_rate'))} | {_fmt(u.get('false_answer_rate'))} "
            f"| {_fmt(u.get('no_source_rate'))} |",
            "",
            f"- Số ngoài ngữ cảnh ở ca âm: {_fmt(u.get('number_violation_rate'))}",
            "> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời "
            "có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. "
            "*Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.",
            "",
        ]

    p = m.get("pagematch")
    if p:
        q = p.get("quality", {})
        qpos, qneg = q.get("positive", {}), q.get("negative", {})
        fpos, fneg = p.get("fallback", {}).get("positive", {}), p.get("fallback", {}).get("negative", {})
        if not q and "positive" in p:  # metrics bản cũ
            qpos, qneg = p.get("positive", {}), p.get("negative", {})
        lines += [
            "## 5. PageMatch (Trafilatura + văn bản dán)",
            f"**Chất lượng — segments** (không warning, top-{p.get('top_k', 5)}):",
            f"| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision "
            f"| Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| {qpos.get('cases', 0)} | {_fmt(qpos.get('hit_rate'))} "
            f"| {_fmt(qpos.get('exact_hit_rate'))} | {_fmt(qpos.get('precision_at_k'))} "
            f"| {_fmt(qpos.get('recall_at_k'))} | {_fmt(qpos.get('f1_at_k_avg'))} "
            f"| {_fmt(qpos.get('span_precision_avg'))} "
            f"| {_fmt(qpos.get('span_coverage_avg'))} | {_fmt(qpos.get('span_f1_avg'))} "
            f"| {qneg.get('cases', 0)} | {_fmt(qneg.get('fpr'))} | {q.get('latency_ms_p50', '—')} |",
            "",
            "**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):",
            f"| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |",
            "|---:|---:|---:|---:|---:|---:|---:|",
            f"| {fpos.get('cases', 0)} | {_fmt(fpos.get('hit_rate'))} "
            f"| {_fmt(fpos.get('precision_at_k'))} | {_fmt(fpos.get('span_coverage_avg'))} "
            f"| {fneg.get('cases', 0)} | {_fmt(fneg.get('fpr'))} "
            f"| {p.get('fallback', {}).get('latency_ms_p50', '—')} |",
            "",
            f"- verify_unavailable_rate: {_fmt(p.get('verify_unavailable_rate'))}"
            f" · full_page_mode_rate: {_fmt(p.get('full_page_mode_rate'))}"
            f" · truncated_rate: {_fmt(p.get('truncated_rate'))}"
            f" · lỗi: {p.get('errors', 0)}",
            "",
        ]
        qfull = q.get("full_page", {})
        qfull_pos, qfull_neg = qfull.get("positive", {}), qfull.get("negative", {})
        if qfull_pos.get("cases") or qfull_neg.get("cases"):
            lines += [
                "**Chất lượng — full-page** (tách khỏi segments; một block cả trang không "
                "được tính như đoạn chính xác):",
                f"| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |",
                "|---:|---:|---:|---:|---:|---:|",
                f"| {qfull_pos.get('cases', 0)} | {_fmt(qfull_pos.get('hit_rate'))} "
                f"| {_fmt(qfull_pos.get('span_coverage_avg'))} "
                f"| {_fmt(qfull_pos.get('full_page_f1_avg'))} "
                f"| {qfull_neg.get('cases', 0)} | {_fmt(qfull_neg.get('fpr'))} |",
                "",
            ]

        ov = p.get("overall") or {}
        ov_pos, ov_neg = ov.get("positive", {}), ov.get("negative", {})
        if ov_pos or ov_neg:
            pos_n = ov_pos.get("cases", 0)
            neg_n = ov_neg.get("cases", 0)
            lines += [
                "**Toàn bộ item trả về** (mọi ca, không cắt top-k — đúng như UI hiển thị):",
                "| Dương tính | Gold trong bất kỳ item (`hit_all`) | `hit5_page` (metric cũ) "
                "| `hit5_score` | Precision all | Coverage all | Span Precision all |",
                "|---:|---:|---:|---:|---:|---:|---:|",
                f"| {pos_n} "
                f"| {_rate_count(ov_pos.get('hit_all'), ov_pos.get('hit_all_count', 0), pos_n)} "
                f"| {_rate_count(ov_pos.get('hit5_page'), ov_pos.get('hit5_page_count', 0), pos_n)} "
                f"| {_rate_count(ov_pos.get('hit5_score'), ov_pos.get('hit5_score_count', 0), pos_n)} "
                f"| {_fmt(ov_pos.get('precision_all_avg'))} "
                f"| {_fmt(ov_pos.get('coverage_all_avg'))} "
                f"| {_fmt(ov_pos.get('span_precision_all_avg'))} |",
                "",
                "**Nhóm `verified=true`** (các đoạn UI auto-select):",
                "| Dương tính | `verified_recall` | Verified precision (macro) "
                "| Verified precision (micro) | Âm tính | FPR bất kỳ item | `verified_fpr` |",
                "|---:|---:|---:|---:|---:|---:|---:|",
                f"| {pos_n} "
                f"| {_rate_count(ov_pos.get('verified_recall'), ov_pos.get('verified_recall_count', 0), pos_n)} "
                f"| {_fmt(ov_pos.get('verified_precision_macro'))} "
                f"| {_fmt(ov_pos.get('verified_precision_micro'))} "
                f"| {neg_n} "
                f"| {_rate_count(ov_neg.get('fpr_any'), ov_neg.get('fpr_any_count', 0), neg_n)} "
                f"| {_rate_count(ov_neg.get('verified_fpr'), ov_neg.get('verified_fpr_count', 0), neg_n)} |",
                "",
                "> `hit5_page` = 5 item đầu **theo thứ tự trang** (metric cũ, không phải top-5 "
                "theo score). `hit5_score` = 5 item tốt nhất theo `score`. `hit_all`/`verified_*` "
                "chấm trên **mọi item trả về**, gồm cả ca full-page và fallback.",
                "",
            ]

    lines += ["## 6. Mẫu câu trả lời (bằng chứng thô)"]
    if not samples:
        lines += ["(không có mẫu RAG trong run này)", ""]
    for sample in samples:
        lines.append(f"### {sample.get('qid', '?')} (answerable={sample.get('answerable')})")
        lines.append(f"- **Hỏi:** {sample.get('question', '')}")
        lines.append(f"- **Đáp:** {(sample.get('answer') or '(trống)')[:600]}")
        if sample.get("gold_text"):
            lines.append(f"- **Gold:** {sample['gold_text'][:300]}")
        if sample.get("n_sources") is not None:
            lines.append(f"- **Nguồn:** {sample.get('n_sources')} · "
                         f"lỗi: {sample.get('error') or '—'}")
        lines.append("")

    lines += [
        "## 7. Cách đọc & ranh giới",
        "- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.",
        "- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.",
        "- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.",
        "- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con "
        "chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.",
        "- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.",
        "",
        "## 8. Tái lập",
        f"- metrics_version: {m.get('metrics_version', manifest.get('metrics_version', '—'))}"
        f" · raw_schema_version: {manifest.get('raw_schema_version', '—')}",
        f"- eval_code_sha256: `{manifest.get('eval_code_sha256', '—')}`",
        f"- command: `{manifest.get('command', '—')}`",
        f"- dataset_version: `{manifest.get('dataset_version', '—')}`"
        f" · fingerprint: `{manifest.get('dataset_fingerprint', '—')}`",
        f"- provider/model/embedding: `{manifest.get('provider', '—')}` / "
        f"`{manifest.get('model', '—')}` / `{manifest.get('embedding_model', '—')}`",
        f"- provider_rpm: `{manifest.get('provider_rpm', '—')}`"
        f" · search_rpm: `{manifest.get('search_rpm', '—')}`"
        f" · rag_rpm: `{manifest.get('rag_rpm', '—')}`"
        f" · pagematch_rpm: `{manifest.get('pagematch_rpm', '—')}`",
        f"- folder_id: `{manifest.get('folder_id', '—')}`"
        f" · folder_mode: `{manifest.get('folder_mode', '—')}`",
        "",
    ]
    if m.get("fatal_error"):
        lines += ["## 9. Lỗi fatal", f"`{m['fatal_error']}`", ""]
    return "\n".join(lines)


# ============================================================ So sánh nhiều model


def _run_metrics_dirs() -> list[Path]:
    if not RUNS_DIR.exists():
        return []
    return [d for d in sorted(RUNS_DIR.iterdir()) if (d / "metrics.json").exists()]


def _load_metrics_for_compare(run_dir: Path) -> dict | None:
    """Ưu tiên ``metrics.recomputed.json`` (định nghĩa metric hiện tại) nếu có.

    Recompute giữ nguyên mọi khóa cũ, nên bảng so sánh vẫn đọc được cả run cũ;
    run chưa recompute dùng ``metrics.json`` và các cột mới hiển thị ``—``.
    """
    candidates = [run_dir / "metrics.json", run_dir / "metrics.recomputed.json"]
    best: dict | None = None
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if best is None or data.get("metrics_version", 0) >= best.get("metrics_version", 0):
            best = data
    return best


def comparison_table() -> str:
    """Gộp metrics.json → bảng so sánh, nhóm theo dataset/top_k/modules/evidence."""
    groups: dict[tuple, list[dict]] = {}
    for run_dir in _run_metrics_dirs():
        data = _load_metrics_for_compare(run_dir)
        if data is None:
            continue
        man = data.get("manifest", {})
        key = (man.get("dataset_fingerprint", "?"), man.get("top_k", "?"),
               man.get("max_sources", 5), tuple(man.get("modules", [])),
               man.get("evidence_type", "unknown"))
        groups.setdefault(key, []).append({"run_dir": run_dir, "data": data, "man": man})

    lines = [
        "# So sánh tổ hợp model",
        "",
        "> Chỉ so sánh trong cùng nhóm "
        "`(dataset_fingerprint, top_k, max_sources, modules, evidence_type)`.",
        "> Run smoke/khác cấu hình được tách nhóm thay vì trộn vào một bảng.",
        "> Chỉ số PageMatch chính là `PM Hit@all`, `PM vRecall`, `PM vFPR` (chấm trên mọi "
        "item trả về / item `verified`). `PM Hit (seg)` và `PM FPR (seg)` giữ nghĩa cũ để "
        "đối chiếu lịch sử.",
        "",
    ]
    if not groups:
        return "\n".join(lines + ["(chưa có run nào có metrics.json)", ""])

    for (fingerprint, top_k, max_sources, modules, evidence), runs in groups.items():
        lines += [
            f"## Nhóm `{fingerprint}` · top_k={top_k} · max_sources={max_sources}"
            f" · modules={','.join(modules) or '—'} · evidence={evidence}",
            "",
            "| Model combo | Run | Search n | R@k | MRR | RAG n | Token-F1 | RAG p50 (ms) "
            "| Từ chối đúng | PM Hit@all | PM vRecall | PM vFPR | PM Hit (seg) | PM FPR (seg) "
            "| Tokens |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        versions = set()
        for item in runs:
            data, man = item["data"], item["man"]
            versions.add(data.get("metrics_version", man.get("metrics_version", 1)))
            search = data.get("search", {})
            rag_a = data.get("rag", {}).get("answerable", {})
            rag_u = data.get("rag", {}).get("unanswerable", {})
            pm = data.get("pagematch", {})
            qpos = pm.get("quality", {}).get("positive", pm.get("positive", {}))
            qneg = pm.get("quality", {}).get("negative", pm.get("negative", {}))
            ov_pos = pm.get("overall", {}).get("positive", {})
            ov_neg = pm.get("overall", {}).get("negative", {})
            f1 = rag_a.get("answer_token_f1_gold_avg", rag_a.get("answer_f1_gold_avg"))
            lines.append(
                f"| `{man.get('model_label', '?')}` | {man.get('run_id', item['run_dir'].name)} "
                f"| {search.get('completed', search.get('queries', '—'))} "
                f"| {_fmt(search.get('recall_at_k'))} | {_fmt(search.get('mrr'))} "
                f"| {rag_a.get('completed', rag_a.get('questions', '—'))} | {_fmt(f1)} "
                f"| {_fmt(rag_a.get('total_ms_p50'))} | {_fmt(rag_u.get('refusal_rate'))} "
                f"| {_fmt(ov_pos.get('hit_all'))} | {_fmt(ov_pos.get('verified_recall'))} "
                f"| {_fmt(ov_neg.get('verified_fpr'))} "
                f"| {_fmt(qpos.get('hit_rate'))} | {_fmt(qneg.get('fpr'))} "
                f"| {data.get('tokens_consumed', '—')} |")
        lines += [""]
        if len(versions) > 1:
            lines += [
                f"> ⚠ Nhóm này trộn metrics_version {sorted(versions)} — run chưa recompute "
                "thiếu cột PageMatch mới. Chạy `--recompute` cho run đó trước khi so sánh "
                "các cột `PM Hit@all`/`PM vRecall`/`PM vFPR`.",
                "",
            ]
    return "\n".join(lines)


# ============================================================ Tái tạo metrics từ raw


_CASE_CLASSES = {
    "ingest": IngestCase,
    "search": SearchCase,
    "rag": RagCase,
    "pagematch": PageMatchCase,
}


def read_raw(run_dir: Path) -> dict[str, list]:
    groups: dict[str, list] = {name: [] for name in _CASE_CLASSES}
    path = run_dir / "raw_results.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Không có {path}")
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} JSON hỏng: {exc}") from exc
        module = data.get("module")
        if module not in _CASE_CLASSES:
            raise ValueError(f"{path}:{line_no} module lạ: {module!r}")
        groups[module].append(case_from_dict(_CASE_CLASSES[module], data))
    return groups


def recompute_metrics(run_dir: Path) -> dict:
    """Tái tạo metrics từ raw_results.jsonl + manifest; không gọi mạng."""
    manifest_path = run_dir / "run_manifest.json"
    old_metrics_path = run_dir / "metrics.json"
    manifest = {}
    old = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if old_metrics_path.exists():
        old = json.loads(old_metrics_path.read_text(encoding="utf-8"))
        manifest = manifest or old.get("manifest", {})

    groups = read_raw(run_dir)
    out: dict = {"run_id": manifest.get("run_id", run_dir.name),
                 "metrics_version": METRICS_VERSION, "manifest": manifest}
    if groups["ingest"]:
        out["ingest"] = aggregate_ingest(groups["ingest"])
    if groups["search"]:
        stored = old.get("search", {})
        out["search"] = aggregate_search(
            groups["search"], int(manifest.get("top_k", 5)),
            int(manifest.get("corpus_notes") or stored.get("corpus_notes", 0)),
            int(manifest.get("corpus_documents") or stored.get("corpus_documents", 0))
            or None)
    if groups["rag"]:
        out["rag"] = aggregate_rag(groups["rag"])
    if groups["pagematch"]:
        out["pagematch"] = aggregate_pagematch(
            groups["pagematch"], int(manifest.get("pagematch_top_k", 5)))
    # Không tái tạo được từ raw: quota/token tiêu thụ (metadata phía server).
    for key in ("tokens_consumed", "quota", "fatal_error"):
        if key in old:
            out[key] = old[key]
    return out


def _diff(expected, actual, path: str = "") -> list[str]:
    diffs: list[str] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key in {"manifest", "quota", "tokens_consumed", "fatal_error",
                       "metrics_version"}:
                continue
            if key not in expected:
                # Trường mới của phiên bản metrics hiện tại — raw/metrics cũ không có.
                # Không tính là lệch: recompute chỉ cần tái tạo đúng những gì đã lưu.
                continue
            diffs += _diff(expected.get(key), actual.get(key), f"{path}.{key}" if path else key)
    elif expected != actual:
        diffs.append(f"{path}: stored={expected!r} recomputed={actual!r}")
    return diffs


def recompute_command(target: str) -> int:
    if target == "latest":
        dirs = [d for d in _run_metrics_dirs() if (d / "raw_results.jsonl").exists()]
        if not dirs:
            print("Không có run nào có raw_results.jsonl")
            return 1
        run_dir = dirs[-1]
    else:
        run_dir = Path(target)
        if not run_dir.is_absolute() and not run_dir.exists():
            run_dir = RUNS_DIR / target
    try:
        recomputed = recompute_metrics(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[recompute] {exc}")
        return 1
    write_json(run_dir / "metrics.recomputed.json", recomputed)
    stored_path = run_dir / "metrics.json"
    if stored_path.exists():
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        diffs = _diff(stored, recomputed)
        if diffs:
            print(f"[recompute] {run_dir.name}: {len(diffs)} khác biệt")
            for diff in diffs[:40]:
                print(f"  - {diff}")
            print(f"→ {run_dir / 'metrics.recomputed.json'}")
            return 1
        print(f"[recompute] {run_dir.name}: ✓ khớp hoàn toàn")
    else:
        print(f"[recompute] {run_dir.name}: đã tạo metrics.recomputed.json")
    return 0


# ============================================================ Pipeline chính


def run_pipeline(cfg: SteadyConfig) -> Path:
    client = BackendClient(cfg)
    run_dir: Path | None = None
    raw_writer: RawWriter | None = None
    manifest: dict = {}
    metrics: dict = {}
    samples: list[dict] = []
    documents_by_file: dict[str, IngestedDocument] = {}
    note_cache: dict[str, str] = {}  # toàn văn note — dùng chung Search (AnswerHit) + RAG
    folder_id: str | None = None
    fatal_error: str | None = None

    try:
        health = client.health()
        if health.get("status") != "ok":
            raise RuntimeError(f"Backend chưa sẵn sàng: {health}")
        client.login()
        try:
            readiness = client.ready()
        except Exception as exc:  # noqa: BLE001 — readiness chỉ là metadata
            readiness = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"[backend] {cfg.api_base_url} — health ok")

        bundle = load_dataset(cfg)
        print_dataset_report(bundle)
        validate_bundle(bundle, allow_partial=cfg.allow_partial)
        evidence_type = resolve_evidence_type(cfg, bundle)
        dataset_version = cfg.dataset_version or bundle.fingerprint

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        safe_label = sanitize_id(cfg.model_label, "model")
        safe_tag = sanitize_id(cfg.tag) if cfg.tag else ""
        run_id = f"{timestamp}_{safe_label}" + (f"_{safe_tag}" if safe_tag else "")
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        raw_writer = RawWriter(run_dir / "raw_results.jsonl")

        manifest = {
            "run_id": run_id,
            "manifest_version": 3,
            "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metrics_version": METRICS_VERSION,
            "raw_schema_version": RAW_SCHEMA_VERSION,
            "eval_code_sha256": eval_code_sha256(),
            "command": " ".join([Path(sys.argv[0]).name, *sys.argv[1:]]),
            "cwd": str(Path.cwd()),
            "python": platform.python_version(),
            "git_commit": git_commit(),
            "backend_health": health,
            "backend_ready": readiness,
            "api_base_url": cfg.api_base_url,
            "model_label": cfg.model_label,
            "provider": cfg.provider,
            "model": cfg.model,
            "embedding_model": cfg.embedding_model,
            "temperature": cfg.temperature,
            "evaluator": cfg.evaluator,
            "evidence_type": evidence_type,
            "dataset_version": dataset_version,
            "dataset_fingerprint": bundle.fingerprint,
            "dataset_stats": bundle.stats,
            "dataset_issues": bundle.issues,
            "included_pairs": len(bundle.pairs),
            "excluded_rows": bundle.excluded_rows,
            "top_k": cfg.top_k,
            "max_sources": cfg.max_sources,
            "pagematch_top_k": cfg.pagematch_top_k,
            "split_chars": cfg.split_chars,
            "truncate_long": cfg.truncate_long,
            "modules": cfg.modules,
            "folder_mode": cfg.folder_mode,
            "folder_id": None,
            "eval_user": cfg.email,
            "fresh_notes": cfg.fresh_notes,
            "cleanup_notes": cfg.cleanup_notes,
            "allow_degraded": cfg.allow_degraded,
            "max_retries_429": cfg.max_retries_429,
            "provider_rpm": cfg.provider_rpm,
            "search_rpm": cfg.search_rpm,
            "rag_rpm": cfg.rag_rpm,
            "pagematch_rpm": cfg.pagematch_rpm,
            "rpm_config": {
                "provider_rpm": cfg.provider_rpm,
                "search_rpm": cfg.search_rpm,
                "rag_rpm": cfg.rag_rpm,
                "pagematch_rpm": cfg.pagematch_rpm,
            },
            "max_concurrency": 1,
        }
        write_json(run_dir / "run_manifest.json", manifest)

        needs_ingest = {"search", "rag"} & set(cfg.modules)
        if needs_ingest and cfg.folder_mode == "run":
            folder = client.find_or_create_folder(f"steady {run_id}")
            folder_id = folder.get("id")
            if not folder_id:
                raise RuntimeError(f"Backend không trả folder_id: {folder}")
            manifest["folder_id"] = folder_id
            write_json(run_dir / "run_manifest.json", manifest)
            print(f"[corpus] folder riêng của run: {folder_id}")

        quota_before = _safe_quota(client)
        metrics = {"run_id": run_id, "metrics_version": METRICS_VERSION,
                   "manifest": manifest}

        if needs_ingest:
            print("\n--- §3.1 Ingest (POST /notes → chờ index) ---")
            run_started_at = datetime.datetime.now(datetime.timezone.utc)
            ingest_cases, documents_by_file = ingest_sources(
                client, bundle, cfg, run_id, folder_id=folder_id, emit=raw_writer.emit,
                run_started_at=run_started_at)
            metrics["ingest"] = aggregate_ingest(ingest_cases)
            bad = not_ready_files(ingest_cases)
            if bad and not cfg.allow_degraded:
                raise RuntimeError(
                    f"{len(bad)} file chưa READY: {bad}. Kiểm tra worker rồi chạy lại "
                    "(hoặc --allow-degraded để chấp nhận metric bị suy giảm).")

        if "search" in cfg.modules:
            print(f"\n--- §3.2 Search (POST /search, max_sources={cfg.max_sources}, "
                  f"top_k={cfg.top_k}) ---")
            notes = client.list_notes(folder_id)
            corpus = len(notes)
            corpus_documents = len({
                str(n.get("document_id")) if n.get("document_id") else str(n.get("id"))
                for n in notes})
            manifest["corpus_notes"] = corpus
            manifest["corpus_documents"] = corpus_documents
            write_json(run_dir / "run_manifest.json", manifest)
            search_cases = run_search(client, bundle, documents_by_file, cfg.top_k,
                                      cfg.max_sources, folder_id=folder_id,
                                      emit=raw_writer.emit, note_cache=note_cache)
            metrics["search"] = aggregate_search(search_cases, cfg.top_k, corpus,
                                                 corpus_documents)

        if "rag" in cfg.modules:
            print("\n--- §3.3 RAG (POST /ai/chat, SSE) ---")
            rag_cases = run_rag(client, bundle, folder_id=folder_id, emit=raw_writer.emit,
                                note_cache=note_cache)
            metrics["rag"] = aggregate_rag(rag_cases)
            first_ok = next((c for c in rag_cases if c.answerable and not c.error), None)
            first_no = next((c for c in rag_cases if not c.answerable), None)
            for case in (first_ok, first_no):
                if case:
                    samples.append({"qid": case.qid, "answerable": case.answerable,
                                    "question": case.question, "answer": case.answer,
                                    "gold_text": case.gold_text, "n_sources": case.n_sources,
                                    "error": case.error})

        if "pagematch" in cfg.modules:
            print("\n--- §3.4 PageMatch (POST /ai/page-match) ---")
            pm_cases = run_pagematch(client, bundle, emit=raw_writer.emit)
            metrics["pagematch"] = aggregate_pagematch(pm_cases, cfg.pagematch_top_k)

        quota_after = _safe_quota(client)
        metrics["quota"] = {"before": quota_before, "after": quota_after}
        if "error" in quota_before or "error" in quota_after:
            metrics["tokens_consumed"] = None
        else:
            try:
                metrics["tokens_consumed"] = max(
                    0, int(quota_after.get("used_tokens", 0))
                    - int(quota_before.get("used_tokens", 0)))
            except (TypeError, ValueError):
                metrics["tokens_consumed"] = None

        if cfg.cleanup_notes:
            ids = list(dict.fromkeys(
                pid for doc in documents_by_file.values() for pid in doc.part_ids))
            if ids:
                try:
                    deleted = client.bulk_delete_notes(ids)
                    print(f"\n[cleanup] Đã xoá {deleted} ghi chú của pipeline")
                except Exception as exc:  # noqa: BLE001 — cleanup không làm hỏng kết quả
                    print(f"[cleanup] Không xoá được ghi chú: {exc}")
            if folder_id:
                try:
                    client.delete_folder(folder_id)
                    print(f"[cleanup] Đã xoá folder {folder_id}")
                except Exception as exc:  # noqa: BLE001 — cleanup không làm hỏng kết quả
                    print(f"[cleanup] Không xoá được folder: {exc}")

        print(f"\n=== XONG. tokens tiêu thụ: {metrics.get('tokens_consumed')} "
              f"· artifact: {run_dir} ===")
    except Exception as exc:  # noqa: BLE001 — vẫn ghi artifact một phần
        fatal_error = f"{type(exc).__name__}: {exc}"
        metrics["fatal_error"] = fatal_error
        if manifest:
            manifest["fatal_error"] = fatal_error
        raise
    finally:
        if raw_writer is not None:
            raw_writer.close()
        client.close()
        if run_dir is not None:
            if manifest:
                write_json(run_dir / "run_manifest.json", manifest)
            write_json(run_dir / "metrics.json", metrics or {"fatal_error": fatal_error})
            (run_dir / "report.md").write_text(
                build_report_md(manifest, metrics or {"fatal_error": fatal_error},
                                bundle_issues=manifest.get("dataset_issues"),
                                samples=samples),
                encoding="utf-8")
            print(f"    Báo cáo: {run_dir / 'report.md'}")
            if fatal_error:
                print(f"    [fatal] {fatal_error} — artifact một phần đã được giữ lại")
    return run_dir  # type: ignore[return-value]


# ============================================================ CLI


def parse_args() -> argparse.Namespace:
    env = load_env(BASE_DIR / ".env")
    parser = argparse.ArgumentParser(description="Steady evaluation — đánh giá QuickAssist qua HTTP thật")
    parser.add_argument("--base-url", default=env.get("STEADY_API_BASE_URL", "http://localhost:8000/api/v1"))
    parser.add_argument("--email", default=env.get("STEADY_EMAIL", "steady-eval@quickassist.local"))
    parser.add_argument("--access-token", default=env.get("STEADY_ACCESS_TOKEN", ""))
    parser.add_argument("--model-label", default=env.get("STEADY_MODEL_LABEL", "unlabeled"),
                        help="Nhãn tổ hợp LLM + embedding của run này (ví dụ 'bonsai9b+gte-qwen2')")
    parser.add_argument("--provider", default=env.get("STEADY_PROVIDER", ""))
    parser.add_argument("--model", default=env.get("STEADY_MODEL", ""))
    parser.add_argument("--embedding-model", default=env.get("STEADY_EMBEDDING_MODEL", ""))
    parser.add_argument("--temperature", default=env.get("STEADY_TEMPERATURE", ""))
    parser.add_argument("--evaluator", default=env.get("STEADY_EVALUATOR", ""))
    parser.add_argument("--evidence-type", default=env.get("STEADY_EVIDENCE_TYPE", "auto"),
                        choices=["auto", "smoke", "quality", "failure"])
    parser.add_argument("--dataset-version", default=env.get("STEADY_DATASET_VERSION", ""))
    parser.add_argument("--dataset-dir", default=str(BASE_DIR / "dataset"))
    parser.add_argument("--modules", default=",".join(ALL_MODULES),
                        help=f"Danh sách module: {','.join(ALL_MODULES)}")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Số NOTE đầu (sau khi phẳng nguồn) dùng cho Recall/MRR/AnswerHit")
    parser.add_argument("--max-sources", type=int,
                        default=int(env.get("STEADY_MAX_SOURCES", "5")),
                        help="SearchIn.max_sources (1..20) — số NGUỒN/domain API trả")
    parser.add_argument("--pagematch-top-k", type=int, default=5,
                        help="Chỉ chấm top-k block PageMatch (backend có thể trả tới 15)")
    parser.add_argument("--split-chars", type=int,
                        default=int(env.get("STEADY_SPLIT_CHARS", "20000")),
                        help="Ngưỡng chia part cho file dài (≤ MAX_NOTE_CHARS; target 90%%)")
    parser.add_argument("--truncate-long", action="store_true",
                        help="Baseline cũ: cắt file > trần thay vì chia part (để A/B)")
    parser.add_argument("--tag", default="", help="Hậu tố run_id")
    parser.add_argument("--folder-mode", choices=["run", "shared"], default="run",
                        help="run = thư mục riêng mỗi run (mặc định); shared = dùng Inbox")
    parser.add_argument("--fresh-notes", action="store_true",
                        help="Idempotency key theo run → tạo ghi chú mới mỗi lần chạy")
    parser.add_argument("--cleanup-notes", action="store_true",
                        help="Xoá ghi chú + thư mục của run sau khi chấm xong")
    parser.add_argument("--allow-partial", action="store_true",
                        help="Vẫn chạy dù dataset còn dòng lỗi/bị loại (mặc định fail-fast)")
    parser.add_argument("--allow-degraded", action="store_true",
                        help="Vẫn chấm dù có note chưa READY (mặc định dừng)")
    parser.add_argument("--wait-index-timeout", type=float, default=120.0)
    parser.add_argument("--pagematch-timeout", type=float, default=90.0)
    parser.add_argument("--max-retries-429", type=int, default=5)
    parser.add_argument("--provider-rpm", type=float,
                        default=float(env["STEADY_PROVIDER_RPM"]) if env.get("STEADY_PROVIDER_RPM") else None,
                        help="Nhịp gọi provider (RPM) chủ động để chống vượt hạn mức (ví dụ 10)")
    parser.add_argument("--search-rpm", type=float,
                        default=float(env["STEADY_SEARCH_RPM"]) if env.get("STEADY_SEARCH_RPM") else None,
                        help="Hạn mức RPM chủ động riêng cho Search (POST /search)")
    parser.add_argument("--rag-rpm", type=float,
                        default=float(env["STEADY_RAG_RPM"]) if env.get("STEADY_RAG_RPM") else None,
                        help="Hạn mức RPM chủ động riêng cho RAG (POST /ai/chat)")
    parser.add_argument("--pagematch-rpm", type=float,
                        default=float(env["STEADY_PAGEMATCH_RPM"]) if env.get("STEADY_PAGEMATCH_RPM") else None,
                        help="Hạn mức RPM chủ động riêng cho PageMatch (POST /ai/page-match)")
    parser.add_argument("--validate", action="store_true", help="Chỉ nạp + kiểm chứng dataset (§2)")
    parser.add_argument("--compare", action="store_true", help="Gộp bảng so sánh mọi run trong runs/")
    parser.add_argument("--recompute", nargs="?", const="latest", default=None,
                        metavar="RUN_DIR", help="Tái tạo metrics từ raw_results.jsonl rồi diff")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.compare:
        table = comparison_table()
        out = RUNS_DIR / "MODEL_COMPARISON.md"
        RUNS_DIR.mkdir(exist_ok=True)
        out.write_text(table, encoding="utf-8")
        print(table)
        print(f"→ {out}")
        return

    if args.recompute is not None:
        sys.exit(recompute_command(args.recompute))

    cfg = SteadyConfig(
        api_base_url=args.base_url, email=args.email, access_token=args.access_token,
        dataset_dir=Path(args.dataset_dir),
        modules=[m.strip() for m in args.modules.split(",") if m.strip()],
        top_k=args.top_k, max_sources=args.max_sources,
        pagematch_top_k=args.pagematch_top_k,
        split_chars=args.split_chars, truncate_long=args.truncate_long,
        model_label=args.model_label, tag=args.tag,
        folder_mode=args.folder_mode,
        fresh_notes=args.fresh_notes, cleanup_notes=args.cleanup_notes,
        allow_partial=args.allow_partial, allow_degraded=args.allow_degraded,
        wait_index_timeout_s=args.wait_index_timeout,
        pagematch_timeout_s=args.pagematch_timeout,
        max_retries_429=args.max_retries_429,
        provider_rpm=args.provider_rpm,
        search_rpm=args.search_rpm,
        rag_rpm=args.rag_rpm,
        pagematch_rpm=args.pagematch_rpm,
        provider=args.provider, model=args.model,
        embedding_model=args.embedding_model, temperature=args.temperature,
        evaluator=args.evaluator, evidence_type=args.evidence_type,
        dataset_version=args.dataset_version,
    )
    unknown = set(cfg.modules) - set(ALL_MODULES)
    if unknown:
        sys.exit(f"Module không hợp lệ: {unknown}")
    if not cfg.modules:
        sys.exit("Cần ít nhất một module trong --modules")
    if not 1 <= cfg.max_sources <= 20:
        sys.exit("--max-sources phải trong khoảng 1..20 (SearchIn.max_sources)")
    if cfg.top_k < 1:
        sys.exit("--top-k phải >= 1")
    if not 1 <= cfg.split_chars <= cfg.max_note_chars:
        sys.exit(f"--split-chars phải trong khoảng 1..{cfg.max_note_chars} (MAX_NOTE_CHARS)")

    if args.validate:
        bundle = load_dataset(cfg)
        print_dataset_report(bundle)
        sys.exit(1 if bundle.issues else 0)

    try:
        run_dir = run_pipeline(cfg)
        print(f"    So sánh: python3 run_evaluation.py --compare")
        print(f"    Tái lập: python3 run_evaluation.py --recompute {run_dir.name}")
    except DatasetError as exc:
        sys.exit(f"[dataset] {exc}")
    except Exception as exc:  # noqa: BLE001 — CLI gọn, artifact đã ghi trong finally
        sys.exit(f"[fatal] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()