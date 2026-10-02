# background/ — Service worker (Extension Background)

Cửa ngõ mạng **duy nhất** của extension (ADR-0007): giữ token, gọi API, outbox, đồng bộ, menu chuột phải, phím tắt.

```
background/
├─ index.ts          composition root — CHỈ đăng ký listener (đồng bộ, top-level — yêu cầu MV3)
├─ handlers.ts       bảng định tuyến RPC: mỗi khoá trong RpcMap ↔ 1 handler (thiếu = lỗi biên dịch)
├─ api.ts            client API có gắn access token, tự refresh khi 401
├─ broadcast.ts      đẩy sự kiện (note đổi trạng thái…) về UI đang mở
├─ page-actions.ts   chrome.scripting.executeScript với hàm từ content/
├─ auth/             google.ts (launchWebAuthFlow + PKCE) · session.ts (lưu/xoá token)
└─ notes/            quick-note.ts (outbox IndexedDB, hoàn tác 5s, flush bằng alarm) · sync.ts (đồng bộ tăng dần)
```

**Quy tắc:** service worker có thể bị tắt bất cứ lúc nào → không giữ trạng thái quan trọng trong biến, dùng `chrome.storage`/IndexedDB; không import `ui/`.
