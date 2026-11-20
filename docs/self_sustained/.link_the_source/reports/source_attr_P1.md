# P1 — Nguồn khi dán (nguồn tham chiếu)

> Phase 1 của `docs/self_sustained/source-attribution-plan.md`
> Ngày: 2026-11-20 · Trạng thái: ✅ Hoàn thành

## Đã làm

- `apps/extension/src/background/page-match.ts`:
  - Thêm `getActiveTabSource()` — đọc metadata tab đang mở (`chrome.tabs.query` active + lastFocusedWindow), chỉ nhận URL `http/https`, title cắt 500 ký tự. Không thêm quyền, không tiêm script.
  - `RunArgs` thêm `url?`/`title?`; nhánh text truyền `url`/`title` vào `PageMatchRequest` (backend `PageMatchIn` đã hỗ trợ, chỉ metadata) và trả lại trong `PageMatchRun` (`tabId` vẫn undefined).
- `apps/extension/src/shared/messaging/protocol.ts`: thêm RPC `pageMatch/source`; mở rộng req `pageMatch/run` với `url?`/`title?`; cập nhật comment `PageMatchRun` (nguồn dán có thể có nguồn tham chiếu, không dùng để highlight).
- `apps/extension/src/background/handlers.ts`: wire `pageMatch/source` → `getActiveTabSource`.
- `apps/extension/src/ui/features/page-finder/SourceChip.tsx` (mới): chip “Nguồn tham chiếu” — hiện title + `sourceLabel(url)`, link mở trang nguồn, nút “Lấy lại tab”, “Bỏ”, “Nhập URL” (validate http/https, tối đa 2048 ký tự, lỗi inline).
- `apps/extension/src/ui/features/page-finder/PageFinderView.tsx`:
  - State `source: SourceRef | null`; vào chế độ dán → tự capture 1 lần; `onPaste` → capture nếu chưa có; capture không ghi đè nguồn người dùng đã chọn.
  - Quét (nguồn dán) gửi `url`/`title` theo chip; lưu note dùng `source.url` cho nguồn dán, `result.url` cho nguồn trang.
  - Kết quả nguồn dán có dòng “Nguồn tham chiếu: <link>”; tooltip “Xem trên trang” cập nhật theo plan.
- `styles.css`: nhóm class `.paste-source-*` + `.pf-source-ref` (dùng token hiện có, focus-visible, ellipsis).
- Test: `tests/page-match.test.ts` (+2 case: text branch với/không nguồn tham chiếu, `getActiveTabSource` 5 tình huống), `tests/ui/page-finder.test.tsx` (sửa 2 test cũ để biết RPC mới + 6 test mới cho chip).

## Kết quả kiểm chứng

- `npx vitest run tests/page-match.test.ts` → 23/23 pass.
- `npx vitest run tests/ui/page-finder.test.tsx` → 29/29 pass (24 cũ + 6 mới, 1 test cũ sửa tooltip).
- Full suite `npx vitest run` → **264/264 pass**, `npm run typecheck` → pass.

## Quyết định ghi nhận trong phase

| # | Vấn đề | Quyết định | Lý do |
|---|---|---|---|
| P1-D1 | Khi nào capture tab | Vào chế độ dán (effect) **và** sự kiện `paste` trên textarea; không capture khi bấm Quét | Người dùng có thể dán trước khi chip kịp lấy tab; không chặn luồng quét |
| P1-D2 | URL tay không hợp lệ | Báo lỗi **inline trong chip**, không đặt nguồn, **không chặn** quét/lưu | Chặn quét sẽ khoá cả luồng dán chỉ vì một input tuỳ chọn; chip vẫn cho sửa tiếp (plan đề xuất “chặn” — nới lỏng có chủ đích) |
| P1-D3 | URL tay có `title` | Để trống `title`, chip hiển thị `sourceLabel(url)` | Người dùng chỉ nhập URL; không tự đặt tên bài |
| P1-D4 | Tắt chế độ dán rồi bật lại | Giữ nguyên `source` hiện có | Người dùng có thể đang dùng URL tay; có nút “Lấy lại tab” để cập nhật |
| P1-D5 | Capture dán xong mới resolve, bấm Quét ngay | Quét dùng giá trị `source` tại thời điểm bấm (có thể null) | Edge case hiếm; người dùng có thể “Lấy lại tab”; tránh phức tạp hoá luồng async |
| P1-D6 | Shape RPC `pageMatch/source` | Validate `url` là string `http/https` trước khi set | RPC lỗi/mừu (mock cũ trả object lạ) không làm chip sai trạng thái |
| P1-D7 | Chip có nguồn mà muốn nhập URL tay | Thêm nút “Nhập URL” vào **cả** trạng thái có nguồn (plan wireframe chỉ vẽ [Lấy lại tab][Bỏ]) | D1 yêu cầu “sửa/bỏ/nhập URL tay”; phải “Bỏ” trước khi nhập là 2 bước thừa |
| P1-D8 | Manual input bọc trong `<label>` | Đổi sang `<div>` (input đã có `aria-label`) | Bọc nút trong label làm accessible name của nút “Dùng URL” bị lấy từ value của input → role query/accessibility sai |

## Chưa rõ / để lại

- Không có. Chip dùng icon `external` hiện có (chưa có icon “link” trong bộ Icon).
