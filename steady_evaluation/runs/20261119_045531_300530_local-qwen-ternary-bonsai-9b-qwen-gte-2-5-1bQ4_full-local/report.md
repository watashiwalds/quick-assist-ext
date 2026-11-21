# Báo cáo đánh giá steady — 20261119_045531_300530_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local
*Model: `local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `b656d2388` · eval-code `980a27b6f` · 2026-11-19T04:55:31.311159+00:00*

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
- 11 file, trạng thái: {'ERROR': 11} · READY 0.0 · tạo mới 0 / replay 0
- create p50 = **0.0 ms** · chờ index p50 = **0.0 ms** · p95 = **0.0 ms**

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
- eval_code_sha256: `980a27b6fd3c0a09ee2d9349191c5038fb3e2423e634460ded8c36149c815eb5`
- command: `run_evaluation.py --model-label local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4 --provider openai --model chat --embedding-model embed --tag full-local --fresh-notes --cleanup-notes`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `openai` / `chat` / `embed`
- folder_id: `25ac23f7-a06e-4ebf-9cb7-b17f30bc82cc` · folder_mode: `run`

## 9. Lỗi fatal
`RuntimeError: 11 file chưa READY: ['Attention Is All You Need.txt', 'Evaluating Quantized Large Language.txt', 'Hà Nội sắp mở bán nhà xã hội gần 30 triệu một m2 ở Đông Anh - Báo VnExpress.html', 'LORA LOW-RANK ADAPTATION.txt', 'Messi rạn nứt với Liên đoàn Bóng đá Argentina - Báo VnExpress Thể thao.html', "Mạng liên lạc tuyệt mật của Cơ quan An ninh Quốc gia Mỹ 'gặp sự cố' - Báo VnExpress.html", 'Mỹ tấn công đảo chiến lược của Iran ở Hormuz - Báo VnExpress.html', 'Quyền lực Nvidia ra sao khi không còn Jensen Huang_ - Báo VnExpress Kinh doanh.html', 'Tấm chắn Mặt Trời có thể cứu Trái Đất khỏi nóng lên_ - Báo VnExpress.html', 'Vận tải cơ chở 17 người bốc cháy, rơi ở Nga - Báo VnExpress.html', 'Ông Lê Thanh Thản ra tòa trong vụ lừa 519 người mua chung cư xây trái phép - Báo VnExpress.html']. Kiểm tra worker rồi chạy lại (hoặc --allow-degraded để chấp nhận metric bị suy giảm).`
