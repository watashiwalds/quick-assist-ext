# shared/ — Dùng chung cho background và UI

```
shared/
├─ messaging/   protocol.ts (hợp đồng RPC UI ↔ background, có kiểu) · client.ts (hàm rpc() cho UI)
├─ api/         http.ts, endpoints.ts (chỉ background dùng) · types.ts (UI được dùng) · schema.d.ts (sinh từ OpenAPI — không sửa tay)
├─ storage/     db.ts — IndexedDB: outbox + cache ghi chú (chỉ background dùng)
├─ pkce.ts      code_verifier / code_challenge
├─ errors.ts    AppError + mã lỗi khớp backend
└─ config.ts    đọc biến VITE_*
```

**Quy tắc:** không import `background/`, `ui/`, `content/`. Đổi `messaging/` hoặc `api/` là đổi hợp đồng → cần cả hai owner duyệt (CODEOWNERS).
