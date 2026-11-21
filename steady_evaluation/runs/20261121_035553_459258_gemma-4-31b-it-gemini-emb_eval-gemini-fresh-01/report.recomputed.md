# Báo cáo đánh giá steady — 20261121_035553_459258_gemma-4-31b-it-gemini-emb_eval-gemini-fresh-01
*Model: `gemma-4-31b-it+gemini-emb` · backend `http://localhost:8000/api/v1` · dataset `ef7c82ca643482ab` · git `6d09ed9c3` · eval-code `138d97ccf` · 2026-11-21T03:55:53.460294+00:00*

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
- create p50 = **68.11 ms** · chờ index p50 = **2031.41 ms** · p95 = **180794.17 ms**

## 3. Tìm kiếm ngữ nghĩa (hybrid SQL thật, nhóm theo nguồn)
`POST /search` với `max_sources=5`; Recall@5/MRR tính trên **tài liệu** (`document_id ?? note`), AnswerHit kiểm tra **toàn bộ part** của tài liệu gold.

| Queries | Hoàn thành | Lỗi | Recall@5 | Recall part | MRR | AnswerHit tài liệu | AnswerHit note | Nguồn TB | Nguồn max | Note TB | Rỗng | p50 (ms) | p95 (ms) | Sàn ngẫu nhiên |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 38 | 0 | 1.0 | 1.0 | 0.9868 | 1.0 | 1.0 | 4.05 | 5 | 6.47 | 0.0 | 617.03 | 748.77 | 0.4545 |

- corpus: 25 note / 11 tài liệu · `max_sources` đúng (ca chạm trần: 0.6053) · gold vắt qua ranh giới part: 0

## 4. RAG hỏi đáp (SSE thật, quota thật)
| Có căn cứ | Hoàn thành | Lỗi | Token-F1 gold (phụ) | F1 reference | Trích dẫn hợp lệ | Không trích dẫn | Số ngoài ngữ cảnh | tokens (TB) | total p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 38 | 11 | 27 | 0.1993 | — | 0.6364 | 0.3636 | 0.0 | 2087.0 | 24013.64 |

- Không có nguồn: 0.0 · không ngữ cảnh: 0.0 · ngữ cảnh TB: 51947.0 ký tự

| Không đủ căn cứ | Hoàn thành | Lỗi | Từ chối đúng | Trả lời bừa | Không nguồn |
|---:|---:|---:|---:|---:|---:|
| 11 | 1 | 10 | 1.0 | 0.0 | 0.0 |

- Số ngoài ngữ cảnh ở ca âm: 0.0
> *Trích dẫn hợp lệ* chỉ kiểm tra chỉ số `[n]` nằm trong số nguồn và câu trả lời có ít nhất một trích dẫn; không kiểm chứng nguồn có thực sự hỗ trợ ý. *Số ngoài ngữ cảnh* là proxy chuỗi trên toàn văn note nguồn, không phải kết luận bịa.

## 5. PageMatch (Trafilatura + văn bản dán)
**Chất lượng — segments** (không warning, top-5):
| Dương tính | Hit | Exact | Precision@k | Recall@k | F1@k | Span Precision | Span Coverage | Span F1 | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.296 | 0.1181 | 0.1689 | 0 | — | 21872.11 |

**Fallback** (warning `VERIFY_UNAVAILABLE` — chỉ đánh giá hành vi, không gộp chất lượng):
| Dương tính | Hit | Precision@k | Span Coverage | Âm tính | FPR | p50 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | — | — | 0 | — | 22114.83 |

- verify_unavailable_rate: 0.5918 · full_page_mode_rate: 0.5918 · truncated_rate: 0.0 · lỗi: 19

**Toàn bộ item trả về** (mọi ca, không cắt top-k — đúng như UI hiển thị):
| Dương tính | Gold trong bất kỳ item (`hit_all`) | `hit5_page` (metric cũ) | `hit5_score` | Precision all | Coverage all | Span Precision all |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.5 (19/38) | 0.2632 (10/38) | 0.4474 (17/38) | 0.0459 | 0.5107 | 0.0392 |

**Nhóm `verified=true`** (các đoạn UI auto-select):
| Dương tính | `verified_recall` | Verified precision (macro) | Verified precision (micro) | Âm tính | FPR bất kỳ item | `verified_fpr` |
|---:|---:|---:|---:|---:|---:|---:|
| 38 | 0.0 (0/38) | 0.0 | 0.0 | 11 | 0.8182 (9/11) | 0.0 (0/11) |

> `hit5_page` = 5 item đầu **theo thứ tự trang** (metric cũ, không phải top-5 theo score). `hit5_score` = 5 item tốt nhất theo `score`. `hit_all`/`verified_*` chấm trên **mọi item trả về**, gồm cả ca full-page và fallback.

## 6. Mẫu câu trả lời (bằng chứng thô)
### QA-001 (answerable=True)
- **Hỏi:** Vai trò của Jensen Huang trong Nvidia trước bê bối ngoại tình?
- **Đáp:** Trước bê bối ngoại tình, Jensen Huang giữ vai trò là CEO của Nvidia [1]. Trong thời gian này, Nvidia là một trong những doanh nghiệp giá trị nhất thế giới, với vốn hóa đạt mức đỉnh cao lên đến 5.700 tỷ USD [1].
- **Gold:** Theo Fortune, Huang là mắt xích then chốt của Nvidia.
- **Nguồn:** 3 · lỗi: —

### QA-003 (answerable=False)
- **Hỏi:** Diễn biến tâm lý của Huang sau khi bê bối ngoại tình bị phanh phui?
- **Đáp:** (trống)
- **Gold:** Không có thông tin.
- **Nguồn:** 2 · lỗi: AI_UNAVAILABLE: Dịch vụ AI tạm thời không khả dụng, hãy thử lại sau

## 7. Cách đọc & ranh giới
- Độ trễ là **end-to-end HTTP** (gồm mạng, embedding/LLM provider); chưa tách thời gian DB thuần.
- Token-F1 chỉ là trùng từ với đoạn gold/reference — metric phụ, không phải độ đúng ngữ nghĩa.
- Phát hiện từ chối là heuristic marker ở câu đầu; câu diễn đạt khác có thể bị bỏ sót.
- PageMatch quality chỉ gồm ca không warning; fallback báo riêng. Coverage là tỷ lệ chuỗi con chung dài nhất của gold trong block, không phải offset ký tự tuyệt đối.
- RAG grounding kiểm tra số trên **toàn văn note nguồn** khi fetch được; nếu không, fallback snippet.

## 8. Tái lập
- metrics_version: 4 · raw_schema_version: 3
- eval_code_sha256: `138d97ccfbd9512405011b8b3da8eb7857ef44323dc9575b7eeed37ac8318911`
- command: `run_evaluation.py --model-label gemma-4-31b-it+gemini-emb --provider gemini --model gemma-4-31b-it --embedding-model gemini-embedding-001 --provider-rpm 5 --wait-index-timeout 300 --folder-mode run --fresh-notes --tag eval-gemini-fresh-01 --evidence-type quality`
- dataset_version: `ef7c82ca643482ab` · fingerprint: `ef7c82ca643482ab`
- provider/model/embedding: `gemini` / `gemma-4-31b-it` / `gemini-embedding-001`
- provider_rpm: `5.0` · search_rpm: `None` · rag_rpm: `None` · pagematch_rpm: `None`
- folder_id: `24cb4be2-3b9a-4ac8-9ee9-1051fa6e0ab9` · folder_mode: `run`
