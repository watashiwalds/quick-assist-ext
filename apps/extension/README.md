# apps/extension — Chrome Extension (Manifest V3)

TypeScript + React + Vite + CRXJS. Tương ứng "Extension UI" và "Extension Background" trong SDS Hình 1.

```
apps/extension/
├─ manifest.config.ts     quyền: activeTab, scripting, contextMenus, sidePanel, storage, identity, alarms
├─ src/
│  ├─ ui/                 giao diện (popup, side panel) — chỉ hiển thị, gọi background qua RPC
│  ├─ background/         service worker — CỬA NGÕ MẠNG DUY NHẤT: gọi API, giữ token, outbox, đồng bộ
│  ├─ content/            hàm tự chứa được tiêm vào trang khi người dùng thao tác (không có content script thường trực)
│  └─ shared/             dùng chung: hợp đồng RPC, client HTTP + kiểu API, IndexedDB, PKCE, lỗi, config
└─ tests/                 vitest: architecture.test.ts (luật phụ thuộc), outbox, pkce
```

## Luồng phụ thuộc

```
ui ──RPC (shared/messaging)──► background ──HTTPS──► API /api/v1
                                   │
                                   └─ chrome.scripting ──► content (tiêm vào tab)
shared ◄── ai cũng được dùng; shared không import ai
```

Luật được kiểm tra trong `tests/architecture.test.ts` (CI):
- `ui/` **không** import `background/`, `shared/storage/`, `shared/api/*` (trừ `shared/api/types`) → UI không tự gọi mạng/IndexedDB;
- `content/` không import gì (hàm bị tuần tự hoá khi tiêm);
- `shared/` không import tầng nào khác;
- `background/` không import `ui/`.

## Thêm tính năng — đặt file ở đâu

| Việc | File |
|---|---|
| Màn hình / khối UI mới | `src/ui/features/<tính năng>/` (component dùng chung → `ui/components/`, hook → `ui/lib/`) |
| UI cần dữ liệu mới | khai báo RPC ở `shared/messaging/protocol.ts` → viết handler ở `background/handlers.ts` (thiếu handler = lỗi biên dịch) |
| Gọi endpoint mới | `shared/api/endpoints.ts`; khi backend đổi schema: `npm run gen:api` |
| Thao tác trên trang | hàm tự chứa trong `content/injected.ts`, gọi từ `background/page-actions.ts` |
| Lưu offline / cache | `shared/storage/db.ts` (IndexedDB), chỉ background dùng |

## Chạy

```bash
cp .env.example .env.local       # điền VITE_GOOGLE_CLIENT_ID
npm install
npm run dev                      # hoặc npm run build → dist/
npm test                         # unit + kiến trúc
```
Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → `apps/extension/dist`.
