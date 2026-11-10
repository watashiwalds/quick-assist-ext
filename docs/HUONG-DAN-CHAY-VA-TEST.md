# Hướng dẫn chạy và kiểm thử QuickAssist (P0)

Các lệnh viết cho **Windows PowerShell**. Lệnh cho bash (Git Bash/Linux/macOS) nằm trong ngoặc *bash:* khi cú pháp khác. Tất cả chạy từ thư mục gốc repo `quick-assist-ext` trừ khi ghi khác.

## 0. Chuẩn bị (một lần)

| Công cụ | Phiên bản | Kiểm tra |
|---|---|---|
| Docker Desktop | mới | `docker compose version` |
| Python | 3.11+ (khuyên 3.12) | `python --version` |
| Node.js | 20+ (khuyên 22) | `node --version` |
| Chrome | mới | — |

## A. Chạy lên và dùng thử (tự kiểm tra bằng tay)

Mục đích: lấy code `dev` về, chạy thật trên Chrome và tự bấm thử các tính năng. **Không cần tài khoản Google, không tốn tiền AI** (dùng đăng nhập thử + AI mock).

### Cách nhanh: bấm đúp `chay-thu.bat` (ở thư mục gốc repo)
Script tự làm A1 + A2: bật Docker Desktop nếu chưa chạy, tạo `infra\.env`, dựng DB + API + worker, chờ API sẵn sàng, kiểm tra khoá Gemini (nếu có), build extension bản kiểm thử, copy sẵn đường dẫn `dist-e2e` vào clipboard. Sau đó bạn chỉ làm bước nạp extension (A2 mục 1–2) và đăng nhập (A3).

Muốn dùng AI thật (Gemini/Gemma 4): tạo file `infra\gemini.key` chứa đúng 1 dòng là khoá (file đã nằm trong `.gitignore`). Script tự gọi thử; khoá lỗi thì tự quay về AI giả lập và báo lý do.

### A1. Lấy code và bật backend
```powershell
git checkout dev
git pull origin dev
copy infra\.env.example infra\.env                     # chỉ lần đầu
docker compose -f infra/docker-compose.yml up -d --build
curl http://localhost:8000/api/v1/health/ready         # phải thấy {"status":"ok","db":"ok"}
```
Lệnh `up` dựng DB, tự chạy migration, bật API (cổng 8000) và worker. Xem log nếu có lỗi: `docker compose -f infra/docker-compose.yml logs -f api worker`.

### A2. Build extension bản dùng thử và nạp vào Chrome
```powershell
cd apps/extension
npm ci
npm run build:e2e        # tạo thư mục dist-e2e/ (bản có nút đăng nhập thử, trỏ tới localhost:8000)
```
1. Chrome → `chrome://extensions` → bật **Developer mode** (góc phải trên).
2. **Load unpacked** → chọn thư mục `apps\extension\dist-e2e`.
3. Ghim biểu tượng QuickAssist lên thanh công cụ (biểu tượng mảnh ghép → ghim).

> Mỗi lần sửa code extension: chạy lại `npm run build:e2e` rồi bấm nút ↻ (Reload) của QuickAssist trong `chrome://extensions`.

### A3. Đăng nhập thử (không cần Google)
Bấm biểu tượng QuickAssist → **Mở thư viện ghi chú** → bấm **Đăng nhập thử (bản kiểm thử)** → thấy các tab **Thư viện · Tìm kiếm · Hỏi AI · Cài đặt**.
Nút này chỉ có trong bản `build:e2e`; bản phát hành (`npm run build`) không có (`npm run check:bundle` chặn nếu lọt).

Muốn thử người dùng thứ hai (kiểm tra không thấy dữ liệu của nhau): đăng xuất trong **Cài đặt**, mở Console của side panel (chuột phải → Inspect) và chạy:
```js
await chrome.runtime.sendMessage({ channel: 'qa-rpc', type: 'e2e/devLogin', payload: { email: 'nguoi-thu-2@quickassist.local' } })
```
rồi tải lại panel.

### A4. Kịch bản dùng thử — đánh dấu ✅/❌

Mở một bài báo tiếng Việt bất kỳ (VD vnexpress.net, tuoitre.vn) để làm dữ liệu.

| # | Thao tác | Kết quả đúng |
|---|---|---|
| 1 | Bôi đen một đoạn → **Alt+Shift+N** | Góc trang hiện toast đếm ngược 5s có nút "Hoàn tác (Alt+Shift+Z)", hết giờ báo "Đã lưu ghi chú ✓" |
| 2 | Bôi đen đoạn khác → chuột phải → **Ghi chú văn bản này** | Như trên |
| 3 | Lưu đoạn thứ ba rồi bấm **Hoàn tác** (hoặc Alt+Shift+Z) trước khi hết 5s | Ghi chú không xuất hiện trong Thư viện |
| 4 | Mở side panel → **Thư viện** | Thấy các ghi chú vừa lưu kèm link trang nguồn; sau vài giây chuyển trạng thái sẵn sàng (đã index) |
| 5 | Thư viện → tạo **Thư mục** mới, chuyển 1 ghi chú vào đó, đổi tên, lọc theo thư mục | Hoạt động đúng, không lỗi |
| 6 | Chuột phải trang → **Ghi chú vào thư mục** → chọn thư mục vừa tạo | Ghi chú nằm đúng thư mục |
| 7 | Mở 1 ghi chú → sửa nội dung → lưu | Báo "Đã lưu — đang cập nhật chỉ mục tìm kiếm" |
| 8 | Tab **Tìm kiếm** → gõ câu hỏi liên quan nội dung đã lưu, thử cả **có dấu** và **không dấu** | Ra đúng ghi chú, có trích nguồn; bấm vào mở được ghi chú |
| 9 | Tìm một thứ hoàn toàn không liên quan | Báo không tìm thấy, không lỗi |
| 10 | Mở ghi chú → **Tóm tắt bằng AI** | Hiện bản tóm tắt (AI mock: nội dung mẫu, không phải tóm tắt thật) |
| 11 | Bôi đen đoạn văn → chuột phải → **Tóm tắt đoạn văn bản này** | Side panel hiện tab **Tóm tắt** với kết quả; lưu được kèm tóm tắt |
| 12 | **Cài đặt** → xem hạn mức AI, đổi thư mục mặc định → lưu nhanh 1 đoạn | Hạn mức giảm sau khi tóm tắt; ghi chú mới vào thư mục mặc định đã chọn |
| 13 | **Offline**: `docker compose -f infra/docker-compose.yml stop api` → mở lại panel → lưu nhanh 1 đoạn | Thư viện vẫn hiện từ bộ nhớ đệm; ghi chú chờ gửi, **không mất** |
| 14 | `docker compose -f infra/docker-compose.yml start api`, đợi ~1 phút hoặc mở lại panel | Ghi chú ở bước 13 tự gửi lên, **không bị trùng** |
| 15 | Xoá 1 ghi chú, rồi chọn nhiều ghi chú → xoá | Biến mất khỏi Thư viện và kết quả tìm kiếm |
| 16 | Thử Alt+Shift+N trên trang `chrome://settings` | Không lưu gì (Chrome chặn tiện ích trên trang này) và extension không bị treo — quay lại trang thường vẫn lưu được |
| 17 | Bật dark mode của Windows/Chrome | Giao diện đọc rõ, nút đỏ (xoá) vẫn đủ tương phản |
| 18 | Dùng phím **Tab / Enter / Esc** đi qua các màn và hộp thoại | Điều khiển được hoàn toàn bằng bàn phím |
| 19 | Tab **Hỏi AI** → hỏi về nội dung đã lưu (VD "hầm xương bò bao lâu") | Câu trả lời hiện dần; có số nguồn [1], [2]… bấm vào mở đúng ghi chú; mục **Nguồn** liệt kê ghi chú và trang gốc |
| 20 | Hỏi tiếp một câu nối theo câu trước (VD "còn gia vị thì sao?") | AI hiểu ngữ cảnh câu trước (giữ 5 cặp hỏi–đáp gần nhất) |
| 21 | Hỏi một câu dài rồi bấm **Dừng** giữa chừng | Ngừng ngay, giữ phần đã hiện kèm "(đã dừng)"; hạn mức chỉ trừ phần đã sinh |
| 22 | Hỏi điều không có trong ghi chú (VD "thời tiết sao hoả") | Báo không tìm thấy ghi chú liên quan, không bịa |
| 23 | Hỏi xong → chuyển sang tab khác rồi quay lại; bấm **Cuộc trò chuyện mới** | Hội thoại vẫn còn khi quay lại; nút xoá làm trống hội thoại |
| 24 | (Cuối cùng) **Cài đặt → Xoá tài khoản…** → làm đủ 2 bước | Đăng xuất, toàn bộ ghi chú bị xoá cả trên server lẫn máy |

Gặp lỗi: chụp màn hình + mở DevTools Console của side panel (và `chrome://extensions` → QuickAssist → **service worker** → Console) để xem lỗi, kèm log `docker compose ... logs api worker`. Mỗi lỗi API có `requestId` — ghi lại để tra log.

### A5. Dùng thử với AI thật — Gemini (Gemma 4 31B)
Sửa `infra/.env` (file này đã nằm trong `.gitignore`, **không commit khoá**):
```
AI_PROVIDER=gemini
GEMINI_API_KEY=<khoá Gemini>
GEMINI_CHAT_MODEL=gemma-4-31b-it
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```
Kiểm tra khoá trước (in ra ✓/✗ cho embedding và chat, không in khoá):
```powershell
cd apps/api
.venv\Scripts\activate
python scripts/check_ai.py --env ../../infra/.env --try-both
```
Nếu chỉ dòng **Vertex express** thành công → thêm `GEMINI_BASE_URL=https://aiplatform.googleapis.com/v1/publishers/google/models` vào `infra/.env`.

Rồi khởi động lại backend. Dữ liệu thử đã index bằng AI mock không dùng chung được với embedding Gemini → xoá dữ liệu cũ cho sạch:
```powershell
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d --build
```
Ghi chú mới sẽ được index bằng `gemini-embedding-001` (1536 chiều) và tóm tắt bằng Gemma 4 31B. Muốn quay về miễn phí: `AI_PROVIDER=mock`.

### A6. Dùng thử bản phát hành với Google thật (tuỳ chọn)
Cần OAuth client trên Google Cloud Console — làm theo mục 3 bên dưới (`npm run build`, nạp `dist/`, khai báo Extension ID).

### A7. Tắt
```powershell
docker compose -f infra/docker-compose.yml down        # thêm -v để xoá sạch dữ liệu thử
```

---

## B. Chạy test tự động nhanh sau khi lấy code từ `dev` về

Chạy lần lượt từ thư mục gốc repo. Lần đầu làm đủ các bước; những lần `pull` sau chỉ cần lặp lại bước 1, 3 và 4.

**1. Lấy code mới nhất**
```powershell
git checkout dev
git pull origin dev
```

**2. Chuẩn bị (lần đầu)**
```powershell
copy infra\.env.example infra\.env
docker compose -f infra/docker-compose.yml up -d db
docker compose -f infra/docker-compose.yml exec db createdb -U postgres quickassist_test

cd apps/api
python -m venv .venv
cd ../..
```

**3. Dựng backend (API + worker + DB, tự migrate)**
```powershell
docker compose -f infra/docker-compose.yml up -d --build
curl http://localhost:8000/api/v1/health/ready      # → {"status":"ok","db":"ok"}
```

**4. Chạy test**
```powershell
# Backend: unit + kiến trúc + integration  → 168 passed
cd apps/api
.venv\Scripts\activate
pip install -e ".[dev]"
$env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test"
pytest
python scripts/smoke_test.py --base http://localhost:8000 --dev-login   # → 11/11 OK
deactivate

# Extension: unit + build + E2E  → 80 passed, 28 passed
cd ../extension
npm ci
npm test
npm run build
npm run check:bundle
npx playwright install chromium      # chỉ lần đầu
npm run test:e2e
cd ../..
```

**5. Tắt khi xong**: `docker compose -f infra/docker-compose.yml down`

> Có test đỏ? Xem bảng *Lỗi thường gặp* (mục 6). Các mục bên dưới giải thích chi tiết từng phần.

---

## 1. Chạy nhanh toàn bộ backend bằng Docker (cách dễ nhất)

```powershell
copy infra\.env.example infra\.env          # bash: cp infra/.env.example infra/.env
docker compose -f infra/docker-compose.yml up --build
```
Lệnh này dựng 4 service: `db` (PostgreSQL 16 + pgvector, cổng 5432), `migrate` (chạy `alembic upgrade head` rồi thoát), `api` (cổng 8000), `worker` (xử lý job index/tóm tắt).

Kiểm tra:
- Mở http://localhost:8000/docs → thấy Swagger.
- `curl http://localhost:8000/api/v1/health/ready` → `{"status":"ok"...}` (kiểm cả kết nối DB).

Mặc định `AI_PROVIDER=mock` (không gọi OpenAI, không tốn tiền) và `ENABLE_DEV_LOGIN=true` (đăng nhập thử không cần Google).
Muốn dùng OpenAI thật: sửa `infra/.env` → `AI_PROVIDER=openai`, `OPENAI_API_KEY=sk-...`, rồi `up` lại.

Dừng: `Ctrl+C`, hoặc `docker compose -f infra/docker-compose.yml down` (thêm `-v` để xoá cả dữ liệu DB).

---

## 2. Chạy backend không Docker (khi sửa code Python)

Chỉ dùng Docker cho database:
```powershell
docker compose -f infra/docker-compose.yml up -d db
```

Cài môi trường Python:
```powershell
cd apps/api
python -m venv .venv
.venv\Scripts\activate                       # bash: source .venv/bin/activate
pip install -e ".[dev]"
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist"
$env:APP_ENV="dev"; $env:ENABLE_DEV_LOGIN="true"; $env:AI_PROVIDER="mock"
# bash: export DATABASE_URL=... APP_ENV=dev ENABLE_DEV_LOGIN=true AI_PROVIDER=mock
alembic upgrade head
```

Chạy 2 terminal (mỗi terminal đều phải activate venv và đặt biến môi trường như trên):
```powershell
uvicorn quickassist.main:app --reload --port 8000   # terminal 1: API
python -m quickassist.worker                        # terminal 2: worker
```
> Không chạy worker thì ghi chú sẽ kẹt ở trạng thái `PENDING` (chưa index, không tìm thấy).

---

## 3. Chạy extension trên Chrome

```powershell
cd apps/extension
copy .env.example .env.local     # điền VITE_GOOGLE_CLIENT_ID (OAuth client loại Web application)
npm install
npm run build                    # tạo thư mục dist/  (hoặc: npm run dev để tự build lại khi sửa)
```

Nạp vào Chrome:
1. Mở `chrome://extensions` → bật **Developer mode**.
2. **Load unpacked** → chọn `apps/extension/dist`.
3. Ghi lại **Extension ID**, rồi:
   - Thêm `chrome-extension://<ID>` vào `CORS_ORIGINS` và `https://<ID>.chromiumapp.org/` vào `OAUTH_ALLOWED_REDIRECT_URIS` trong `infra/.env` (hoặc biến môi trường backend), khởi động lại API.
   - Trên Google Cloud Console, thêm Authorized redirect URI `https://<ID>.chromiumapp.org/`.

Thử tay các luồng chính:

| Luồng | Cách làm | Kết quả đúng |
|---|---|---|
| Lưu nhanh | Bôi đen chữ trên trang web → **Alt+Shift+N** (hoặc chuột phải → lưu ghi chú) | Toast "Đã lưu", có nút hoàn tác |
| Hoàn tác | Bấm Hoàn tác trên toast hoặc **Alt+Shift+Z** | Ghi chú bị huỷ |
| Thư viện | Mở side panel → tab Ghi chú | Thấy ghi chú, trạng thái chuyển sang READY sau vài giây |
| Tìm kiếm | Tab Tìm kiếm, gõ câu hỏi có hoặc không dấu | Ra kết quả kèm nguồn |
| Tóm tắt | Mở ghi chú → Tóm tắt, hoặc tóm tắt vùng chọn | Hiện bản tóm tắt (mock: văn bản mẫu) |
| Offline | Tắt backend → mở panel → lưu ghi chú → bật lại backend | Panel vẫn hiện từ cache; ghi chú tự gửi lại, không bị trùng |

> Phím tắt dùng **Alt+Shift**, không phải Ctrl+Alt (Chrome từ chối Ctrl+Alt nên extension không nạp được). Có thể đổi tại `chrome://extensions/shortcuts`.

---

## 4. Kiểm thử tự động

### 4.1 Backend — unit + kiến trúc (không cần DB)
```powershell
cd apps/api
.venv\Scripts\activate
pytest                     # test integration tự skip nếu chưa đặt TEST_DATABASE_URL
pytest tests/architecture  # chỉ luật tầng L1–L7
```

### 4.2 Backend — integration (cần PostgreSQL)
Tạo DB test riêng một lần (đừng dùng DB `quickassist` vì test sẽ xoá sạch schema):
```powershell
docker compose -f infra/docker-compose.yml exec db createdb -U postgres quickassist_test
```
Chạy:
```powershell
cd apps/api
$env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test"
pytest -v
```
Kết quả mong đợi: **168 passed**.

### 4.3 Đánh giá chất lượng tìm kiếm
```powershell
cd apps/api
$env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test"
python -m tests.eval.run_eval
```
Kết quả ghi vào `apps/api/tests/eval/results/`; xem phân tích ở `docs/ai/eval-report.md`.

### 4.4 Extension — unit + kiến trúc
```powershell
cd apps/extension
npm test             # mong đợi: 80 passed
npm run typecheck
```

### 4.5 Extension — E2E (Playwright, chạy extension thật trên Chromium)
Cần backend đang chạy với `ENABLE_DEV_LOGIN=true`, `AI_PROVIDER=mock` và **worker** (mục 1 hoặc 2).
```powershell
cd apps/extension
npx playwright install chromium     # lần đầu
npm run test:e2e                    # build bản E2E (dist-e2e/) rồi chạy
$env:E2E_HEADED="1"; npm run test:e2e   # xem trình duyệt chạy
npx playwright show-report          # xem báo cáo HTML
```
Mong đợi: **28 passed**. Biến tuỳ chọn: `E2E_API_BASE_URL` (mặc định `http://localhost:8000/api/v1`), `E2E_DATABASE_URL` (để test chỉnh quota). Chi tiết ở `apps/extension/e2e/README.md`.

### 4.6 Kiểm tra bản phát hành không lọt code test
```powershell
cd apps/extension
npm run build
npm run check:bundle     # báo lỗi nếu dist/ chứa dev-login hoặc hook E2E
npm run package          # đóng gói zip vào release/
```

### 4.7 Smoke test toàn hệ thống
Khi backend và worker đang chạy:
```powershell
cd apps/api
python scripts/smoke_test.py --base http://localhost:8000 --dev-login
```
Mong đợi: **11/11 bước OK** (health, header bảo mật, 401, tạo ghi chú idempotent → READY → tìm thấy → tóm tắt → xoá). Bản deploy thật: xem `docs/deploy/runbook.md`.

---

## 5. Thứ tự kiểm tra trước khi commit

```powershell
cd apps/api;       pytest                      # 4.1 (và 4.2 nếu có DB)
cd ../extension;   npm test; npm run typecheck; npm run build; npm run check:bundle
```
E2E (4.5) và smoke test (4.7) chạy khi sửa luồng chính hoặc trước demo.

## 6. Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Chrome báo không nạp được extension vì shortcut | Bản manifest cũ dùng Ctrl+Alt | Build lại từ code P0 (đã đổi sang Alt+Shift) |
| Ghi chú mãi `PENDING`, tìm không ra | Worker không chạy | Chạy `python -m quickassist.worker` hoặc service `worker` |
| Lỗi CORS hoặc OAuth `redirect_uri_mismatch` | Chưa khai báo Extension ID | Làm bước 3 trong mục 3 |
| `pytest` báo integration bị skip | Chưa đặt `TEST_DATABASE_URL` | Mục 4.2 |
| `database "quickassist_test" does not exist` | Chưa tạo DB test | Lệnh `createdb` ở mục 4.2 |
| `429 RATE_LIMITED` | Gọi API quá nhanh (ADR-0010) | Chờ theo header `Retry-After` |
| `port 5432 is already allocated` | Máy đang có PostgreSQL khác | Tắt PostgreSQL cục bộ hoặc đổi cổng trong `docker-compose.yml` |
| PowerShell không cho chạy `.venv\Scripts\activate` | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
