# Báo cáo đánh giá steady — 20261121_024854_536342_gemma-4-31b-it-gemini-emb_eval-gemini-retry-01
*Model: `gemma-4-31b-it+gemini-emb` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `6d09ed9c3` · eval-code `138d97ccf` · 2026-11-21T02:48:54.537546+00:00*

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
- create p50 = **61.25 ms** · chờ index p50 = **2024.2 ms** · p95 = **180878.87 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 1.0 | 1.0 | 0.9868 | 1.0 | 1.0 | 4.03 | 5 | 6.45 | 0.0 | 595.79 | 833.44 | 0.4545 |

- corpus: 25 note / 11 tài liệu · `max_sources` đúng (ca chạm trần: 0.6053) · gold vắt qua ranh giới part: 0

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 15 | 23 | 0.2251 | — | 0.8 | 0.2 | 0.2 | 1888.4 | 21526.85 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 47134.8 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 4 | 7 | 0.75 | 0.25 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | — | — | — | — | — | — | — | 0 | — | 0.0 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | — | — | 0 | — | 22103.7 |

- verify_unavailable_rate: 0.2653 · full_page_mode_rate: 0.2653 · truncated_rate: 0.0 · lỗi: 36

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Trước bê bối ngoại tình, Jensen Huang giữ vai trò CEO của Nvidia [1]. Trong thời gian này, Nvidia là một trong những doanh nghiệp giá trị nhất thế giới, với vốn hóa đạt đỉnh cao lên đến 5.700 tỷ USD [1].
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 3 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** (trống)
- **Gold:** Không có thông tin.
- **Nguồn:** 1 · lỗi: AI_UNAVAILABLE: Dịch vụ AI tạm thời không khả dụng, hãy thử lại sau

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 3 · raw_schema_version: 3
- eval_code_sha256: `138d97ccfbd9512405011b8b3da8eb7857ef44323dc9575b7eeed37ac8318911`
- command: `run_evaluation.py --model-label gemma-4-31b-it+gemini-emb --provider gemini --model gemma-4-31b-it --embedding-model gemini-embedding-001 --provider-rpm 5 --wait-index-timeout 300 --folder-mode run --fresh-notes --tag eval-gemini-retry-01 --evidence-type quality`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `gemini` / `gemma-4-31b-it` / `gemini-embedding-001`
- provider_rpm: `5.0` · search_rpm: `None` · rag_rpm: `None` · pagematch_rpm: `None`
- folder_id: `e90382a5-231e-48c2-a3aa-9659ad54a8f9` · folder_mode: `run`
