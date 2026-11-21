# Steady Evaluation — pipeline đánh giá QuickAssist trên hệ thống chạy đầy đủ

Pipeline độc lập đánh giá **chất lượng + hiệu năng** của QuickAssist, khác căn bản so với
`../quickassist_ai_evaluation` (harness v2):

| | Harness v2 | steady_evaluation |
|---|---|---|
| Kết nối | Import service, quota shim | **HTTP thật** vào FastAPI + PostgreSQL/pgvector |
| Hybrid SQL, quota, rate-limit | Không kiểm chứng được | **Chạy thật**, đo được |
| Dataset | Hardcode trong code | **Folder + CSV** tách khỏi code |
| Độ trễ | Vòng lặp in-process (không đại diện) | **Lớp HTTP thật** (p50/p95 mỗi bước) |
| Model | Một cấu hình | Mỗi run = **một tổ hợp LLM + embedding**, có bảng so sánh |
| Cô lập corpus | — | **Thư mục riêng mỗi run** + `folder_id` cho search/chat |
| Tái lập | — | `eval_code_sha256`, `metrics_version`, `command`, `--recompute` |

> **Phạm vi hiện tại:** dataset trong repo có **11 nguồn** (8 HTML + 3 TXT) và 47 cặp hợp lệ
> (36 answerable, 11 unanswerable); 2 dòng bị loader loại vì `gold_text` không còn nguyên văn
> trong nguồn. Report tự đánh dấu `evidence_type=smoke` khi dataset < 20 cặp hoặc chưa đặt
> `--model-label`, và cảnh báo **không dùng số liệu để kết luận chất lượng** khi chưa đủ
> kích thước/nhãn chuẩn. Chạy full dataset nên sửa 2 dòng lỗi hoặc dùng `--allow-partial`.

> **Hợp đồng API đầy đủ:** [`API_REFERENCE.md`](API_REFERENCE.md) — tài liệu thiết kế cho
> automated evaluation: input, process, output, mã lỗi, rate limit, quota và giao thức SSE
> của toàn bộ backend API (tiếng Anh).

## Kiến trúc — mỗi file một giai đoạn

| File | Giai đoạn | Trách nhiệm |
|---|---|---|
| `steady_backend.py` | §0–§1 | `SteadyConfig` + `BackendClient`: dev-login/token, folder, JSON, SSE, page-match, quota — **cổng duy nhất** nói chuyện với backend |
| `steady_dataset.py` | §2 | Nạp `dataset/sources/` + `dataset/qa_pairs.csv`, kiểm chứng fail-fast (gold nguyên văn, câu/gold rỗng, giới hạn backend) |
| `steady_flows.py` | §3 | Ingest → chờ index; Search; RAG SSE; PageMatch — mỗi case ghi raw ngay, lỗi từng ca được cô lập |
| `steady_metrics.py` | §4 | Hàm chấm thuần (không I/O): chuẩn hoá, token-F1, trích dẫn, số ngoài ngữ cảnh, aggregate + p50/p95 |
| `run_evaluation.py` | §5 | CLI, điều phối, manifest/raw_results/metrics/report, `--compare`, `--recompute` |
| `tests/` | — | unittest stdlib cho metric, dataset, report, recompute, cô lập lỗi |

Đồ thị phụ thuộc (một chiều, không vòng): `run_evaluation → flows → {backend, dataset → metrics}`.

## Điều kiện chạy

1. Backend đang chạy: `uvicorn` ở `http://localhost:8000` (check: `GET /api/v1/health/live`).
2. Worker đang chạy: `python -m quickassist.worker` (nếu không, note sẽ kẹt `PROCESSING` → case báo `TIMEOUT`).
3. Xác thực: `STEADY_EMAIL` qua **dev-login** (đòi `APP_ENV=dev|test` + `ENABLE_DEV_LOGIN=true`),
   hoặc `STEADY_ACCESS_TOKEN` nếu muốn dùng token có sẵn.
4. Python 3.11+, chỉ cần `httpx` (backend đã dùng). Không cần PostgreSQL client.

> **Dev-login không tạo kho mới cho mỗi lần chạy.** Backend dùng `sub = "dev:<email>"`, nên
> cùng email trả về cùng user. Pipeline mặc định tạo **một thư mục riêng cho mỗi run**
> (`--folder-mode run`), nạp note vào đó và truyền `folder_id` vào search/chat — nhờ vậy note
> của run trước không lẫn vào metric. Dùng `--cleanup-notes` để xoá note + thư mục sau khi chấm.
> Đổi model: sửa `CHAT_MODEL`/`EMBEDDING_MODEL` ở backend (hoặc alias llama-server) → restart →
> chạy lại với `--model-label` khác.

## Contract dataset

```
steady_evaluation/
└── dataset/
    ├── sources/          # *.html (luồng Trafilatura), *.txt (luồng văn bản dán)
    │   ├── tai-che-nhua-pet.html      (file mẫu — thay bằng dữ liệu của bạn)
    │   └── bao-quan-thuc-pham.txt     (file mẫu — thay bằng dữ liệu của bạn)
    └── qa_pairs.csv      # 4 cột bắt buộc + 1 cột tùy chọn
```

`qa_pairs.csv`: `source_file,question,gold_text,answerable[,reference_answer]`

- `source_file` khớp tên file trong `sources/`; `gold_text` là **nguyên văn một đoạn** trong file
  (với HTML: văn bản hiển thị, không chứa thẻ — loader kiểm chứng sau chuẩn hoá bỏ dấu).
- `question` và `gold_text` **không được rỗng**. Dòng lỗi bị loại và ghi vào `issues`; runner
  **dừng** nếu còn bất kỳ issue nào, trừ khi chủ động `--allow-partial`.
- `answerable`: `yes|no`. Câu `no` dùng đo **từ chối đúng** (RAG) và **FPR** (PageMatch); không
  tham gia metric search.
- `reference_answer` (tùy chọn): câu trả lời chuẩn ngắn; khi có, report báo thêm
  `answer_token_f1_reference_avg` bên cạnh F1 với đoạn gold (metric phụ).
- Text tiếng Việt có dấu phẩy → phải bọc trong ngoặc kép (CSV chuẩn, loader dùng `csv` module).
- Giới hạn được kiểm chứng trước khi chạy: question ≤ 500 ký tự, HTML ≤ 2 MB. File dài hơn
  `--split-chars` được **chia thành part ≤ trần backend** (không cắt nội dung; `truncated` chỉ
  còn khi chủ động chạy `--truncate-long` để làm baseline A/B).

## Cách chạy

```bash
cd steady_evaluation
cp .env.example .env        # chỉnh nếu cần (biến OS cùng tên được ưu tiên)

python3 run_evaluation.py --validate                                  # kiểm chứng dataset; exit ≠ 0 nếu lỗi
python3 run_evaluation.py --model-label "bonsai9b+gte-qwen2" --tag m1 # chạy đầy đủ
python3 run_evaluation.py --modules rag --model-label "khac"          # chạy một phần
python3 run_evaluation.py --compare                                   # bảng so sánh (nhóm theo dataset/config)
python3 run_evaluation.py --recompute latest                          # tái tạo metrics từ raw rồi diff
python3 -m unittest discover -s tests -t .                            # test offline
```

Cờ hữu ích:

| Cờ | Ý nghĩa |
|---|---|
| `--folder-mode run|shared` | `run` (mặc định) = thư mục riêng mỗi run; `shared` = dùng Inbox |
| `--fresh-notes` | Idempotency key theo run thay vì theo nội dung |
| `--cleanup-notes` | Xoá note + thư mục của run sau khi chấm |
| `--allow-partial` | Vẫn chạy dù dataset còn dòng bị loại (mặc định fail-fast) |
| `--allow-degraded` | Vẫn chấm dù có note chưa `READY` (mặc định dừng) |
| `--top-k` | Số **tài liệu/note** đầu (sau khi gom theo `document_id`, phẳng nguồn → note) dùng cho Recall/MRR/AnswerHit (mặc định 5) |
| `--max-sources` | `SearchIn.max_sources` (1..20) — số **nguồn/domain** gửi lên `/search` (mặc định 5; env `STEADY_MAX_SOURCES`) |
| `--split-chars` | Ngưỡng chia part cho file dài (≤ `MAX_NOTE_CHARS`, mặc định 20k; env `STEADY_SPLIT_CHARS`) |
| `--truncate-long` | Baseline cũ: cắt file > trần thay vì chia part (dùng cho A/B before/after) |
| `--pagematch-top-k` | Chỉ chấm top-k block PageMatch (mặc định 5) |
| `--evidence-type auto|smoke|quality|failure` | Nhãn loại bằng chứng ghi vào report/manifest |
| `--provider`, `--model`, `--embedding-model`, `--temperature`, `--evaluator` | Metadata tái lập (không tự đọc được từ HTTP health) |
| `--provider-rpm` | Nhịp gọi provider chủ động (RPM) để chống 429 upstream (ví dụ 10; env `STEADY_PROVIDER_RPM`) |
| `--search-rpm`, `--rag-rpm`, `--pagematch-rpm` | Hạn mức RPM chủ động riêng cho Search, RAG, PageMatch |
| `--max-retries-429` | Số lần chờ `Retry-After` cho JSON **và SSE** (mặc định 5) |
| `--pagematch-timeout` | Timeout riêng cho PageMatch (mặc định 90s) |

## Artifact

```
runs/<run_id>/
├── run_manifest.json          # model/provider/embedding, eval_code_sha256, command, dataset, folder…
├── raw_results.jsonl          # từng case (response thô + field dẫn xuất), ghi ngay khi xong
├── metrics.json               # chỉ số tổng hợp + quota before/after + tokens tiêu thụ
├── metrics.recomputed.json    # (khi --recompute) metrics tái tạo từ raw
└── report.md                  # bảng kết quả + banner smoke + mẫu câu trả lời + ranh giới
runs/MODEL_COMPARISON.md       # (khi --compare) bảng so sánh nhóm theo dataset/config
```

Nếu lỗi giữa chừng, `raw_results.jsonl` + `metrics.json` + `report.md` vẫn được giữ lại và
`metrics.json` có `fatal_error` — không còn cảnh chỉ còn mỗi manifest.

## Định nghĩa metric (chi tiết trong `steady_metrics.py`)

| Module | Chất lượng | Hiệu năng | Lưu ý đọc kết quả |
|---|---|---|---|
| Ingest | trạng thái index (READY/FAILED/SKIPPED/TIMEOUT/ERROR) theo **mọi part** của tài liệu, created/reused, `indexed_chars / source_chars`, part lớn nhất, `truncated` | create p50, **chờ index p50/p95** | phản ánh worker thật; replay idempotent có wait ≈ 0; file > `--split-chars` được chia part (Lát 3), READY chỉ khi tất cả part READY |
| Search | Recall@k/MRR/AnswerHit@k trên **tài liệu** (`document_id ?? note`); kèm Recall@k **part chứa gold** và AnswerHit **note** để chẩn đoán | p50/p95 HTTP | API nhóm theo nguồn (`sources[].notes[]`) và trả `document_id` ở cấp nguồn; phẳng theo hạng nguồn rồi note, cắt top-k; AnswerHit tài liệu kiểm tra **toàn bộ part** của tài liệu đã lọt top-k; báo nguồn TB/max/rỗng; sàn ngẫu nhiên = k/số tài liệu |
| RAG | Token-F1 (phụ), F1 reference (nếu có), trích dẫn hợp lệ, không trích dẫn, số ngoài ngữ cảnh, từ chối đúng | first-event p50, total p50/p95, tokens | lỗi AI tách khỏi chất lượng; citation kiểm tra chỉ số + có ít nhất 1 trích dẫn |
| PageMatch | **quality — segments** (không warning): Hit, Exact, Precision@k, Recall@k, F1@k, Span Precision/Coverage/F1; **quality — full-page** báo riêng; **fallback** báo riêng; FPR ca âm; **overall** trên toàn bộ item (`hit_all`, `precision_all`, `coverage_all`, `span_precision_all`, `hit5_page`, `hit5_score`) + nhóm **verified** (`verified_recall`, `verified_precision_macro/micro`, `verified_fpr`) | p50/p95 | top-k mặc định 5 cho metric cũ; `hit_all`/`verified_*` chấm trên mọi item (khớp UI); span precision phạt block quá lớn; coverage = tỷ lệ chuỗi con chung dài nhất của gold trong block |

### Những gì đã sửa so với bản smoke đầu tiên (metrics v4)

- Search: theo contract `POST /search` mới — request gửi `max_sources` thay cho `top_k`,
  response đọc `sources[].notes[]` thay cho `items[]`; top-k là **note** sau khi phẳng
  theo hạng nguồn rồi note. AnswerHit dùng `snippet` trước, không khớp thì fetch toàn văn
  note (cache theo run) để tránh âm tính giả với gold dài.
- Ingest: `POST /notes` trả `201` cả khi idempotent replay (cùng `Idempotency-Key`), nên
  `created` được xác định bằng `created_at` so với thời điểm bắt đầu run (dung sai 5 s).
- Auth: tự `POST /auth/refresh` một lần khi gặp `401 TOKEN_EXPIRED` (cả JSON lẫn SSE).
- `numbers_of`: bỏ citation `[n]`, chuẩn hoá `1,5 → 1.5`, `1.000 → 1000`, `âm 18 → -18`,
  bỏ chữ số trong mã như `CO2`; không cộng gold vào tập số hợp lệ; kiểm tra trên **toàn văn note
  nguồn** (fetch qua API) thay vì snippet 240 ký tự.
- `citation_valid_rate`: mẫu số là **mọi câu answerable hoàn thành**; câu không trích dẫn = 0;
  báo thêm `citation_presence_rate` / `no_citation_rate`.
- `_pct`: nearest-rank đúng `ceil(n·q)` (trước đây lệch một bậc).
- `token_f1`: đa tập (`Counter`) thay vì giao tập; chỉ là metric phụ.
- RAG: lỗi AI không còn bị tính là "trả lời bừa"; báo `error_rate`, `no_source_rate`, `no_context_rate`.
- PageMatch: tách **quality/fallback** và **segments/full-page**, giới hạn top-k,
  Precision/Recall/F1@k, Span Precision/Coverage/F1, Full-page F1 — không còn thưởng precision 1.0
  cho "trả cả trang".
- v4 — PageMatch: thêm nhóm **overall** chấm trên **toàn bộ item trả về** (khớp UI hiển thị
  mọi item): `hit_all`, `hit5_page` (5 item đầu theo thứ tự trang — metric cũ),
  `hit5_score` (top-5 theo score), `precision_all`, `coverage_all`, `span_precision_all`;
  thêm nhóm **verified** (`verified_recall`, `verified_precision_macro/micro`, `verified_fpr`)
  vì UI auto-select item `verified=true`. Khóa cũ giữ nguyên nghĩa top-k.
- Dataset: fail-fast, reject câu/gold rỗng, `--validate` exit ≠ 0, ghi included/excluded.
- Corpus: thư mục riêng mỗi run + `folder_id` cho notes/search/chat; đếm corpus đúng thư mục.
- Độ bền: bắt lỗi từng case, ghi JSONL ngay, retry 429 cho cả SSE, timeout riêng PageMatch,
  gate note `READY`, artifact một phần khi fatal.
- Tái lập: `eval_code_sha256`, `metrics_version`, `command`, `--recompute` diff với `metrics.json`.

### Lát 3 — tài liệu dài nhiều part (harness)

- Bỏ truncation mặc định: file > `--split-chars` được chia theo đoạn → câu → từ (target 90% trần)
  và gửi **một** `POST /notes` với `parts` + `document_id`; nội dung nạp đủ (`indexed_chars`).
  `--truncate-long` giữ hành vi cũ để A/B với baseline.
- qid → **document + part chứa gold**: harness map `source_file` → tài liệu đã nạp, tìm part chứa
  gold nguyên văn, báo `gold_part_index`, `gold_spans_parts`, `gold_part_missing`.
- Recall@k/MRR tính trên **tài liệu**; AnswerHit tài liệu kiểm tra mọi part (kể cả part ngoài top-k
  note); vẫn báo Recall part + AnswerHit note để chẩn đoán ranh giới chia.
- Ingest báo `documents/parts/parts_ready/indexed_chars/max_part_chars`; một part FAILED → cả
  tài liệu không READY (gate trước khi chấm search/RAG).
- Tương thích raw cũ: thiếu `document_id`/`answer_hit_document` thì suy từ `ranked_note_ids`/`items`
  và `answer_hit`, nên `--recompute` run cũ vẫn ra số cũ.

## Ranh giới đã biết (trung thực về phạm vi)

- "Số ngoài ngữ cảnh" vẫn là **proxy chuỗi** trên toàn văn note nguồn; không phải kiểm chứng
  ngữ nghĩa. Nếu không fetch được note, fallback về snippet và điều này được phản ánh ở
  `context_chars_avg`/`context_note_count`.
- Phát hiện từ chối dựa trên marker ở câu đầu (gồm dạng gián tiếp "không đề cập…") — có thể bỏ
  lỡ cách diễn đạt khác. Tín hiệu cấu trúc `n_sources = 0` được báo riêng.
- Trích dẫn chỉ kiểm tra **chỉ số `[n]` nằm trong số nguồn** và có ít nhất một trích dẫn; chưa
  kiểm chứng nguồn có thực sự hỗ trợ ý (cần rubric người hoặc entailment).
- PageMatch Span Coverage là tỷ lệ chuỗi con chung dài nhất, không phải offset ký tự tuyệt đối;
  Full-page F1 so token với văn bản nguồn do tool trích, không phải ground-truth của backend.
- Dataset hiện tại 11 nguồn/47 cặp (36 answerable) → `random_floor ≈ 5/11 = 0.45` khi
  `--top-k 5`, vẫn chưa đủ để kết luận search tốt/xấu. Cần thêm note/chunk và câu nhiễu
  (hoặc tăng corpus) để metric retrieval có ý nghĩa; luôn đọc kèm `random_floor`.
- Chưa có module Tóm tắt, reliability/fault-injection, cache, prompt injection, ablation
  full-text/vector/hybrid, nhãn 2 người — nằm ngoài phạm vi phiên này.
- Độ trễ là end-to-end HTTP, gồm provider; chưa tách thời gian DB thuần.