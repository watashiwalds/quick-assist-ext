# Tìm trong trang — thêm nguồn "Nội dung dán"

> One-pager từ buổi idea-refine (12/11/2026). Tính năng nền: AutoChunk "Tìm trong trang" (ADR-0013).

## Problem Statement
> Làm sao để "Tìm trong trang" (AutoChunk, ADR-0013) nhận thêm **nội dung người dùng dán vào** (PDF, Word, chat, email — gần như mọi nguồn dạng chữ) làm nguồn xử lý, song song với tab đang mở, với thay đổi tối thiểu và giữ đúng kiến trúc phân lớp hiện có?

## Recommended Direction
**Hướng B — text là nguồn hạng nhất.** API `POST /ai/page-match` thêm trường `text` song song với `html` (bắt buộc chọn đúng một). Service rẽ nhánh: `text` → tách đoạn → `build_blocks()` trực tiếp (hàm thuần đã có trong `extractor.py`, bỏ qua Trafilatura vốn chỉ dành cho HTML không tin cậy); `html` → giữ nguyên hiện trạng. Toàn bộ pipeline phía sau — embed 1 batch, cosine, LLM thẩm định, `segments|full_page`, degrade `VERIFY_UNAVAILABLE`, quota 2 lease — **không đổi một dòng**.

Lựa chọn này thay vì "bọc HTML" (hướng A) vì Trafilatura làm phẳng xuống dòng (mất ranh giới đoạn khi copy từ PDF/Word → đoạn cắt theo câu, kém tự nhiên), và vì việc nhét text không phải HTML vào trường `html` đi ngược convention phân lớp rất chặt của repo. Đổi lại là một thay đổi nhỏ có kiểm soát ở schema + service, tái dùng tối đa hàm thuần sẵn có. Hướng C ("nguồn" thống nhất cho Tóm tắt / Hỏi AI) ghi lại làm hướng tương lai, không làm trong MVP.

UX: nút phụ **"Dán nội dung…"** trong tab "Tìm trong trang" → textarea dán (Ctrl+V thủ công, không thêm permission) → cùng một luồng kết quả / chọn đoạn / lưu ghi chú. Nút "Xem trên trang" **vô hiệu hoá kèm giải thích** khi nguồn là dán. Ghi chú lưu với **tiêu đề = truy vấn, không URL** (`notes/create` đã chấp nhận `url: string | null` — đã xác nhận trong `apps/extension/src/shared/messaging/protocol.ts`).

## Key Assumptions to Validate
- [ ] Tách đoạn theo dòng trống (`\n\n`) cho khối tự nhiên; text PDF copy chỉ có `\n` đơn → fallback tách câu (`split_long_block` đã có). *Kiểm tra với 2–3 mẫu copy thật từ PDF, Word, chat.*
- [ ] Cap 50.000 ký tự (`PAGE_MATCH_MAX_CHARS`) đủ cho đa số tài liệu (~10–12 trang); dài hơn → banner "chỉ phần đầu được quét" (đã có sẵn). *Thử dán tài liệu 20 trang.*
- [ ] Dán thủ công vào textarea **không cần permission mới** — giữ nguyên tắc quyền tối thiểu H01. *Xác nhận trong code review.*
- [ ] Chất lượng "đoạn" từ đường dẫn text tốt hơn đường dẫn bọc HTML. *So sánh A/B trên 1 mẫu PDF trong lúc test.*

## MVP Scope

### Backend (`apps/api`)
1. `presentation/schemas/page_match.py` — `PageMatchIn`: thêm `text: str | None`; `html` thành optional; `model_validator` bắt lỗi "phải có đúng một trong hai".
2. `business/page_match/extractor.py` — hàm thuần mới `split_paragraphs(text)` (tách `\n\n`, fallback câu) + unit test.
3. `business/page_match/page_match_service.py` — `match()` nhận `text`; rẽ nhánh text → `build_blocks()` trực tiếp (skip Trafilatura + process pool); giữ nguyên embed/verify/quota/log.
4. `presentation/api/v1/controllers/page_match_controller.py` — truyền `text` xuống service.
5. Tests: schema validator, `split_paragraphs`, service text path, `PAGE_NO_CONTENT` khi text rỗng sau split.

### Extension (`apps/extension`)
6. `src/shared/messaging/protocol.ts` — `pageMatch/run` req thêm `text?: string`; `PageMatchRun` → `tabId?`, `url: string | null`.
7. `src/background/page-match.ts` — `runPageMatch({ query, text? })`: khi có `text` → bỏ capture/tabId, gọi API với `{query, text, url: null}`.
8. `src/shared/api/` — cập nhật type request `pageMatch`.
9. `src/ui/features/page-finder/PageFinderView.tsx` — nút "Dán nội dung…" cạnh "Quét trang" → chế độ textarea (counter ký tự, cho phép dán dài, backend tự truncate + banner) → "Quét nội dung"; khi `result.tabId == null`: ẩn "Xem tất cả trên trang", nút "Xem trên trang" disabled + tooltip *"Nội dung dán không có trang gốc để xem"*, đổi copy "Lưu cả trang" → "Lưu toàn bộ nội dung", banner "Trang rất dài" → "Nội dung rất dài"; lưu với `url: result.url ?? null`.
10. Tests: `tests/page-match.test.ts` (nguồn text không đụng `chrome.scripting`), `tests/ui/page-finder.test.tsx` (luồng dán + lưu không URL).

### Docs
- `docs/api/conventions.md` (bảng endpoint), `docs/user-guide.md`, `docs/ux/README.md` (Luồng 7), ADR (xem Open Questions).

## Not Doing (and Why)
- **HTML/Markdown khi dán** — đã xác nhận text thuần là đủ; thêm sau nếu nhu cầu thật xuất hiện.
- **Tự đọc clipboard** (`navigator.clipboard.readText` + permission `clipboardRead`) — ngược nguyên tắc quyền tối thiểu H01; Ctrl+V thủ công không cần permission nào.
- **Gộp nhiều nguồn trong một lần quét** — UX phức tạp (phân tách nguồn), chưa có nhu cầu được xác nhận.
- **Nâng cap 50k ký tự cho nguồn dán** — quota AI là ràng buộc thật; banner truncate đã xử lý case dài.
- **"Xem trên trang" cho nội dung dán** — không tồn tại trang gốc; disabled + tooltip là đủ.
- **Mở rộng "nguồn" cho Tóm tắt / Hỏi AI** (hướng C) — scope creep; ghi lại làm hướng tương lai.
- **Tab riêng cho tính năng dán** — nút phụ trong tab hiện có, ít điều hướng hơn.

## Open Questions
- Cap text dùng chung `PAGE_MATCH_MAX_CHARS` hay thêm `PAGE_MATCH_MAX_TEXT_CHARS` riêng? *(khuyến nghị: dùng chung, chỉ tách khi cần)*
- ADR: cập nhật appendix của ADR-0013 hay viết ADR-0015 mới? *(0014 đã bị UI Evolution chiếm; khuyến nghị ADR-0015 mới vì đây là thay đổi contract API)*
- Truy vấn rất ngắn (vd. "tóm tắt") làm tiêu đề ghi chú — chấp nhận hay thêm ô "Tiêu đề" khi lưu từ nguồn dán? *(MVP: chấp nhận)*
