# Báo cáo đánh giá steady — 20261119_042408_020707_smoke-api-check_api-check
*Model: `smoke-api-check` · backend `http://localhost:8000/api/v1` · dataset `4e6fa6ea3cfebd2c` · git `c091f69f3` · eval-code `945ddf823` · 2026-11-19T04:24:08.020923+00:00*

> **Loại bằng chứng: `smoke`** · metrics v3 · module: `search, rag, pagematch`

> ⚠ **KHÔNG dùng các số dưới đây để kết luận chất lượng.** Dataset hiện tại chỉ kiểm chứng pipeline chạy được (smoke). Cần dataset đúng kích thước + nhãn chuẩn và `--evidence-type quality` trước khi báo cáo chất lượng.

## 1. Dataset

- source_files: 1
- html_files: 1
- text_files: 0
- qa_pairs: 3
- answerable: 1
- unanswerable: 2
- reference_answers: 0
- excluded_rows: 0
- plain_chars_min: 3433
- plain_chars_median: 3433
- plain_chars_max: 3433
- files_over_chunk_size: 1
- included_pairs: 3 · excluded_rows: 0

## 2. Ingest (nạp ghi chú + chờ index)
- 1 file, trạng thái: {'READY': 1} · READY 1.0 · tạo mới 1 / replay 0
- create p50 = **60.68 ms** · chờ index p50 = **3015.96 ms** · p95 = **3015.96 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR/AnswerHit tính trên 5 **note** đầu sau khi phẳng nguồn → note.

| Queries | Hoàn thành | Lỗi | Recall@5 | MRR | AnswerHit | Nguồn TB | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 273.93 | 273.93 | 1.0 |

> ⚠ `random_floor = 1.0` (top_k ≥ số note trong corpus): Recall@k bị chặn trần, không phản ánh chất lượng xếp hạng.

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 0.4918 | — | 1.0 | 0.0 | 0.0 | 681.0 | 2270.04 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 3492.0 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 0 | 1.0 | 0.0 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.0 | 1.0 | 0.2 | 1.0 | 0.3333 | 0.2417 | 1.0 | 0.3893 | 2 | 1.0 | 12248.45 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | — | — | 0 | — | 0.0 |

- verify_unavailable_rate: 0.0 · full_page_mode_rate: 0.0 · truncated_rate: 0.0 · lỗi: 0

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-002 (answerable=True)
- **Hỏi:** Mục tiêu tấn công của Mỹ trong động thái gần đây tại Iran?
- **Đáp:** Dựa trên thông tin bạn cung cấp, mục tiêu tấn công của Mỹ tại Iran gần đây bao gồm:

*   Tấn công trận địa tên lửa của Vệ binh Cách mạng Hồi giáo Iran (IRGC) trên đảo Qeshm, Hormuz để trả đáp cho hành động gây hấn của Tehran nhắm vào quân nhân và tài sản của Washington [1].
*   Sử dụng vũ khí chính xác để đánh bật các mục tiêu cụ thể trên đảo chiến lược này [1].
- **Gold:** Một quan chức Mỹ giấu tên ngày 17/11 cho biết các tiêm kích nước này đã "sử dụng vũ khí chính xác để tấn công một trận địa phóng tên lửa của Vệ binh Cách mạng Hồi giáo Iran (IRGC) trên đảo Qeshm".
- **Nguồn:** 1 · lỗi: —

### QA-001 (answerable=False)
- **Hỏi:** Vì sao Mỹ tấn công Iraq?
- **Đáp:** Ghi chú của bạn chưa có thông tin về lý do chiến lược cụ thể cho việc Mỹ tấn công Iraq trong câu hỏi này. Nội dung <sources> chỉ ghi lại chi tiết về việc Mỹ tấn công đảo Hormuz của Iran (Hormuz Islands) nhằm "đáp trả hành động gây hấn của Tehran", chứ không đề cập bất kỳ sự kiện hay lý do nào liên quan đến Iraq.
- **Gold:** Không có thông tin.
- **Nguồn:** 1 · lỗi: —

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 3 · raw_schema_version: 3
- eval_code_sha256: `945ddf823850a913366505e7215da8207e74bf9ef49ca7224a861fb9b078ed1e`
- command: `run_evaluation.py --dataset-dir /tmp/opencode/steady_one_source --modules search,rag,pagematch --model-label smoke-api-check --tag api-check --fresh-notes --cleanup-notes`
- dataset_version: `4e6fa6ea3cfebd2c` · fingerprint: `4e6fa6ea3cfebd2c`
- provider/model/embedding: `` / `` / ``
- folder_id: `74b8a27d-a67e-44c0-ad68-e90ddf8a5fe0` · folder_mode: `run`
