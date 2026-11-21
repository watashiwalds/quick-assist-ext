# Báo cáo đánh giá steady — 20261119_173634_531332_smoke-lat3_mini2
*Model: `smoke-lat3` · backend `http://localhost:8000/api/v1` · dataset `e342658c42ad9b4c` · git `4ccd0513b` · eval-code `e6fa1c826` · 2026-11-19T17:36:34.531550+00:00*

> **Loại bằng chứng: `smoke`** · metrics v3 · module: `search, rag`

> ⚠ **KHÔNG dùng các số dưới đây để kết luận chất lượng.** Dataset hiện tại chỉ kiểm chứng pipeline chạy được (smoke). Cần dataset đúng kích thước + nhãn chuẩn và `--evidence-type quality` trước khi báo cáo chất lượng.

## 1. Dataset

- source_files: 2
- html_files: 0
- text_files: 2
- qa_pairs: 3
- answerable: 2
- unanswerable: 1
- reference_answers: 0
- excluded_rows: 0
- plain_chars_min: 54
- plain_chars_median: 2933
- plain_chars_max: 5812
- files_over_chunk_size: 1
- included_pairs: 3 · excluded_rows: 0

## 2. Ingest (nạp ghi chú + chờ index)
- 2 file, trạng thái: {'READY': 2} · READY 1.0 · tạo mới 2 / replay 0
- tài liệu dài: **2 file → 8 part** · part READY 8/8 (1.0) · file đủ part READY 2/2
- ký tự đã index: **5,860 / 5,860** (1.0) · part lớn nhất 865 ký tự · file bị cắt: 0
- create p50 = **25.14 ms** · chờ index p50 = **1009.97 ms** · p95 = **2014.31 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0.0 | 1.0 | 0.0 | 1.0 | 1.0 | 1.5 | 2 | 7.5 | 0.0 | 133.93 | 150.02 | 1.0 |

- corpus: 8 note / 2 tài liệu · `max_sources` đúng (ca chạm trần: 0.0) · gold vắt qua ranh giới part: 0

> ⚠ `random_floor = 1.0` (top_k ≥ số tài liệu trong corpus): Recall@k bị chặn trần, không phản ánh chất lượng xếp hạng.

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 0.4658 | — | 1.0 | 0.0 | 0.0 | 1038.0 | 1486.93 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 2409.5 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 1.0 | 0.0 | 1.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Con số cần tìm là gì?
- **Đáp:** Con số cần tìm là 2468.

*   [1]
- **Gold:** Con số cần tìm là 2468 nằm ở phần cuối tài liệu.
- **Nguồn:** 3 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Giá bao nhiêu?
- **Đáp:** Mình không tìm thấy ghi chú nào liên quan tới câu hỏi này, nên không trả lời để tránh bịa thông tin. Hãy thử diễn đạt khác, bỏ lọc thư mục, hoặc lưu thêm ghi chú về chủ đề này.
- **Gold:** Tài liệu không đề cập.
- **Nguồn:** 0 · lỗi: —

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 3 · raw_schema_version: 3
- eval_code_sha256: `e6fa1c8266b28c30861f23ea4e21a63a7b7fd5d41ca19a6f1f79410ada0e2e2f`
- command: `run_evaluation.py --base-url http://localhost:8000/api/v1 --dataset-dir /tmp/lat3-mini --modules search,rag --split-chars 1000 --top-k 5 --max-sources 5 --model-label smoke-lat3 --evidence-type smoke --tag mini2 --cleanup-notes`
- dataset_version: `e342658c42ad9b4c` · fingerprint: `e342658c42ad9b4c`
- provider/model/embedding: `` / `` / ``
- folder_id: `8fc403c8-af08-4eee-a524-bc929343d896` · folder_mode: `run`
