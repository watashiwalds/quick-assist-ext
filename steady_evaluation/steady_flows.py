"""§3 — Sử dụng các chức năng của hệ thống qua HTTP (mô phỏng hành trình extension).

Bốn luồng, gọi đúng API thật của backend:
  1. ingest    : POST /notes (+Idempotency-Key) → poll GET /notes/{id} tới khi
                 index_status ≠ PROCESSING (worker embed thật, có giới hạn chờ).
                 Chỉ chạy khi cần (search/rag); pagematch là stateless không cần.
  2. search    : POST /search — truy xuất hybrid SQL thật (pgvector + ts_rank_cd + RRF).
  3. rag       : POST /ai/chat (SSE) — sources → delta… → done|error, chốt quota thật.
  4. pagematch : POST /ai/page-match — .html → field `html` (Trafilatura),
                 .txt → field `text` (luồng văn bản dán).

Mỗi luồng trả về bản ghi case thô (§4 chấm); mọi độ trễ đo tại lớp HTTP.
Mỗi case được ghi ngay qua callback ``emit`` (raw_results.jsonl) và lỗi từng ca
được bắt riêng — một request hỏng không làm mất cả run.

Lưu ý idempotency: với `--folder-mode run` (mặc định), khoá idempotency theo run
để note không bị tái dùng từ folder của run trước. Với `--folder-mode shared`,
dùng khoá bền theo nội dung file → chạy lại KHÔNG tạo note trùng (đúng hợp đồng
chống trùng của backend); `--fresh-notes` luôn đổi sang khoá theo run.
"""

from __future__ import annotations

import datetime
import hashlib
import time
from typing import Callable

from steady_backend import BackendClient, SteadyConfig
from steady_dataset import DatasetBundle
from steady_metrics import (IngestCase, PageMatchCase, RagCase, SearchCase,
                            citation_indices, normalize_text, numbers_of)

_INDEX_TERMINAL = {"READY", "FAILED", "SKIPPED"}
_NO_CONTEXT_MARKERS = (
    "minh khong tim thay ghi chu nao lien quan",
    "khong tim thay ghi chu nao lien quan",
)

Emit = Callable[[str, object], None] | None


def _emit(emit: Emit, module: str, case) -> None:
    if emit is not None:
        emit(module, case)


def _idempotency_key(cfg: SteadyConfig, run_scope: str, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]
    # Với folder riêng mỗi run, khóa PHẢI theo run: khóa "shared" sẽ trả lại note
    # của folder run trước (backend idempotency theo user+key), phá cô lập corpus.
    scope = run_scope if (cfg.fresh_notes or cfg.folder_mode == "run") else "shared"
    return f"steady-{scope}-{digest}"


def not_ready_files(cases: list[IngestCase]) -> list[str]:
    """Tên file chưa READY — runner dùng làm cổng trước khi chấm search/RAG."""
    return [c.file for c in cases if c.index_status != "READY"]


# ============================================================ 1. Nạp ghi chú + chờ index


def _created_during_run(note: dict, status_code: int,
                        run_started_at: datetime.datetime | None) -> bool:
    """POST /notes trả 201 cho CẢ idempotent replay (API_REFERENCE §8.1).

    Vì vậy không thể suy ra "tạo mới" chỉ từ status code. So ``created_at``
    với thời điểm bắt đầu run (dung sai 5 s cho lệch đồng hồ); nếu không có
    mốc/không parse được thì giữ fallback theo status code.
    """
    if status_code != 201 or run_started_at is None or not note.get("created_at"):
        return status_code == 201
    try:
        created_at = datetime.datetime.fromisoformat(
            str(note["created_at"]).replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)
        return created_at >= run_started_at - datetime.timedelta(seconds=5)
    except (TypeError, ValueError):
        return status_code == 201


def ingest_sources(client: BackendClient, bundle: DatasetBundle, cfg: SteadyConfig,
                   run_scope: str, folder_id: str | None = None,
                   emit: Emit = None,
                   run_started_at: datetime.datetime | None = None
                   ) -> tuple[list[IngestCase], dict[str, str]]:
    """Nạp từng file thành ghi chú; trả về case + map file→note_id.

    Lỗi từng file được ghi thành case ``index_status=ERROR`` và luồng tiếp tục;
    runner quyết định dừng hay không dựa trên ``not_ready_files``.
    """
    cases: list[IngestCase] = []
    note_id_by_file: dict[str, str] = {}
    for src in bundle.sources:
        content = src.plain
        truncated = False
        if len(content) > cfg.max_note_chars:
            content, truncated = content[:cfg.max_note_chars], True
            print(f"  [ingest] {src.name}: cắt còn {cfg.max_note_chars} ký tự (giới hạn backend)")
        title = src.path.stem[:500]
        try:
            status_code, note, create_ms = client.create_note(
                content, title, _idempotency_key(cfg, run_scope, content), folder_id)
        except Exception as exc:  # noqa: BLE001 — cô lập lỗi từng file
            case = IngestCase(file=src.name, note_id="", index_status="ERROR",
                              content_chars=len(content), truncated=truncated,
                              create_ms=0.0, wait_index_ms=0.0, folder_id=folder_id,
                              error=f"{type(exc).__name__}: {exc}")
            cases.append(case)
            _emit(emit, "ingest", case)
            print(f"  [ingest] {src.name}: LỖI {case.error}")
            continue

        note_id = note.get("id", "")
        if note_id:
            note_id_by_file[src.name] = note_id
        created = _created_during_run(note, status_code, run_started_at)

        t0 = time.perf_counter()
        status = note.get("index_status", "PROCESSING")
        fetch_error = None
        while status == "PROCESSING" and (time.perf_counter() - t0) < cfg.wait_index_timeout_s:
            time.sleep(cfg.poll_interval_s)
            try:
                note, _ = client.get_note(note_id)
            except Exception as exc:  # noqa: BLE001 — ghi lại rồi dừng chờ
                fetch_error = f"{type(exc).__name__}: {exc}"
                break
            status = note.get("index_status", "PROCESSING")
        wait_ms = (time.perf_counter() - t0) * 1000
        if status == "PROCESSING":
            status = "TIMEOUT"  # hết giờ chờ — ghi rõ, không giả định
            print(f"  [ingest] {src.name}: TIMEOUT chờ index sau {cfg.wait_index_timeout_s}s")

        case = IngestCase(file=src.name, note_id=note_id, index_status=status,
                          content_chars=len(content), truncated=truncated,
                          create_ms=round(create_ms, 2), wait_index_ms=round(wait_ms, 2),
                          created=created, folder_id=folder_id, error=fetch_error)
        cases.append(case)
        _emit(emit, "ingest", case)
        kind = "tạo mới" if created else "idempotent replay"
        print(f"  [ingest] {src.name} → {status} ({kind}, create {create_ms:.0f} ms, "
              f"wait {wait_ms:.0f} ms)")
    return cases, note_id_by_file


# ============================================================ 2. Tìm kiếm ngữ nghĩa


def _flatten_sources(sources: list[dict]) -> list[dict]:
    """Phẳng ``sources[].notes[]`` theo thứ hạng nguồn rồi note trong nguồn.

    Gắn ``source_rank``/``source_domain``/``source_label`` vào từng note để raw
    artifact giữ được ngữ cảnh nhóm. Giới hạn top-k chỉ áp dụng cho metric,
    không cắt dữ liệu thô (aggregate tự cắt theo top-k).
    """
    notes: list[dict] = []
    for source in sources:
        for note in source.get("notes", []) or []:
            notes.append({
                **note,
                "source_rank": source.get("source_rank"),
                "source_domain": source.get("domain"),
                "source_label": source.get("label"),
            })
    return notes


def _answer_in_notes(client: BackendClient, notes: list[dict], gold_text: str,
                     cache: dict[str, str]) -> bool:
    """Gold nguyên văn có nằm trong top-k note không.

    Search chỉ trả ``snippet`` ~240 ký tự, trong khi gold của dataset có thể dài
    hơn. Vì vậy nếu snippet không khớp, fetch toàn văn note (cache theo run) để
    tránh báo âm tính giả. Fetch lỗi → chỉ dùng snippet, không làm hỏng case.
    """
    norm_gold = normalize_text(gold_text)
    if not norm_gold:
        return False
    for note in notes:
        if norm_gold in normalize_text(str(note.get("snippet", ""))):
            return True
        note_id = str(note.get("note_id", ""))
        if not note_id:
            continue
        if note_id not in cache:
            try:
                note_body, _ = client.get_note(note_id)
                cache[note_id] = note_body.get("content", "") or ""
            except Exception:  # noqa: BLE001 — fallback sang snippet
                cache[note_id] = ""
        if norm_gold in normalize_text(cache[note_id]):
            return True
    return False


def run_search(client: BackendClient, bundle: DatasetBundle, note_id_by_file: dict[str, str],
               top_k: int, max_sources: int = 5, folder_id: str | None = None,
               emit: Emit = None, note_cache: dict[str, str] | None = None) -> list[SearchCase]:
    cases: list[SearchCase] = []
    cache = note_cache if note_cache is not None else {}
    for pair in bundle.pairs:
        if not pair.answerable:
            continue  # câu âm tính không có gold note — không chấm search
        gold = note_id_by_file.get(pair.source_file, "")
        try:
            sources, elapsed = client.search(pair.question, max_sources, folder_id)
            notes = _flatten_sources(sources)
            ranked: list[str] = []
            for note in notes:
                note_id = str(note.get("note_id", ""))
                if note_id and note_id not in ranked:  # giữ thứ hạng tốt nhất
                    ranked.append(note_id)
            answer_hit = _answer_in_notes(client, notes[:top_k], pair.gold_text, cache)
            case = SearchCase(qid=pair.qid, query=pair.question, gold_note_id=gold,
                              ranked_note_ids=ranked, answer_hit=answer_hit,
                              latency_ms=round(elapsed, 2), items=notes,
                              folder_id=folder_id, n_sources=len(sources),
                              max_sources=max_sources, sources=sources)
        except Exception as exc:  # noqa: BLE001 — cô lập lỗi từng truy vấn
            case = SearchCase(qid=pair.qid, query=pair.question, gold_note_id=gold,
                              ranked_note_ids=[], answer_hit=False, latency_ms=0.0,
                              folder_id=folder_id, max_sources=max_sources,
                              error=f"{type(exc).__name__}: {exc}")
        cases.append(case)
        _emit(emit, "search", case)
        hit_rank = next((i for i, nid in enumerate(case.ranked_note_ids[:top_k], 1)
                         if nid == gold), None)
        flag = (f" lỗi={case.error}" if case.error
                else f" gold @ hạng {hit_rank or '—'} · {case.n_sources} nguồn/"
                     f"{len(case.items)} note")
        print(f"  [search] {pair.qid}: {flag} ({case.latency_ms:.0f} ms)")
    return cases


# ============================================================ 3. Hỏi đáp RAG (SSE)


def _note_texts(client: BackendClient, note_ids: list[str], cache: dict[str, str]) -> list[str]:
    """Lấy toàn văn note nguồn (cache theo run) để kiểm tra số trong ngữ cảnh.

    SSE ``sources`` chỉ có snippet ~240 ký tự; số nằm ngoài snippet sẽ bị coi là
    "không có trong ngữ cảnh" nếu chỉ dùng snippet. Fetch note một lần/note.
    """
    texts: list[str] = []
    for note_id in note_ids:
        if not note_id:
            continue
        if note_id not in cache:
            try:
                note, _ = client.get_note(note_id)
                cache[note_id] = note.get("content", "") or ""
            except Exception:  # noqa: BLE001 — fallback sang snippet, đã ghi ở case
                cache[note_id] = ""
        if cache[note_id]:
            texts.append(cache[note_id])
    return texts


def run_rag(client: BackendClient, bundle: DatasetBundle, folder_id: str | None = None,
            emit: Emit = None, note_cache: dict[str, str] | None = None) -> list[RagCase]:
    cases: list[RagCase] = []
    cache = note_cache if note_cache is not None else {}
    for pair in bundle.pairs:
        try:
            stream = client.chat_sse(pair.question, folder_id)
            answer_parts: list[str] = []
            sources: list[dict] = []
            tokens_used, error = 0, None
            for event_type, data in stream.events:
                if event_type == "sources":
                    # Controller gom SSE: delta bọc {"text": ...}, các sự kiện khác gửi data nguyên vẹn
                    sources = data if isinstance(data, list) else data.get("sources", [])
                elif event_type == "delta":
                    answer_parts.append(data.get("text", ""))
                elif event_type == "done":
                    tokens_used = int(data.get("tokens_used", 0))
                elif event_type == "error":
                    error = f"{data.get('code', '?')}: {data.get('message', '')}"
            answer = "".join(answer_parts)
            note_ids = list(dict.fromkeys(s.get("note_id", "") for s in sources))
            note_texts = _note_texts(client, note_ids, cache)
            # Ngữ cảnh thật = câu hỏi + toàn văn note nguồn (không cộng gold).
            context_text = " ".join([pair.question, *note_texts])
            if not note_texts:  # không fetch được note → dùng snippet làm fallback
                context_text += " " + " ".join(s.get("snippet", "") for s in sources)
            allowed_numbers = numbers_of(context_text)
            violations = sorted(numbers_of(answer) - allowed_numbers)
            cites = citation_indices(answer)
            citation_valid = bool(cites) and all(1 <= i <= len(sources) for i in cites)
            norm_answer = normalize_text(answer)
            no_context = (len(sources) == 0
                          or any(marker in norm_answer for marker in _NO_CONTEXT_MARKERS))
            case = RagCase(
                qid=pair.qid, question=pair.question, answerable=pair.answerable,
                gold_text=pair.gold_text, answer=answer, source_note_ids=note_ids,
                sources=sources, n_sources=len(sources),
                citations_ok=(None if error else citation_valid),
                citation_count=len(cites), number_violations=violations,
                tokens_used=tokens_used, first_event_ms=round(stream.first_event_ms, 2),
                total_ms=round(stream.total_ms, 2), context_note_count=len(note_texts),
                context_chars=len(context_text), no_context=no_context,
                reference_answer=pair.reference_answer, error=error)
        except Exception as exc:  # noqa: BLE001 — cô lập lỗi từng câu
            case = RagCase(qid=pair.qid, question=pair.question, answerable=pair.answerable,
                           gold_text=pair.gold_text, answer="", citations_ok=None,
                           reference_answer=pair.reference_answer,
                           error=f"{type(exc).__name__}: {exc}")
        cases.append(case)
        _emit(emit, "rag", case)
        if case.error:
            print(f"  [rag] {pair.qid}: LỖI {case.error}")
        else:
            print(f"  [rag] {pair.qid}: {len(case.answer)} ký tự, {case.n_sources} nguồn"
                  f" (ctx {case.context_chars} ký tự), tokens={case.tokens_used}"
                  + (f", không ngữ cảnh" if case.no_context else ""))
    return cases


# ============================================================ 4. Tìm trong trang (PageMatch)


def run_pagematch(client: BackendClient, bundle: DatasetBundle,
                  emit: Emit = None) -> list[PageMatchCase]:
    cases: list[PageMatchCase] = []
    for pair in bundle.pairs:
        src = bundle.source_by_name[pair.source_file]
        try:
            if src.kind == "html":
                out, elapsed = client.page_match(pair.question, html=src.raw,
                                                 title=src.path.stem)
            else:
                out, elapsed = client.page_match(pair.question, text=src.raw,
                                                 title=src.path.stem)
            items = out.get("items", [])
            case = PageMatchCase(
                qid=pair.qid, source_file=pair.source_file,
                answerable=pair.answerable, gold_text=pair.gold_text,
                block_texts=[i.get("text", "") for i in items],
                verified=[bool(i.get("verified")) for i in items],
                items=items, mode=out.get("mode", ""), warning=out.get("warning"),
                match_ratio=float(out.get("match_ratio", 0.0)),
                truncated=bool(out.get("truncated")),
                total_chars=int(out.get("total_chars", 0) or 0),
                full_text=out.get("full_text"), source_text=src.plain,
                total_ms=round(elapsed, 2))
        except Exception as exc:  # noqa: BLE001 — cô lập lỗi từng ca
            case = PageMatchCase(qid=pair.qid, source_file=pair.source_file,
                                 answerable=pair.answerable, gold_text=pair.gold_text,
                                 source_text=src.plain,
                                 error=f"{type(exc).__name__}: {exc}")
        cases.append(case)
        _emit(emit, "pagematch", case)
        if case.error:
            print(f"  [pagematch] {pair.qid} @ {pair.source_file}: LỖI {case.error}")
        else:
            flag = f" (warning={case.warning})" if case.warning else ""
            print(f"  [pagematch] {pair.qid} @ {pair.source_file}: {len(case.block_texts)} block, "
                  f"mode={case.mode}, {case.total_ms:.0f} ms{flag}")
    return cases