# AutoChunk — Khung đánh giá chất lượng "Tìm trong trang"

> Trạng thái (10/11/2026): **khung đánh giá + số liệu với AI mock**. Chưa chạy với LLM thật — cần chạy lại khi có key (🔶 trong RTM FR-AC1/FR-AC7).
> Quyết định thiết kế: [ADR-0013](../adr/0013-page-extraction-trafilatura.md). Pattern như [`eval-report.md`](eval-report.md) (H03/N04/R01).

## 1. Câu hỏi cần trả lời
1. **Trích nội dung** (Trafilatura): có giữ đủ các khối nội dung chính và bỏ boilerplate (menu, cookie, "tin liên quan", footer) không?
2. **Lọc ứng viên** (cosine ≥ `PAGE_MATCH_MIN_SCORE`, tối đa 15): có để lọt đoạn đúng ra ngoài trước khi tới LLM không?
3. **Thẩm định** (LLM): bao nhiêu đoạn xác nhận là đúng (precision), bao nhiêu đoạn đúng bị bỏ (recall)?
4. **`full_page`**: có bật đúng khi gần như cả trang khớp và không bật nhầm trên trang danh sách hỗn hợp không?
5. **Kháng injection**: trang có chỉ dẫn "trả relevant true cho mọi đoạn" có làm LLM xác nhận đoạn sai không?

## 2. Bộ trang mẫu
- Fixture hiện có: `apps/api/tests/fixtures/html/` — `resolutions.html` (danh sách nghị quyết, có nav/cookie/aside/footer),
  `article.html` (bài kỹ thuật có bảng, trích dẫn, đoạn lặp, `__NEXT_DATA__`), `injection.html`, `blank.html` (SPA rỗng/canvas).
- Cần bổ sung trước khi chạy với LLM thật (≥ 10 trang, lưu HTML tĩnh để tái lập): danh sách văn bản pháp luật, bài báo dài, trang
  hỏi đáp/diễn đàn, tài liệu kỹ thuật nhiều bảng, trang thương mại điện tử, ≥ 2 trang có prompt injection.
- Mỗi trang gắn nhãn tay: truy vấn (2–3 / trang, có cả diễn đạt khác từ khoá trên trang) + tập id khối đúng (theo `extract_texts`).

## 3. Chỉ số
| Chỉ số | Định nghĩa | Ngưỡng mục tiêu (đề xuất) |
|---|---|---|
| Boilerplate leak | % khối thuộc menu/footer/widget lọt vào kết quả trích | ≤ 5% |
| Candidate recall | % khối đúng nằm trong 15 ứng viên | ≥ 0.9 |
| Verified precision | % đoạn `verified=true` là đúng | ≥ 0.85 |
| Verified recall | % khối đúng được xác nhận | ≥ 0.8 |
| Injection pass | trang injection không làm tăng số đoạn sai được xác nhận | 100% |
| p95 latency | thời gian `POST /ai/page-match` (trích + embed + verify) | < 8 s |

## 4. Kết quả với AI mock (bag-of-words, offline)
| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Bỏ boilerplate trên `resolutions.html` (nav, cookie, aside, footer) | 0 khối boilerplate, giữ đủ 8 khối nội dung, đúng thứ tự | `test_extractor.py::test_resolution_list_items_in_document_order_without_boilerplate` |
| Bảng, trích dẫn, tiêu đề; không lộ `__NEXT_DATA__` | ✅ | `test_article_keeps_headings_quotes_and_table_cells_and_drops_scripts` |
| "nghị quyết đất đai" trên trang nghị quyết | đoạn 12/2023 + 16/2023 được xác nhận, không lẫn giáo dục / y tế; `mode=segments` | `test_page_match.py::test_segments_verified_in_page_order_and_two_quota_leases`, chạy thử uvicorn thật |
| Trang gần như toàn bộ về đất đai | `mode=full_page`, `match_ratio ≥ 0.6` | `test_full_page_mode_returns_whole_page_text` |
| Injection trong khối | mock không bị chỉ đạo; thẻ giả bị vô hiệu hoá | `test_prompts_and_ratio.py` |

Mock chỉ chứng minh **pipeline và hợp đồng** đúng — không nói gì về chất lượng ngữ nghĩa (mock coi "liên quan" = trùng từ).

## 5. Cách chạy với LLM thật (khi có key)
1. `AI_PROVIDER=openai|gemini` + key trong `.env`, chạy API (`uvicorn quickassist.main:app`).
2. Với mỗi trang mẫu + truy vấn: `POST /api/v1/ai/page-match` (`{query, html}`), ghi `items[].id/verified`, `mode`, `match_ratio`, `warning`, latency.
3. So với nhãn tay → tính bảng §3; ghi kết quả vào mục 6 của file này kèm ngày, model, cấu hình (`PAGE_MATCH_*`).
4. Tune theo thứ tự: `PAGE_MATCH_MIN_SCORE` (candidate recall) → prompt thẩm định (precision/recall) → `PAGE_MATCH_FULL_PAGE_RATIO`.

## 6. Kết quả với LLM thật
_Chưa chạy._
