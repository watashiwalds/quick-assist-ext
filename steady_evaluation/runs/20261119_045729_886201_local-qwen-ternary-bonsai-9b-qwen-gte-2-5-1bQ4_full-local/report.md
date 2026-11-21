# Báo cáo đánh giá steady — 20261119_045729_886201_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_full-local
*Model: `local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `b656d2388` · eval-code `59ae54a50` · 2026-11-19T04:57:29.886527+00:00*

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
- 11 file, trạng thái: {'READY': 11} · READY 1.0 · tạo mới 11 / replay 0
- create p50 = **22.38 ms** · chờ index p50 = **3015.5 ms** · p95 = **7037.05 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR/AnswerHit tính trên 5 **note** đầu sau khi phẳng nguồn → note.

| Queries | Hoàn thành | Lỗi | Recall@5 | MRR | AnswerHit | Nguồn TB | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.7105 | 0.6798 | 0.6842 | 1.0 | 4.37 | 0.0 | 187.38 | 285.46 | 0.4545 |

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.1707 | — | 0.5263 | 0.4737 | 0.0 | 1035.2 | 2902.88 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 17355.8 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 1.0 | 0.0 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.8235 | 0.8235 | 0.2314 | 0.8235 | 0.3392 | 0.1231 | 0.8468 | 0.2017 | 6 | 0.6667 | 14917.84 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | — | — | 0 | — | 16390.13 |

- verify_unavailable_rate: 0.0408 · full_page_mode_rate: 0.5306 · truncated_rate: 0.2245 · lỗi: 0

**Chất lượng — full-page** (tách khỏi segments; một block cả trang không được tính như đoạn chính xác):
| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 20 | 0.5 | 0.5722 | 0.8156 | 4 | 1.0 |

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Dựa trên các ghi chú cung cấp:

*   Trước khi liên quan đến bê bối ngoại tình với người nghi ngờ là gián điệp, Nvidia là một trong những doanh nghiệp có giá trị nhất thế giới, với mức vốn hóa đạt đỉnh cao lên tới 5.700 tỷ USD [1].
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 3 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** Ghi chú của bạn chưa có thông tin về diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui.
- **Gold:** Không có thông tin.
- **Nguồn:** 3 · lỗi: —

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 3 · raw_schema_version: 3
- eval_code_sha256: `59ae54a5085c6e098b9b96370d157b73924ee321b27f1fec92a38b8913b2627e`
- command: `run_evaluation.py --model-label local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4 --provider openai --model chat --embedding-model embed --tag full-local --fresh-notes --cleanup-notes`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `openai` / `chat` / `embed`
- folder_id: `06373908-ed0e-4aa7-ae63-6bae7d4d5d09` · folder_mode: `run`
