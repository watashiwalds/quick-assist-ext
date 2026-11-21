# Báo cáo đánh giá steady — 20261121_023251_415228_local-qwenternary-qwenqte_lat3-full-local
*Model: `local-qwenternary-qwenqte` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `6d09ed9c3` · eval-code `824b467cf` · 2026-11-21T02:32:51.415514+00:00*

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
- create p50 = **25.83 ms** · chờ index p50 = **3019.71 ms** · p95 = **53366.17 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.7105 | 0.7105 | 0.6798 | 0.7105 | 0.7105 | 3.68 | 5 | 4.08 | 0.0 | 194.43 | 268.96 | 0.4545 |

- corpus: 25 note / 11 tài liệu · `max_sources` đúng (ca chạm trần: 0.3947) · gold vắt qua ranh giới part: 0

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.1629 | — | 0.7368 | 0.2632 | 0.0 | 1399.7 | 3332.26 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 25098.9 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 0.8182 | 0.1818 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 19 | 0.7895 | 0.7895 | 0.2754 | 0.7895 | 0.3737 | 0.1609 | 0.7952 | 0.2295 | 6 | 0.5 | 10781.11 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | — | — | 0 | — | 8466.08 |

- verify_unavailable_rate: 0.0408 · full_page_mode_rate: 0.4898 · truncated_rate: 0.2245 · lỗi: 0

**Chất lượng — full-page** (tách khỏi segments; một block cả trang không được tính như đoạn chính xác):
| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 18 | 0.5 | 0.588 | 0.7642 | 4 | 1.0 |

**Toàn bộ item trả về** (mọi ca, không cắt top-k — đúng như UI hiển thị):
| Dương tính | Gold trong bất kỳ item (`hit_all`) | `hit5_page` (metric cũ) | `hit5_score` | Precision all | Coverage all | Span Precision all |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.7895 (30/38) | 0.6579 (25/38) | 0.6316 (24/38) | 0.171 | 0.826 | 0.1038 |

**Nhóm `verified=true`** (các đoạn UI auto-select):
| Dương tính | `verified_recall` | Verified precision (macro) | Verified precision (micro) | Âm tính | FPR bất kỳ item | `verified_fpr` |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.7632 (29/38) | 0.1882 | 0.1068 | 11 | 0.7273 (8/11) | 0.6364 (7/11) |

> `hit5_page` = 5 item đầu **theo thứ tự trang** (metric cũ, không phải top-5 theo score). `hit5_score` = 5 item tốt nhất theo `score`. `hit_all`/`verified_*` chấm trên **mọi item trả về**, gồm cả ca full-page và fallback.

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Dựa trên thông tin có sẵn, tôi chỉ tìm thấy được một mục liên quan đến sự kiện "bê bối ngoại tình" của Jensen Huang, nhưng ghi chú này chỉ nêu bật tác động của việc ông rời khỏi vị trí CEO mà chưa cung cấp chi tiết về vai trò cụ thể trước sự kiện đó.

Dưới đây là thông tin có trong dữ liệu:
*   Trước khi bị dính bê bối ngoại tình, Nvidia là một trong những doanh nghiệp có giá trị nhất thế giới với vốn hóa lên đến 5.700 tỷ USD [1].
*   Việc Jensen Huang không còn là CEO đặt dấu hỏi cho tương lai của Nvidia và ảnh hưởng của hãng với Washington cùng chính sách AI của Mỹ [1].

Ghi chú của bạn chưa
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 5 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** Ghi chú của bạn chưa có thông tin về diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui. Các đoạn ghi chú hiện có tập trung vào các chủ đề khác: quyền lực công nghệ và chính trị sau vụ việc [1], vụ án lừa đảo ở Việt Nam [2], thông tin về Lionel Messi [3], và sự cố hệ thống kỹ thuật tại Mỹ [4].
- **Gold:** Không có thông tin.
- **Nguồn:** 4 · lỗi: —

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 4 · raw_schema_version: 3
- eval_code_sha256: `824b467cfefb0aad04036665542cdc1f3d5af9b1607fbed03d4713a2b6417688`
- command: `run_evaluation.py --model-label local-qwenternary-qwenqte --provider openai --model chat --embedding-model gte-Qwen2-1.5B-instruct --tag lat3-full-local --fresh-notes --cleanup-notes`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `openai` / `chat` / `gte-Qwen2-1.5B-instruct`
- folder_id: `dde18d92-96f2-47af-b38f-831770f04d1c` · folder_mode: `run`
