# Hỏi AI — lưu lịch sử hội thoại theo phiên trên trình duyệt

> One-pager từ buổi idea-refine (13/11/2026). Tính năng nền: Hỏi đáp AI trên ghi chú (X02, ADR-0012 — server không lưu nội dung chat). UI tạm giản đơn; vòng redesign UI (kiểu Thư viện / Tìm trong trang) làm sau, ngoài phạm vi.
>
> **Trạng thái (13/11/2026): đã triển khai.** Khác plan một điểm: UI **không** đọc/ghi storage trực tiếp — thêm RPC `chatSessions/load|save` để giữ luật phân tầng (`tests/architecture.test.ts` cấm `ui/` import `shared/storage/`); background sở hữu key `qa.chatSessions`.
>
> **Cập nhật (13/11/2026): đã xong vòng redesign UI** theo demo `upgrade-plan/redesign/aichat` — xem mục cuối.

## Problem Statement
> Làm sao để hội thoại tab "Hỏi AI" không mất khi đóng side panel — lưu **nhiều phiên song song** ngay trên trình duyệt (`chrome.storage.local`, xoá khi đăng xuất), không đổi backend, và chuẩn bị sẵn tầng dữ liệu cho vòng redesign UI sau?

## Recommended Direction
**Hướng V2 — hook `useChatSessions` bọc quanh `useChat`.** `useChat` giữ nguyên 100% (thuần in-memory, test cũ không đổi). Hook mới quản lý: danh sách phiên, phiên đang mở, lưu/tải, auto-title. Redesign UI sau chỉ thay view, tái dùng nguyên tầng dữ liệu.

Lưu trữ: **một key duy nhất** `qa.chatSessions` = `{ v: 1, sessions, activeId }` trong `chrome.storage.local`, đặt ở module mới `src/shared/storage/chat-sessions.ts` — cùng nhà với `shared/storage/db.ts` (notesCache): UI hook đọc/ghi trực tiếp, `signedOut()` ở `background/handlers.ts` gọi `clearChatSessions()` (mở rộng dòng R-10). Chọn một key thay vì key/phiên vì tần suất ghi thấp (2 lần/lượt hỏi–đáp) và có cap; IndexedDB hay key-riêng-mỗi-phiên là over-engineering ở quy mô này.

Chiến lược ghi (điểm khó nhất — **không ghi per-delta khi stream**): ghi ngay khi gửi câu hỏi, khi câu trả lời kết thúc (done/stopped/error), và flush qua `pagehide` khi đóng panel. Khôi phục: message đang `streaming` → đánh dấu `stopped` (stream chết theo Port của panel — không hứa tiếp tục stream), giữ phần text đã nhận; `folderId` khôi phục kèm phiên. "Cuộc trò chuyện mới" = lưu lại phiên hiện tại (nếu có ≥1 cặp) + tạo phiên mới. `buildHistory` (cap 5 cặp) chạy trên mảng messages nên được miễn phí.

UI tạm: **Select chọn phiên** trong toolbar `ChatView` (tên = câu hỏi đầu cắt ~60 ký tự + thời gian) cạnh nút "Cuộc trò chuyện mới" hiện có. Không xoá từng phiên — redesign lo.

## Key Assumptions to Validate
- [ ] Quota `chrome.storage.local` (10 MB, manifest không có `unlimitedStorage`) đủ với cap 20 phiên × cap tin nhắn. *Đo `getBytesInUse` sau một buổi dùng "chăm chỉ".*
- [ ] Ghi 2 lần/lượt + flush `pagehide` đủ an toàn khi panel bị đóng đột ngột giữa stream. *Thử đóng panel giữa stream, mở lại kiểm tra.*
- [x] `folderId` đã bị xoá khi khôi phục → Select rơi về "Trong mọi thư mục" mà không lỗi (normalize value không khớp option). *Đã có test UI.*
- [ ] Không phát sinh save thừa khi chuyển tab trong panel (messages ở Shell không đổi). *Cơ chế `signature` đã chặn ghi khi chỉ đổi text/rerender; kiểm tra thủ công khi demo.*

## MVP Scope

### Extension (`apps/extension`)
1. `src/shared/chat.ts` (mới) — dời `ChatMessageItem` từ `useChat.ts` sang đây (useChat re-export để không vỡ import); kiểu `ChatSession` + hằng cap (`MAX_SESSIONS = 20`, cap tin nhắn/phiên); hàm thuần: `sessionTitle()`, `capMessages()` (cắt từ đầu theo cặp hỏi–đáp), `normalizeRestored()` (streaming→stopped, bỏ trả lời rỗng), `evictSessions()` (FIFO > 20) — unit test hết.
2. `src/shared/storage/chat-sessions.ts` (mới) — `load/save/clear` trên key `qa.chatSessions` (có `v: 1` để migrate khi redesign).
3. `src/ui/features/chat/useChatSessions.ts` (mới) — bọc `useChat`: load lúc mount, save theo chiến lược ghi, `switchSession(id)` (dừng stream đang chạy nếu có), `newSession()` (bọc `reset`), auto-title, evict; trả về `ChatState` + API phiên.
4. `src/ui/sidepanel/App.tsx` — thay `useChat()` → `useChatSessions()`; listener `pagehide` flush.
5. `src/ui/features/chat/ChatView.tsx` — toolbar thêm Select phiên (disabled khi streaming); không đổi luồng hỏi/đáp.
6. `src/background/handlers.ts` — `signedOut()`: thêm `await clearChatSessions()`.
7. Tests: unit cho hàm thuần (1); `tests/ui/chat-sessions.test.tsx` — lưu/khôi phục/chuyển phiên với `installChrome` + storage mock; giữ `tests/ui/chat.test.tsx` xanh (useChat không đổi).

### Docs
- `docs/adr/0012-chat-history-client-side.md` — appendix ngắn: lịch sử giờ lưu cục bộ nhiều phiên trên `chrome.storage.local`, xoá khi đăng xuất (R-10); server vẫn không lưu.
- `docs/user-guide.md`; `docs/qa/rtm.md` + `test-plan.md` (thêm case); `docs/architecture/README.md` (bản đồ storage).

## Not Doing (and Why)
- **Redesign UI phiên** (sidebar, đổi tên, ghim, tìm kiếm phiên) — *đã làm ở vòng redesign bên dưới* (chưa ghim).
- **Xoá từng phiên trong UI** — *đã làm ở vòng redesign bên dưới.*
- **Đồng bộ đa thiết bị / lưu server** — vi phạm ADR-0012.
- **Tiếp tục stream sau khi mở lại panel** — Port SSE chết theo panel; giới hạn có chủ ý.
- **Auto-title bằng AI** — câu hỏi đầu cắt 60 ký tự là đủ, không tốn hạn mức.
- **Đổi `MAX_HISTORY_PAIRS` / `buildHistory`** — hoạt động đúng như cũ trên lịch sử khôi phục.
- **IndexedDB / key-riên-mỗi-phiên** — over-engineering với cap hiện tại; xem lại chỉ khi getBytesInUse cảnh báo.

## Open Questions (đã chốt 13/11/2026)
- Tin nhắn dở khi khôi phục: **`stopped`** (nhãn "Đã dừng") — không thêm trạng thái/nhánh UI mới.
- Đổi thư mục hỏi giữa phiên: **giữ cùng phiên**, chỉ cập nhật `folderId` và lưu kèm.
- Cap: **20 phiên** × **40 tin nhắn/phiên** (20 cặp); chỉnh sau khi đo `getBytesInUse` nếu cần.

## Cập nhật 13/11/2026 — redesign UI (đã triển khai)

Áp demo `upgrade-plan/redesign/aichat/demo` vào `ChatView`, giữ đúng ngôn ngữ thị giác của Thư viện / Tìm trong trang
(chỉ token A05, radius 8px, system font) và tái dùng component sẵn có (`Button`, `Select`, `TextArea`, `Modal`,
`ConfirmDialog`, `ProgressBar`, `Icon`). Tầng dữ liệu `useChatSessions` chỉ được **mở rộng**, không đổi luồng hỏi/đáp.

- Bố cục: rail phiên | hội thoại khi ≥ 881px; ≤ 880px rail thành drawer trượt (nút trong header, scrim, Esc).
  Breakpoint 1100/980/880/720/480 dùng viewport media query cho khớp hai màn còn lại.
- Rail: tìm theo tiêu đề, "Mới", số lượt + ngày, chỉ báo "Đang trả lời", footer `n phiên` + dung lượng (**RPC mới
  `chatSessions/usage`** → `chatStorageUsage()` ở background), modal **Quản lý** (dung lượng + danh sách + xoá từng phiên).
- Hội thoại: header đổi tên inline / xoá phiên (confirm), empty state có câu hỏi mẫu, turn người dùng/AI, pill
  "Đang trả lời"/"Đã dừng", sao chép, "Hỏi lại", chip nguồn + "Chi tiết nguồn" (khoá khi đang stream), `ErrorCard`.
- API hook thêm `renameSession` / `deleteSession` / `clearSessions`; rename/delete/clear đi qua state + RPC
  `chatSessions/save` sẵn có (một đường ghi duy nhất, không thêm RPC ghi). Đổi phiên giữa stream: dừng stream, chốt
  phần đã nhận ở phiên cũ dạng `stopped`.
- Xoá tất cả dùng `ConfirmDialog` với `confirmText="XOÁ"` (2 bước); xoá một phiên chỉ cần confirm thường.
- Select phạm vi chỉ hiện tên thư mục (không kèm số ghi chú); option rỗng đổi thành "Tất cả thư mục".
- Test: `tests/ui/chat.test.tsx`, `tests/ui/chat-sessions.test.tsx` (rail thay select, thêm đổi tên/xoá/quản lý/lọc,
  chuyển phiên khi đang stream), `tests/chat-sessions.test.ts` (`chatStorageUsage`), `e2e/x02-chat.spec.ts`
  (selector mới + case drawer ở panel hẹp).
