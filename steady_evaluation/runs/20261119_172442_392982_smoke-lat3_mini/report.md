# Báo cáo đánh giá steady — 20261119_172442_392982_smoke-lat3_mini
*Model: `smoke-lat3` · backend `http://localhost:8000/api/v1` · dataset `e342658c42ad9b4c` · git `4ccd0513b` · eval-code `e6fa1c826` · 2026-11-19T17:24:42.393219+00:00*

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
- 2 file, trạng thái: {'TIMEOUT': 2} · READY 0.0 · tạo mới 2 / replay 0
- tài liệu dài: **2 file → 8 part** · part READY 0/8 (0.0) · file đủ part READY 0/2
- ký tự đã index: **0 / 5,860** (0.0) · part lớn nhất 865 ký tự · file bị cắt: 0
- create p50 = **29.17 ms** · chờ index p50 = **120707.34 ms** · p95 = **120760.84 ms**

## 6. Mẫu câu trả lời (bằng chứng thô)
(không có mẫu RAG trong run này)

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 3 · raw_schema_version: 3
- eval_code_sha256: `e6fa1c8266b28c30861f23ea4e21a63a7b7fd5d41ca19a6f1f79410ada0e2e2f`
- command: `run_evaluation.py --base-url http://localhost:8000/api/v1 --dataset-dir /tmp/lat3-mini --modules search,rag --split-chars 1000 --top-k 5 --max-sources 5 --model-label smoke-lat3 --evidence-type smoke --tag mini --cleanup-notes`
- dataset_version: `e342658c42ad9b4c` · fingerprint: `e342658c42ad9b4c`
- provider/model/embedding: `` / `` / ``
- folder_id: `498c1d11-182c-4c65-b67c-7fc2be4d3d6a` · folder_mode: `run`

## 9. Lỗi fatal
`RuntimeError: 2 file chưa READY: ['long.txt', 'short.txt']. Kiểm tra worker rồi chạy lại (hoặc --allow-degraded để chấp nhận metric bị suy giảm).`
