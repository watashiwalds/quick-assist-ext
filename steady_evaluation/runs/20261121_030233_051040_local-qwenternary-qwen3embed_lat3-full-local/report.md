# Báo cáo đánh giá steady — 20261121_030233_051040_local-qwenternary-qwen3embed_lat3-full-local
*Model: `local-qwenternary-qwen3embed` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `6d09ed9c3` · eval-code `824b467cf` · 2026-11-21T03:02:33.061756+00:00*

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
- create p50 = **26.98 ms** · chờ index p50 = **3018.77 ms** · p95 = **40279.39 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.9737 | 0.8947 | 0.9342 | 0.9737 | 0.8947 | 1.53 | 3 | 2.34 | 0.0263 | 110.07 | 152.62 | 0.4545 |

- corpus: 25 note / 11 tài liệu · `max_sources` đúng (ca chạm trần: 0.0) · gold vắt qua ranh giới part: 0

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.177 | — | 0.8421 | 0.1579 | 0.0263 | 1121.7 | 2645.19 |

- Không có nguồn: 0.0263 · không ngữ cảnh: 0.0263 · ngữ cảnh TB: 25257.4 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 0.8182 | 0.1818 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 28 | 0.5714 | 0.5714 | 0.1696 | 0.5714 | 0.2488 | 0.1429 | 0.6304 | 0.1799 | 8 | 0.5 | 10528.95 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 1.0 | 0.375 | 1.0 | 2 | 0.5 | 7393.64 |

- verify_unavailable_rate: 0.102 · full_page_mode_rate: 0.1837 · truncated_rate: 0.2245 · lỗi: 0

**Chất lượng — full-page** (tách khỏi segments; một block cả trang không được tính như đoạn chính xác):
| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 7 | 0.4286 | 0.5959 | 0.6362 | 1 | 1.0 |

**Toàn bộ item trả về** (mọi ca, không cắt top-k — đúng như UI hiển thị):
| Dương tính | Gold trong bất kỳ item (`hit_all`) | `hit5_page` (metric cũ) | `hit5_score` | Precision all | Coverage all | Span Precision all |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.7632 (29/38) | 0.5789 (22/38) | 0.6316 (24/38) | 0.1626 | 0.7964 | 0.1205 |

**Nhóm `verified=true`** (các đoạn UI auto-select):
| Dương tính | `verified_recall` | Verified precision (macro) | Verified precision (micro) | Âm tính | FPR bất kỳ item | `verified_fpr` |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.6842 (26/38) | 0.1555 | 0.1015 | 11 | 0.5455 (6/11) | 0.4545 (5/11) |

> `hit5_page` = 5 item đầu **theo thứ tự trang** (metric cũ, không phải top-5 theo score). `hit5_score` = 5 item tốt nhất theo `score`. `hit_all`/`verified_*` chấm trên **mọi item trả về**, gồm cả ca full-page và fallback.

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Dựa trên thông tin trong ghi chú, trước khi dính bê bối ngoại tình, vai trò của Jensen Huang là **CEO (CỔ TỪ GIÁM ĐOẠI) của Nvidia**.

*   Ông giữ vị trí này và Nvidia là một trong những doanh nghiệp có giá trị nhất thế giới với vốn hóa lên đến 5.700 tỷ USD [1].
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 1 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** Ghi chú của bạn chưa có thông tin về diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui. Các nguồn hiện tại chỉ đề cập đến vai trò chính trị, quan hệ với giới hoạch định chính sách và sự thân thiết giữa ông Huang và Tổng thống Trump, không thể suy đoán tâm lý liên quan đến sự kiện ngoại tình.
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
- eval_code_sha256: `824b467cfefb0aad04036665542cdc1f3d5af9b1607fbed03d4713a2b6417688`
- command: `run_evaluation.py --model-label local-qwenternary-qwen3embed --provider openai --model chat --embedding-model Qwen3-Embedding-0.6B-Q8_0 --tag lat3-full-local --fresh-notes --cleanup-notes`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `openai` / `chat` / `Qwen3-Embedding-0.6B-Q8_0`
- folder_id: `d832b2da-bd92-4a12-976d-fe1fb73d5de6` · folder_mode: `run`
