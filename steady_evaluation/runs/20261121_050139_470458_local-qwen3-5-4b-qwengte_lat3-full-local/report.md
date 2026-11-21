# Báo cáo đánh giá steady — 20261121_050139_470458_local-qwen3-5-4b-qwengte_lat3-full-local
*Model: `local-qwen3.5_4b-qwengte` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `46f543515` · eval-code `6808d78d4` · 2026-11-21T05:01:39.470700+00:00*

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
- create p50 = **27.15 ms** · chờ index p50 = **3019.69 ms** · p95 = **53363.06 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.7105 | 0.7105 | 0.6798 | 0.7105 | 0.7105 | 3.68 | 5 | 4.08 | 0.0 | 204.58 | 276.86 | 0.4545 |

- corpus: 25 note / 11 tài liệu · `max_sources` đúng (ca chạm trần: 0.3947) · gold vắt qua ranh giới part: 0

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 0.1493 | — | 0.7895 | 0.2105 | 0.0526 | 1434.1 | 4341.97 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 25098.9 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 0.8182 | 0.1818 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.1818
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 29 | 0.5862 | 0.5862 | 0.2598 | 0.5862 | 0.3322 | 0.1592 | 0.6255 | 0.1892 | 8 | 0.5 | 10456.12 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | — | — | 0 | — | 5414.84 |

- verify_unavailable_rate: 0.0408 · full_page_mode_rate: 0.2449 · truncated_rate: 0.2245 · lỗi: 0

**Chất lượng — full-page** (tách khỏi segments; một block cả trang không được tính như đoạn chính xác):
| Dương tính | Hit | Span Coverage | Full-page F1 | Âm tính | FPR |
|---:|---:|---:|---:|---:|---:|
| 8 | 0.5 | 0.6398 | 0.7642 | 2 | 1.0 |

**Toàn bộ item trả về** (mọi ca, không cắt top-k — đúng như UI hiển thị):
| Dương tính | Gold trong bất kỳ item (`hit_all`) | `hit5_page` (metric cũ) | `hit5_score` | Precision all | Coverage all | Span Precision all |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.6842 (26/38) | 0.5789 (22/38) | 0.6316 (24/38) | 0.2217 | 0.7252 | 0.1332 |

**Nhóm `verified=true`** (các đoạn UI auto-select):
| Dương tính | `verified_recall` | Verified precision (macro) | Verified precision (micro) | Âm tính | FPR bất kỳ item | `verified_fpr` |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.6579 (25/38) | 0.2445 | 0.1376 | 11 | 0.6364 (7/11) | 0.5455 (6/11) |

> `hit5_page` = 5 item đầu **theo thứ tự trang** (metric cũ, không phải top-5 theo score). `hit5_score` = 5 item tốt nhất theo `score`. `hit_all`/`verified_*` chấm trên **mọi item trả về**, gồm cả ca full-page và fallback.

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Dựa trên các ghi chú đã lưu, dưới đây là thông tin về vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình:

*   Trước khi dính bê bối ngoại tình với người bị nghi là gián điệp, Jensen Huang giữ vị trí là **CEO** (Tổng giám đốc) của Nvidia.
*   Lúc đó, Nvidia là một trong những **doanh nghiệp có giá trị nhất thế giới**, với vốn hóa đạt đỉnh cao lên đến **5.700 tỷ USD** [1].
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 5 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** Ghi chú của bạn chưa có thông tin về diễn biến tâm lý của Jensen Huang sau khi bê bối ngoại tình bị phanh phui. Các đoạn ghi chú hiện có chỉ đề cập đến các phản ứng chính trị từ phía Tổng thống Trump và các chính trị gia cứng rắn với Trung Quốc, cũng như các cáo buộc về việc Nvidia xem nhẹ tình trạng buôn lậu chip và phóng đại năng lực chip của đối thủ.
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
- eval_code_sha256: `6808d78d446fb98372b42529fa0a82d139955a144531da27af7d61fdbfa71b3b`
- command: `run_evaluation.py --model-label local-qwen3.5_4b-qwengte --provider openai --model chat --embedding-model gte-Qwen2-1.5B-instruct-Q4_K_M --tag lat3-full-local --fresh-notes --cleanup-notes`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `openai` / `chat` / `gte-Qwen2-1.5B-instruct-Q4_K_M`
- folder_id: `a11bf531-db1d-4326-b9be-c74e26620ae9` · folder_mode: `run`
