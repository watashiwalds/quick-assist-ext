# E2E extension (N07 · C05 · R05 · SUM-03 · A08 · H05)

Chạy extension **thật** trên Chromium (Playwright) với backend thật (PostgreSQL + pgvector, worker, AI mock).

| File | Task | Nội dung |
|---|---|---|
| `n07-quick-note.spec.ts` | N07, C04 | lưu nhanh → toast → server → READY; hoàn tác; mất mạng gửi lại không trùng; hết quota (SKIPPED); textarea; trang `chrome://`; chọn thư mục |
| `c05-library.spec.ts` | C05 | cache-first + offline; sửa có 409; xoá 1/nhiều; quản lý thư mục; tombstone |
| `r05-search.spec.ts` | R05 | 4 câu hỏi mẫu (có/không dấu); nguồn + mở ghi chú; lọc thư mục; không lộ dữ liệu người khác; hết quota |
| `sum-a08.spec.ts` | SUM-03, A08 | tóm tắt ghi chú & vùng chọn; cài đặt; xoá tài khoản 2 bước xoá dữ liệu server + máy |
| `h05-a11y.spec.ts` | H05 | axe-core WCAG 2.1 AA mọi màn + popup + hộp thoại; điều hướng bàn phím |

## Chạy
```bash
# 1) Backend (terminal 1, 2) — bật dev-login, AI mock
cd apps/api
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist APP_ENV=dev ENABLE_DEV_LOGIN=true AI_PROVIDER=mock
alembic upgrade head && uvicorn quickassist.main:app --port 8000
python -m quickassist.worker
# 2) E2E (terminal 3)
cd apps/extension
npx playwright install chromium   # lần đầu
npm run test:e2e                  # build bản E2E (dist-e2e/) rồi chạy; E2E_HEADED=1 để xem trình duyệt
```
Biến: `E2E_API_BASE_URL` (mặc định `http://localhost:8000/api/v1`), `E2E_DATABASE_URL` (để chỉnh quota trong test).

## Bản build E2E khác bản phát hành ở đâu?
`VITE_E2E=true` thêm: RPC `e2e/devLogin` (đăng nhập không cần Google), hook `globalThis.__qaE2E` trong service worker (thay cho thao tác menu chuột phải/phím tắt mà Playwright không bấm được), quyền vào `http://127.0.0.1/*` (trang thử). **Bản phát hành không chứa các phần này** — `npm run check:bundle` (CI) chặn nếu lọt.

Kết quả lần chạy gần nhất: [`docs/qa/reports/`](../../../docs/qa/reports/).
