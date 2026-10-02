# ADR-0007: Extension — background là cổng mạng duy nhất, RPC có kiểu, không content script thường trực

**Bối cảnh.** MV3 có nhiều ngữ cảnh (service worker, popup, side panel, trang). Token, retry, cache cần một chỗ quản lý; quyền rộng (`<all_urls>`) làm tăng rủi ro và gây khó khi duyệt store.

**Quyết định.**
- Chỉ `background/` gọi API (`shared/api/*`) và IndexedDB. UI/trang gửi **RPC** theo hợp đồng `shared/messaging/protocol.ts` (`RpcMap`); `background/handlers.ts` có kiểu buộc đủ handler.
- Không khai báo content script; đọc vùng chọn và hiện toast bằng `chrome.scripting.executeScript` với `activeTab` (quyền tạm thời do người dùng thao tác). `host_permissions` chỉ gồm origin API.
- Kiểu dữ liệu API sinh từ OpenAPI (`npm run gen:api`).

**Phương án đã loại.** UI tự `fetch` (token và retry rải rác 3 nơi, refresh song song gây `REFRESH_REUSED`); content script trên mọi trang (quyền rộng, chạy cả khi không dùng).

**Hệ quả.** (+) 1 chỗ gắn token/refresh/retry; quyền tối thiểu; UI test được bằng mock RPC. (−) Thêm boilerplate 2 dòng cho mỗi tính năng (khai báo RPC + handler); hàm tiêm phải tự chứa (không import).
