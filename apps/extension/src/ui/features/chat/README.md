# features/chat — Hỏi đáp AI trên ghi chú (RAG, Nice-to-have)

Chưa triển khai. Khi làm (SDS §5.1.6):
- `ChatView.tsx` — khung hội thoại, hiển thị trích dẫn nguồn (note_id);
- RPC `chat.ask` trong `shared/messaging/protocol.ts`; background đọc SSE từ `POST /api/v1/ai/chat` và đẩy từng phần về UI qua port/broadcast;
- nút Stop → huỷ request ở background.

Owner: xem `.github/CODEOWNERS` (`/apps/extension/src/ui/features/chat/`).
