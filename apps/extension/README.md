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
├─ tests/                 vitest: kiến trúc, outbox/quick-note, sync/phiên, hàm tiêm, UI (React Testing Library), tương phản màu
├─ e2e/                   Playwright: extension thật + backend thật (xem e2e/README.md)
└─ scripts/check-bundle.mjs  rà soát bản build: không secret, không quyền thừa, không hook kiểm thử (H01)
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
cp .env.example .env.local       # điền VITE_GOOGLE_CLIENT_ID (+ VITE_EXTENSION_KEY để cố định ID)
npm install
npm run dev                      # hoặc npm run build → dist/
npm test                         # unit + kiến trúc + UI
npm run check:bundle             # sau build: rà soát bảo mật bundle (H01)
npm run test:e2e                 # E2E — cần backend chạy (e2e/README.md)
```
Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → `apps/extension/dist`.

## Phím tắt
| Phím | Việc |
|---|---|
| **Alt+Shift+N** | Ghi chú nhanh đoạn đang bôi đen (vào thư mục mặc định trong Cài đặt — mặc định Inbox) |
| **Alt+Shift+Z** | Hoàn tác khi toast đang đếm ngược 5 giây |

Chrome **không cho phép** tổ hợp `Ctrl+Alt+…` trong manifest (trùng phím AltGr) — bản cũ khai báo `Ctrl+Alt+N` khiến extension **không nạp được**. Đổi phím tại `chrome://extensions/shortcuts`. Chọn thư mục cho từng ghi chú: chuột phải → *QuickAssist ▸ Ghi chú vào thư mục ▸ …*

## Cố định Extension ID cho cả nhóm (R-03)
Mỗi máy "Load unpacked" sẽ ra ID khác → redirect URI OAuth / `CORS_ORIGINS` khác. Dùng chung một khoá:
```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -nocrypt -out key.pem        # 1 người tạo, gửi riêng cho nhóm, KHÔNG commit
openssl rsa -in key.pem -pubout -outform DER | base64 -w0              # → dán vào VITE_EXTENSION_KEY trong .env.local
openssl rsa -in key.pem -pubout -outform DER | sha256sum | head -c32 | tr 0-9a-f a-p   # → Extension ID
```
