# Báo cáo đánh giá steady — 20261121_043458_145357_local-qwen3-5-4b-qwen3embed_lat3-full-local
*Model: `local-qwen3.5_4b-qwen3embed` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `5b751bb1b` · eval-code `6808d78d4` · 2026-11-21T04:34:58.145601+00:00*

> **Loại bằng chứng: `quality`** · metrics v4 · module: `search, rag, pagematch`

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
- create p50 = **25.01 ms** · chờ index p50 = **2014.43 ms** · p95 = **40274.87 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.9737 | 0.8947 | 0.9342 | 0.9737 | 0.8947 | 1.58 | 3 | 2.42 | 0.0263 | 114.95 | 185.14 | 0.4545 |

- corpus: 25 note / 11 tài liệu · `max_sources` đúng (ca chạm trần: 0.0) · gold vắt qua ranh giới part: 0

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.1638 | — | 0.9211 | 0.0789 | 0.0789 | 1209.7 | 4952.55 |

- Không có nguồn: 0.0263 · không ngữ cảnh: 0.0263 · ngữ cảnh TB: 26155.2 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 0.6364 | 0.3636 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 32 | 0.5938 | 0.5938 | 0.2479 | 0.5938 | 0.3167 | 0.1872 | 0.6306 | 0.1852 | 10 | 0.3 | 8300.41 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 0.5 | 0.5 | 0.5442 | 0 | — | 3411.92 |

- verify_unavailable_rate: 0.0408 · full_page_mode_rate: 0.102 · truncated_rate: 0.2245 · lỗi: 0

**Chất lượng — full-page** (tách khỏi segments; một block cả trang không được tính như đoạn chính xác):
| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 4 | 0.5 | 0.7251 | 0.5427 | 1 | 1.0 |

**Toàn bộ item trả về** (mọi ca, không cắt top-k — đúng như UI hiển thị):
| Dương tính | Gold trong bất kỳ item (`hit_all`) | `hit5_page` (metric cũ) | `hit5_score` | Precision all | Coverage all | Span Precision all |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.6579 (25/38) | 0.5789 (22/38) | 0.5789 (22/38) | 0.2445 | 0.6944 | 0.1751 |

**Nhóm `verified=true`** (các đoạn UI auto-select):
| Dương tính | `verified_recall` | Verified precision (macro) | Verified precision (micro) | Âm tính | FPR bất kỳ item | `verified_fpr` |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.6316 (24/38) | 0.2438 | 0.1412 | 11 | 0.3636 (4/11) | 0.3636 (4/11) |

> `hit5_page` = 5 item đầu **theo thứ tự trang** (metric cũ, không phải top-5 theo score). `hit5_score` = 5 item tốt nhất theo `score`. `hit_all`/`verified_*` chấm trên **mọi item trả về**, gồm cả ca full-page và fallback.

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Theo ghi chú, vai trò của Jensen Huang khi chưa dính bê bối ngoại tình là:

*   Ông là người nắm giữ vị trí **CEO** của Nvidia [1].
*   Tại thời điểm đó, ông đã giúp định hình ảnh hưởng của công ty đối với Washington và các chính sách AI của Mỹ, đồng thời giữ cho Nvidia là một trong những doanh nghiệp có vốn hóa lớn nhất thế giới (đỉnh cao lên đến 5.700 tỷ USD) [1].

*Lưu ý: Ghi chú chỉ đề cập đến thời điểm "trước khi dính bê bối", không nêu chi tiết về các hoạt động quản lý cụ thể trong giai đoạn đó.*
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 1 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** Theo các ghi chú đã lưu, nội dung mô tả diễn biến tâm lý và hành động của Jensen Huang sau khi bê bối ngoại tình bị phanh phui **chưa có thông tin**.

Ghi chú của bạn chưa có thông tin về **diễn biến tâm lý của Jensen Huang** sau sự việc. Nội dung hiện có (Nguồn [1]) chỉ tập trung vào các hoạt động chính trị của ông, việc quyên góp tiền cho Tổng thống Trump, và quan hệ thân thiết với ông tại Mar-a-Lago.
- **Gold:** Không có thông tin.
- **Nguồn:** 2 · lỗi: —

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 4 · raw_schema_version: 3
- eval_code_sha256: `6808d78d446fb98372b42529fa0a82d139955a144531da27af7d61fdbfa71b3b`
- command: `run_evaluation.py --model-label local-qwen3.5_4b-qwen3embed --provider openai --model chat --embedding-model Qwen3-Embedding-0.6B-Q8_0 --tag lat3-full-local --fresh-notes --cleanup-notes`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `openai` / `chat` / `Qwen3-Embedding-0.6B-Q8_0`
- folder_id: `53429f93-6d10-46db-a7de-728d3217e3c8` · folder_mode: `run`
