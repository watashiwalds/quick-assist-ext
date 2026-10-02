# ADR-0009: SSE cho streaming câu trả lời chat (Nice-to-have)

**Bối cảnh.** SDS §5.1.6: trả lời từng token, có nút Stop, trừ quota khi stream kết thúc hoặc bị ngắt.

**Quyết định (đề xuất).** `POST /ai/chat` trả `text/event-stream` (sự kiện `delta`, `sources`, `done`). Background đọc bằng `fetch` + `ReadableStream`, chuyển tiếp cho side panel qua `chrome.runtime.connect` (Port). Stop = `AbortController.abort()` → server nhận `CancelledError` → vẫn `quota.commit` phần đã sinh.

**Phương án đã loại.** WebSocket (hai chiều không cần thiết, khó qua proxy, phải tự quản lý kết nối); long-polling (trễ, tốn request).

**Hệ quả.** (+) Chạy trên HTTP thường, đơn giản. (−) Một chiều; mỗi câu hỏi là một request mới (chấp nhận).
