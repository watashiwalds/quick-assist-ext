# Báo cáo đánh giá steady — 20261121_024136_851783_gemma-4-31b-it-gemini-emb_eval-gemini-20261121
*Model: `gemma-4-31b-it+gemini-emb` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `6d09ed9c3` · eval-code `138d97ccf` · 2026-11-21T02:41:36.853596+00:00*

> **Loại bằng chứng: `quality`** · metrics v3 · module: `search, rag, pagematch`

## 1. Dataset

- source_files: 11
- html_files: 8
- text_files: 3
- qa_pairs: 49
- answerable: 38
- unanswerable: 11
- reference_answers: 0
- excluded_rows: 0
- plain_chars_min: 2865
- plain_chars_median: 5964
- plain_chars_max: 156885
- files_over_chunk_size: 11
- included_pairs: 49 · excluded_rows: 0

## 2. Ingest (nạp ghi chú + chờ index)
- 11 file, trạng thái: {'READY': 10, 'TIMEOUT': 1} · READY 0.9091 · tạo mới 11 / replay 0
- tài liệu dài: **11 file → 25 part** · part READY 23/25 (0.92) · file đủ part READY 10/11
- ký tự đã index: **280,143 / 316,032** (0.8864) · part lớn nhất 17,995 ký tự · file bị cắt: 0
- create p50 = **63.34 ms** · chờ index p50 = **2024.44 ms** · p95 = **120201.82 ms**

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
- eval_code_sha256: `138d97ccfbd9512405011b8b3da8eb7857ef44323dc9575b7eeed37ac8318911`
- command: `run_evaluation.py --model-label gemma-4-31b-it+gemini-emb --provider gemini --model gemma-4-31b-it --embedding-model gemini-embedding-001 --provider-rpm 5 --folder-mode run --fresh-notes --tag eval-gemini-20261121 --evidence-type quality`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `gemini` / `gemma-4-31b-it` / `gemini-embedding-001`
- provider_rpm: `5.0` · search_rpm: `None` · rag_rpm: `None` · pagematch_rpm: `None`
- folder_id: `c44c6c88-103d-418b-80cb-9c0051ad1570` · folder_mode: `run`

## 9. Lỗi fatal
`RuntimeError: 1 file chưa READY: ['Evaluating Quantized Large Language.txt']. Kiểm tra worker rồi chạy lại (hoặc --allow-degraded để chấp nhận metric bị suy giảm).`
