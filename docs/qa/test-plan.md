# P08 — Chiến lược kiểm thử QuickAssist

> Owner: Trần Thùy Dương · Phối hợp: Lê Đăng Sơn · Cập nhật 09/10/2026 · Ma trận truy vết: [`rtm.md`](rtm.md)

## 1. Mục tiêu
Mọi yêu cầu **Must-have** (SDS v1.1 §3.1) và NFR (§3.2) có ít nhất một ca kiểm thử tự động chạy trong CI, có người chịu trách nhiệm, và có bằng chứng (biên bản trong `reports/`).

## 2. Kim tự tháp kiểm thử
| Tầng | Công cụ | Vị trí | Số ca (09/10) | Chạy ở |
|---|---|---|---|---|
| Kiến trúc (luật tầng L1–L7, ranh giới extension) | pytest, vitest | `apps/api/tests/architecture`, `apps/extension/tests/architecture.test.ts` | 7 + 4 | CI mỗi PR |
| Unit backend (business, infrastructure) | pytest | `apps/api/tests/unit` | 85 | CI |
| Integration backend (HTTP + PostgreSQL/pgvector thật, AI mock) | pytest + httpx ASGI | `apps/api/tests/integration` | 74 | CI (service pgvector) |
| Đánh giá chất lượng tìm kiếm (Recall@5, MRR, p95) | pytest | `apps/api/tests/eval` | 2 cổng | CI |
| Unit extension (outbox, sync, phiên, hàm tiêm, UI, tương phản màu) | vitest + happy-dom + Testing Library | `apps/extension/tests` | 80 | CI |
| **E2E** extension thật + backend thật | Playwright (Chromium) + axe-core | `apps/extension/e2e` | 28 | CI job `e2e` |
| Smoke test môi trường demo/RC | script | `apps/api/scripts/smoke_test.py` | 11 bước | sau mỗi deploy |
| Thủ công / người dùng | checklist | [`demo-script.md`](../demo-script.md), H05 | — | trước demo |

(Số liệu đúng tại commit cuối; `pytest -q`, `npx vitest run`, `npx playwright test` in tổng.)

## 3. Môi trường
- **CI**: GitHub Actions — `pgvector/pgvector:pg16`, Python 3.11, Node 22, Chromium của Playwright. AI = mock (không tốn tiền, tất định).
- **Dev**: `docker compose -f infra/docker-compose.yml up` hoặc chạy tay (README).
- **Demo**: `infra/docker-compose.prod.yml` + OpenAI thật; chỉ chạy smoke test + checklist demo + `tests.eval.summary_injection`.

## 4. Dữ liệu kiểm thử
Chỉ dữ liệu tự viết, an toàn (SDS §2.1): `tests/eval/dataset_vi.json` (20 ghi chú, 46 truy vấn), `tests/eval/summary_pages.json` (10 trang, 3 trang prompt injection), `e2e/pages/article.html` (trang có CSS "phá" giao diện). Không dùng tài khoản Google thật trong test tự động — E2E dùng `dev-login` (chỉ bật ở dev/test, bị chặn ở prod).

## 5. Tiêu chí vào / ra
| | Điều kiện |
|---|---|
| Vào kiểm thử một task | có acceptance criteria trong backlog; build xanh |
| Ra (Definition of Done) | ca kiểm thử nhánh chính + nhánh lỗi pass trong CI; không còn lỗi P0/P1 mở; biên bản ghi số pass/fail + commit |
| Phát hành (H05) | 100% ca E2E P0 pass; axe không vi phạm WCAG AA; smoke test RC 11/11; checklist demo pass |

## 6. Phân loại lỗi
| Mức | Ví dụ | Xử lý |
|---|---|---|
| P0 | mất ghi chú, lộ dữ liệu người khác, không cài được extension | chặn phát hành, sửa ngay |
| P1 | chức năng Must-have sai, quota trừ sai | sửa trong tuần |
| P2 | giao diện/thông báo chưa rõ | xếp lịch |
| P3 | góp ý | backlog |

Lỗi ghi trong GitHub Issues: tiêu đề `[P0][N07] …`, kèm `request_id` (mã lỗi hiện trên giao diện), bước tái hiện, owner theo CODEOWNERS.

## 7. Lỗi đã phát hiện nhờ bộ kiểm thử (09/10/2026)
| # | Mức | Mô tả | Phát hiện bởi | Đã sửa |
|---|---|---|---|---|
| 1 | **P0** | Manifest khai báo phím `Ctrl+Alt+N` — Chrome cấm tổ hợp Ctrl+Alt nên **extension không nạp được** | E2E (service worker không khởi động) | ✅ đổi sang `Alt+Shift+N` / `Alt+Shift+Z` |
| 2 | P1 | Đổi tên thư mục / "Thử lại AI" trả 500 (thuộc tính `updated_at` hết hạn sau commit) | integration `test_notes_crud` | ✅ |
| 3 | P1 | Dùng lại `Idempotency-Key` cho tóm tắt → gọi AI lần 2 **không trừ quota**; key trùng giữa 2 user dùng chung ledger | integration `test_summary`, `test_quota` | ✅ request_id gắn user + 409 |
| 4 | P1 | Job index thử lại sau lỗi tạm thời → lần thử sau **không bị tính quota** | integration `test_indexing_job` | ✅ request_id theo lần thử |
| 5 | P1 | Giữ chỗ quota bị treo vĩnh viễn nếu tiến trình chết giữa chừng | review + test | ✅ worker hoàn định kỳ |
| 6 | P1 | Ước lượng token thấp hơn thực tế ~29% với tiếng Việt (giữ chỗ thiếu) | spike P03 | ✅ |
| 7 | P1 | Ghi chú gửi lỗi không thể thử lại bị **xoá âm thầm** khỏi outbox | review N06 | ✅ store "failed" + Gửi lại/Bỏ |
| 8 | P1 | Mất mạng → side panel báo lỗi thay vì mở thư viện từ cache | E2E C05 | ✅ |
| 9 | P2 | Tìm "mua quà gì ở đà lạt" / gõ không dấu không ra kết quả từ khoá | eval H03 | ✅ unaccent + OR (Recall không dấu 0.77 → 1.0) |
| 10 | P2 | Hộp thoại lồng nhau trùng `id` tiêu đề (trình đọc màn hình đọc sai) | E2E C05 | ✅ |
| 11 | P2 | Nút "nguy hiểm" chữ trắng trên nền đỏ nhạt ở chế độ tối (tương phản < 4.5) | test tương phản | ✅ token `--danger-fg` |
| 12 | P2 | So sánh mốc đồng bộ theo chuỗi ("…43Z" vs "…43.5Z") có thể bỏ sót | review C02 | ✅ |

| 13 | P1 | AutoChunk "Lưu cả trang" > 20 000 ký tự bị tách cứng giữa chừng một từ (mất ranh giới đoạn) | vitest `page-finder.test.tsx` | ✅ tách theo biên khối trước khi gộp |

### 7.1 AutoChunk — "Tìm trong trang" (10/11/2026, ADR-0013)
| Lớp | Bộ test | Phủ |
|---|---|---|
| Unit (pytest) | `unit/business/page_match/test_extractor.py` | Trafilatura bỏ nav/cookie/aside/footer; thứ tự tài liệu; `id`/`occ`; tách câu không mất chữ; cap theo biên khối; parser treo/crash → bị giết, pool tự hồi phục |
| Unit (pytest) | `unit/business/page_match/test_prompts_and_ratio.py` | bọc `<document>`, vô hiệu thẻ `document/query/block` giả; parse JSON chỉ nhận id đã gửi; mock không bị chỉ đạo; `match_ratio` (ngoại suy khi > 15 ứng viên) |
| Integration (pgvector) | `integration/api/test_page_match.py` | contract; embed đúng 1 batch; 2 lease quota COMMITTED/RELEASED; `VERIFY_UNAVAILABLE` (LLM lỗi / JSON rác); 413/422/402/429/502/401; `full_page`; lưu bằng `POST /notes` |
| Kiến trúc | `architecture/test_layers.py::test_L8_only_page_match_parses_untrusted_html` | chỉ `business/page_match` import trafilatura/lxml |
| Extension (vitest) | `tests/page-match.test.ts` | `getRawHtml` bỏ thẻ + dữ liệu nhạy cảm, không sửa DOM thật, > 2 MB dừng sớm; `highlightBlocksByText` (khoảng trắng, `<br>`, occ, contains, fuzzy, tự tắt, khôi phục nguyên trạng DOM); background run/highlight + lỗi |
| UI (vitest) | `tests/ui/page-finder.test.tsx` | quét → tích sẵn đoạn đã xác nhận → lưu gộp; bỏ chọn; badge theo `warning`; rỗng; highlight; `full_page` + hỏi lại + tách nhiều ghi chú; 402/413/422/mạng; xin quyền đọc trang |
| Cần người thật | — | chất lượng thẩm định với LLM thật trên bộ trang mẫu (`docs/ai/page-match-eval.md`); highlight trên trang SPA/React thật |

## 8. Việc còn lại cần người thật / tài khoản thật
- Đăng nhập Google thật (cần OAuth client của nhóm) — checklist demo bước 4.
- `tests.eval.summary_injection` và `run_eval` với OpenAI thật (SUM-04, H03 phần OpenAI).
- Kiểm thử khả dụng (usability) với 3–5 sinh viên theo kịch bản `demo-script.md` §3 (H05).
