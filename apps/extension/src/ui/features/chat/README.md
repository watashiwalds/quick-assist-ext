# features/chat — Hỏi AI trên ghi chú (RAG, X02)

- `useChat.ts` — trạng thái hội thoại (đặt ở Shell của side panel để chuyển tab không mất), gửi kèm tối đa
  5 cặp hỏi–đáp gần nhất; lịch sử chỉ nằm trong bộ nhớ panel (ADR-0012).
- `ChatView.tsx` — giao diện split-view theo demo `upgrade-plan/redesign/aichat`: rail phiên (tìm, Mới,
  footer dung lượng + **Quản lý**) | hội thoại (header đổi tên/xoá, câu trả lời hiện dần, trích dẫn `[n]`
  bấm được, chip + chi tiết nguồn, nút **Dừng**, composer lọc theo thư mục). ≤880px rail thu thành drawer.
- `useChatSessions.ts` — lưu nhiều phiên trên máy: chuyển/tạo/đổi tên/xoá phiên, xoá tất cả; chỉ ghi ở
  mốc hội thoại đổi (không ghi mỗi delta). Dung lượng lấy qua RPC `chatSessions/usage`.
- Luồng dữ liệu: `askChat()` (shared/messaging/client) mở Port `qa-chat` → `background/chat.ts` gọi
  `POST /api/v1/ai/chat` (SSE) → chuyển tiếp `sources` / `delta` / `done` | `stopped` | `error` về UI.
  Dừng = huỷ request ở background → server chỉ trừ hạn mức phần đã sinh.

Owner: xem `.github/CODEOWNERS` (`/apps/extension/src/ui/features/chat/`).
