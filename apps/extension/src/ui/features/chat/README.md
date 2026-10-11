# features/chat — Hỏi AI trên ghi chú (RAG, X02)

- `useChat.ts` — trạng thái hội thoại (đặt ở Shell của side panel để chuyển tab không mất), gửi kèm tối đa
  5 cặp hỏi–đáp gần nhất; lịch sử chỉ nằm trong bộ nhớ panel (ADR-0012).
- `ChatView.tsx` — khung hội thoại: câu trả lời hiện dần, trích dẫn `[n]` bấm được để mở ghi chú,
  danh sách nguồn, nút **Dừng**, lọc theo thư mục.
- Luồng dữ liệu: `askChat()` (shared/messaging/client) mở Port `qa-chat` → `background/chat.ts` gọi
  `POST /api/v1/ai/chat` (SSE) → chuyển tiếp `sources` / `delta` / `done` | `stopped` | `error` về UI.
  Dừng = huỷ request ở background → server chỉ trừ hạn mức phần đã sinh.

Owner: xem `.github/CODEOWNERS` (`/apps/extension/src/ui/features/chat/`).
