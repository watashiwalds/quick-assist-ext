# Báo cáo đánh giá steady — 20261119_173736_232665_local-qwen-ternary-bonsai-9b-qwen-gte-2-5-1bQ4_lat3-full-local
*Model: `local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `4ccd0513b` · eval-code `0f8e5e7e9` · 2026-11-19T17:37:36.232904+00:00*

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
- tài liệu dài: **11 file → 25 part** · part READY 25/25 (1.0) · file đủ part READY 11/11
- ký tự đã index: **316,032 / 316,032** (1.0) · part lớn nhất 17,995 ký tự · file bị cắt: 0
- create p50 = **26.26 ms** · chờ index p50 = **3020.86 ms** · p95 = **52350.77 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.7105 | 0.7105 | 0.6798 | 0.7105 | 0.7105 | 3.68 | 5 | 4.08 | 0.0 | 193.6 | 273.88 | 0.4545 |

- corpus: 25 note / 11 tài liệu · `max_sources` đúng (ca chạm trần: 0.3947) · gold vắt qua ranh giới part: 0

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.1694 | — | 0.5526 | 0.4474 | 0.0263 | 1393.6 | 3782.71 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 25098.9 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 0.9091 | 0.0909 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 0.6 | 0.6 | 0.1889 | 0.6 | 0.2644 | 0.1215 | 0.6416 | 0.1914 | 6 | 0.3333 | 13634.88 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 0.5 | 0.125 | 0.5 | 0 | — | 16438.08 |

- verify_unavailable_rate: 0.0612 · full_page_mode_rate: 0.3878 · truncated_rate: 0.0816 · lỗi: 7

**Chất lượng — full-page** (tách khỏi segments; một block cả trang không được tính như đoạn chính xác):
| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 14 | 0.5 | 0.566 | 0.8589 | 4 | 1.0 |

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Dựa trên các ghi chú cung cấp, không có thông tin cụ thể nào về vai trò của Jensen Huang trước bê bối ngoại tình, ngoại trừ thông tin cơ bản về chức danh và ảnh hưởng của việc ông nghỉ việc.

*   Trước khi dính bê bối, Jensen Huang giữ chức vụ **CEO** của Nvidia. Việc ông không còn tại vị đã làm thay đổi ảnh hưởng của hãng đối với Washington và chính sách AI của Mỹ.
*   Nvidia dưới thời ông là một trong những doanh nghiệp giá trị nhất thế giới, với vốn hóa đỉnh cao lên đến **5.700 tỷ USD**.

Ghi chú của bạn chưa có thông tin về các chi tiết cụ thể về vai trò chi tiết hay các hoạt động trước bê
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 5 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** Ghi chú của bạn chưa có thông tin về diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui. Các đoạn ghi chú chỉ đề cập đến các thông tin về chính sách kinh doanh, hợp đồng thương mại hay các sự kiện pháp lý khác, nhưng không có nội dung liên quan đến sự việc ngoại tình hay tâm lý của ông.
- **Gold:** Không có thông tin.
- **Nguồn:** 4 · lỗi: —

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 3 · raw_schema_version: 3
- eval_code_sha256: `0f8e5e7e93c130cb8bf9a329209b4ef39e6a5abaa98fa28a940d1888f54d45cb`
- command: `run_evaluation.py --model-label local-qwen_ternary_bonsai_9b-qwen_gte_2.5_1bQ4 --provider openai --model chat --embedding-model embed --tag lat3-full-local --fresh-notes --cleanup-notes`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `openai` / `chat` / `embed`
- folder_id: `ea00a0a5-4962-4ffd-ab42-5ba432f5fa18` · folder_mode: `run`
