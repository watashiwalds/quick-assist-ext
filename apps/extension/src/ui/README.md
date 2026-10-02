# ui/ — Extension UI (popup, side panel)

```
ui/
├─ popup/        entry popup (index.html, main.tsx, Popup.tsx)
├─ sidepanel/    entry side panel (index.html, main.tsx, App.tsx)
├─ features/     mỗi tính năng một thư mục: auth, notes, search, summary, chat (RAG — Nice-to-have)
├─ components/   component dùng chung, không biết nghiệp vụ
├─ lib/          hooks (useAsync, useBroadcast)
└─ styles.css
```

**Được:** React component, state hiển thị, gọi `rpc(...)` từ `@/shared/messaging/client`, dùng kiểu từ `@/shared/api/types`.

**Cấm** (test kiến trúc): import `background/`, `shared/storage/`, `shared/api/http|endpoints` — UI không gọi `fetch`, không mở IndexedDB, không giữ token.
Nội dung ghi chú/trang web hiển thị bằng text (React escape sẵn) — không dùng `dangerouslySetInnerHTML`.
