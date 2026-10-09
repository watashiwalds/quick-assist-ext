# Hướng dẫn chạy và kiểm thử QuickAssist (P0)

Các lệnh viết cho **Windows PowerShell**. Lệnh cho bash (Git Bash/Linux/macOS) nằm trong ngoặc *bash:* khi cú pháp khác. Tất cả chạy từ thư mục gốc repo `quick-assist-ext` trừ khi ghi khác.

> **Branch áp dụng:** bản hướng dẫn này đang được rà soát trên `quang-test-dev`. Trước khi chạy, kiểm tra bằng `git branch --show-current`. Không chạy `git checkout dev` nếu bạn cần kiểm tra code trên branch hiện tại.

## Cách dùng hướng dẫn này trên Windows

Hướng dẫn dùng **PowerShell**. Không dán lệnh vào cửa sổ cài Node.js, Chrome DevTools (trừ đoạn JavaScript được ghi rõ ở A3), hay Docker Desktop.

1. Cài Node.js xong, đóng Command Prompt/PowerShell cũ để Windows nạp lại `PATH`.
2. Mở **Windows PowerShell** mới: nhấn `Windows`, gõ `PowerShell`, rồi mở ứng dụng. Không cần quyền Administrator.
3. Đi tới thư mục project và giữ cửa sổ này mở trong suốt phần đang làm:
   ```powershell
   cd D:\quick-assist-ext
   Get-Location                 # phải hiện Path là D:\quick-assist-ext
   ```
   Nếu dùng **Command Prompt** thay vì PowerShell, lệnh tương đương là `cd /d D:\quick-assist-ext`. Các lệnh đặt biến dạng `$env:...` trong tài liệu này chỉ chạy trong PowerShell.
4. Lệnh có `cd apps/...` sẽ đổi thư mục của chính cửa sổ terminal đó. Muốn quay lại gốc bất cứ lúc nào, chạy `cd D:\quick-assist-ext`.
5. Khi hướng dẫn ghi **Terminal 1** và **Terminal 2**, mở hai cửa sổ PowerShell riêng; mỗi cửa sổ cần tự `cd` vào đúng thư mục và tự đặt các biến môi trường được ghi trong block của nó.

### Nên bắt đầu từ đâu?

Nếu mới cài công cụ và chỉ muốn dùng thử extension, làm tuần tự **mục A1 → A2 → A3 → A4**. Không cần Gemini, Google OAuth thật, Python virtualenv hay E2E ở lần đầu.

| Việc | Chạy ở đâu |
|---|---|
| `docker`, `git`, `python`, `npm` | PowerShell tại `D:\quick-assist-ext`, trừ khi block có `cd` khác |
| Sửa `infra\.env` | Mở bằng Notepad/VS Code; không dán các dòng `KEY=VALUE` vào terminal |
| Load extension, lấy Extension ID | Chrome tại `chrome://extensions` |
| Lệnh JavaScript đăng nhập thử | DevTools Console của side panel, chỉ ở bước A3 |

## 0. Chuẩn bị (một lần)

| Công cụ | Phiên bản | Kiểm tra |
|---|---|---|
| Docker Desktop | mới | `docker compose version` |
| Python | **3.12** để chạy B4 trên Windows | `py -3.12 --version` |
| Node.js | 20+ (khuyên 22) | `node --version` |
| Chrome | mới | — |

Sau khi cài Node.js, mở PowerShell **mới** và chạy cả hai lệnh sau. Chỉ tiếp tục khi chúng in ra số phiên bản:

```powershell
node --version
npm --version
```

Mở Docker Desktop trước khi chạy phần A hoặc B; đợi biểu tượng Docker báo đang chạy, rồi kiểm tra:

```powershell
docker compose version
```

## A. Chạy lên và dùng thử (tự kiểm tra bằng tay)

Mục đích: chạy thật trên Chrome và tự bấm thử các tính năng của branch hiện tại. **Không cần tài khoản Google, không tốn tiền AI** (dùng đăng nhập thử + AI mock).

### A1. Lấy code và bật backend
Mở PowerShell tại `D:\quick-assist-ext`, rồi chạy lần lượt từng lệnh. Nếu `git status --short` có dòng nào, **không chạy `git pull`**; điều đó nghĩa là có thay đổi cục bộ cần giữ hoặc commit trước.

```powershell
# Xác nhận đang ở đúng branch cần thử (hiện tại: quang-test-dev).
git branch --show-current
# Phải không in gì trước khi pull. Có dòng xuất hiện thì bỏ qua lệnh pull.
git status --short
# Chỉ chạy dòng này nếu git status --short không in gì:
git pull --ff-only
if (-not (Test-Path infra\.env)) { Copy-Item infra\.env.example infra\.env }
docker compose -f infra/docker-compose.yml up -d --build
curl http://localhost:8000/api/v1/health/ready         # phải thấy {"status":"ok","db":"ok"}
```
Lệnh `up` dựng DB, tự chạy migration, bật API (cổng 8000) và worker. Lần đầu có thể mất vài phút để Docker tải image/build. Chỉ qua A2 khi lệnh `curl` trả `"status":"ok"` và `"db":"ok"`. Xem log nếu có lỗi: `docker compose -f infra/docker-compose.yml logs -f api worker`; thoát xem log bằng `Ctrl+C` (không dừng service).

### A2. Build extension bản dùng thử và nạp vào Chrome
Tiếp tục trong cùng PowerShell. `cd apps/extension` sẽ chuyển terminal vào thư mục extension.

```powershell
cd apps/extension
npm ci
npm run build:e2e        # tạo thư mục dist-e2e/ (có RPC đăng nhập thử, trỏ tới localhost:8000)
```
`npm ci` có thể mất vài phút ở lần đầu. Chỉ tiếp tục khi lệnh build kết thúc với dòng có `dist-e2e` và không có lỗi.

1. Chrome → `chrome://extensions` → bật **Developer mode** (góc phải trên).
2. **Load unpacked** → chọn thư mục `apps\extension\dist-e2e`.
3. Ghim biểu tượng QuickAssist lên thanh công cụ (biểu tượng mảnh ghép → ghim).
4. Sao chép **Extension ID** Chrome hiển thị, rồi sửa `infra\.env`:
   ```env
   CORS_ORIGINS=chrome-extension://<EXTENSION_ID>
   ```
   Khởi động lại API để áp dụng CORS trước khi đăng nhập thử:
   ```powershell
   cd ..\..
   docker compose -f infra/docker-compose.yml up -d --build api
   ```
   Sau lệnh này, terminal đã quay lại `D:\quick-assist-ext`.

> Mỗi lần sửa code extension: chạy lại `npm run build:e2e` rồi bấm nút ↻ (Reload) của QuickAssist trong `chrome://extensions`.
> Nếu Extension ID thay đổi, cập nhật `CORS_ORIGINS` rồi khởi động lại API. Dùng `VITE_EXTENSION_KEY` trong `apps/extension/.env.local` nếu cần ID cố định.

### A3. Đăng nhập thử (không cần Google)
1. Bấm biểu tượng QuickAssist → **Mở thư viện ghi chú** (side panel mở bên phải). Màn hình hiện nút "Đăng nhập bằng Google" — bỏ qua nút này.
2. Chuột phải vào side panel → **Inspect** → tab **Console**, dán rồi Enter:
   ```js
   await chrome.runtime.sendMessage({ channel: 'qa-rpc', type: 'e2e/devLogin', payload: { email: 'demo@quickassist.local' } })
   ```
   Kết quả có `ok: true` là được. Nếu thấy `NETWORK_ERROR`, kiểm tra lại Extension ID trong `CORS_ORIGINS`, rồi restart API như A2. Nếu thấy `NO_BACKGROUND`, quay lại `chrome://extensions` và bấm Reload extension.
3. Đóng DevTools, chuột phải side panel → **Reload frame** (hoặc đóng mở lại panel) → thấy các tab **Thư viện · Tìm kiếm · Cài đặt**.

Muốn thử người dùng thứ hai (kiểm tra không thấy dữ liệu của nhau): đăng xuất trong **Cài đặt**, rồi đăng nhập thử với email khác.

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
| 19 | (Cuối cùng) **Cài đặt → Xoá tài khoản…** → làm đủ 2 bước | Đăng xuất, toàn bộ ghi chú bị xoá cả trên server lẫn máy |

Gặp lỗi: chụp màn hình + mở DevTools Console của side panel (và `chrome://extensions` → QuickAssist → **service worker** → Console) để xem lỗi, kèm log `docker compose ... logs api worker`. Mỗi lỗi API có `requestId` — ghi lại để tra log.

### A5. Dùng thử với AI thật — Gemini (Gemma 4 31B)
Chỉ làm mục này **sau khi A1 đến A4 đã chạy ổn với `AI_PROVIDER=mock`**. Gemini gọi dịch vụ bên ngoài, có giới hạn sử dụng/quota theo tài khoản Google; không dán API key vào chat, ảnh chụp màn hình, source code hay Git.

#### A5.1 Lấy Gemini API key

1. Đăng nhập tài khoản Google tại [Google AI Studio](https://aistudio.google.com/).
2. Mở trang **API keys** hoặc chọn **Get API key**.
3. Chọn **Create API key**, chọn/tạo project theo màn hình Google, rồi sao chép key vừa tạo.
4. Nếu AI Studio hỏi quyền/billing, đọc kỹ quota và điều khoản trước khi tiếp tục. API key thuộc tài khoản Google của bạn.

> Key tạo trong AI Studio nên được giới hạn cho Gemini API. Google hiện quản lý key và project tại AI Studio; xem [hướng dẫn chính thức về Gemini API key](https://ai.google.dev/gemini-api/docs/api-key).

#### A5.2 Cấu hình QuickAssist

Trong PowerShell, mở file cấu hình. Đây là file cục bộ đã được `.gitignore`; vẫn không được gửi hoặc commit file này.

```powershell
notepad D:\quick-assist-ext\infra\.env
```

Tìm phần `# --- Gemini API ... ---`, thay/điền các dòng sau. Giữ nguyên các dòng khác, đặc biệt `CORS_ORIGINS` đã cấu hình cho extension.

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=DAN_API_KEY_O_DAY
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/models
GEMINI_CHAT_MODEL=gemma-4-31b-it
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_THINKING_LEVEL=minimal
```

Ví dụ: chỉ thay `DAN_API_KEY_O_DAY` bằng key thật; không thêm dấu nháy và không để khoảng trắng ở đầu/cuối key. Lưu file bằng `Ctrl+S`, rồi đóng Notepad.

#### A5.3 Kiểm tra key và model trước khi thay dữ liệu demo

Chạy lệnh này từ thư mục gốc project. Nó tạo một container tạm, kiểm tra cả embedding lẫn chat, không in API key và không sửa database:

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml run --rm --no-deps api python scripts/check_ai.py --try-both
```

Kết quả đạt là cả hai dòng `✓ embedding` và `✓ chat` xuất hiện ở ít nhất một endpoint.

- Nếu **AI Studio** đạt: giữ `GEMINI_BASE_URL` như ở A5.2.
- Nếu chỉ **Vertex express** đạt: mở lại `infra\.env` và đổi thành:
  ```env
  GEMINI_BASE_URL=https://aiplatform.googleapis.com/v1/publishers/google/models
  ```
  Sau đó chạy lại lệnh kiểm tra.
- Nếu cả hai đều lỗi: **không xoá database**. Kiểm tra thông báo `http 400/403` (key, project hoặc quyền) hay `http 404` (model), sau đó sửa và chạy lại. Khi cần quay về demo miễn phí, đặt `AI_PROVIDER=mock`.

#### A5.4 Khởi động lại bằng Gemini

Embedding từ AI mock không dùng chung với embedding Gemini. Cách ít nhầm nhất khi chỉ có dữ liệu demo là xoá dữ liệu thử, để mọi ghi chú sau đó đều được index bằng Gemini:

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d --build
curl http://localhost:8000/api/v1/health/ready
```

> `down -v` xoá **toàn bộ** volume PostgreSQL của môi trường Docker này: tài khoản demo, ghi chú, folder, quota và index. Không chạy lệnh này nếu có dữ liệu cần giữ. Nếu chọn giữ dữ liệu cũ, các note đã index bằng mock sẽ cần index lại trước khi search đáng tin cậy với Gemini.

Không cần build lại extension vì thay đổi này chỉ nằm ở backend. Mở Chrome, đăng nhập thử như A3, tạo một note mới, chờ trạng thái **Sẵn sàng tìm kiếm**, rồi thử **Tóm tắt bằng AI**. Lúc này nội dung tóm tắt không còn là kết quả mock.

#### A5.5 Quay về AI mock

Mở `infra\.env`, đổi lại:

```env
AI_PROVIDER=mock
```

Sau đó khởi động lại API và worker:

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml up -d --build --force-recreate api worker
```

Nếu đã tạo/search note bằng Gemini, nên dùng một database demo mới (`down -v` rồi `up`) trước khi đánh giá search với mock, vì hai loại embedding không cùng không gian vector.

### A6. Dùng thử bản phát hành với Google thật (tuỳ chọn)
Cần OAuth client trên Google Cloud Console — làm theo mục 3 bên dưới (`npm run build`, nạp `dist/`, khai báo Extension ID).

### A7. Tắt
```powershell
docker compose -f infra/docker-compose.yml down        # thêm -v để xoá sạch dữ liệu thử
```

---

## B. Chạy test tự động

Mục này dành cho kiểm thử tự động. Nếu vừa hoàn thành phần A và `curl http://localhost:8000/api/v1/health/ready` đang trả `200 OK`, Docker đã chạy rồi: **không chạy lại `up --build`**. Chỉ chuẩn bị database test ở bước B2, rồi đi thẳng tới B4.

Mỗi block bên dưới đều bắt đầu bằng `cd D:\quick-assist-ext` hoặc ghi rõ thư mục cần đứng. Đừng chạy lệnh Docker khi đang ở `apps\api` hay `apps\extension`, vì đường dẫn `infra\docker-compose.yml` là tương đối từ thư mục gốc.

### B1. Xác nhận branch và trạng thái

Mở PowerShell mới hoặc quay về thư mục gốc:

```powershell
cd D:\quick-assist-ext
git branch --show-current       # mong đợi: quang-test-dev
git status --short
```

Chỉ khi `git status --short` không in gì và bạn thật sự muốn cập nhật branch hiện tại mới chạy `git pull --ff-only`. Nếu thấy các file tài liệu do bạn/mình vừa sửa, bỏ qua `git pull`.

### B2. Chuẩn bị một lần cho backend test

Backend integration test dùng database riêng `quickassist_test`; không dùng chung database demo `quickassist`.

```powershell
cd D:\quick-assist-ext
if (-not (Test-Path infra\.env)) { Copy-Item infra\.env.example infra\.env }
docker compose -f infra/docker-compose.yml up -d db
docker compose -f infra/docker-compose.yml exec db createdb -U postgres quickassist_test
```

Lệnh `createdb` chỉ chạy lần đầu. Nếu báo database `quickassist_test` đã tồn tại, đó không phải lỗi cần xử lý; bỏ qua và tiếp tục.

Tạo Python virtual environment một lần. **Dùng Python 3.12**, không dùng Python 3.14: ở Python 3.14, suite hiện có thể kẹt ở test Gemini streaming. Trước hết kiểm tra máy có Python 3.12:

```powershell
py -3.12 --version
```

Nếu `.venv` đã được tạo trước đó bằng Python 3.14, giữ nó nguyên và tạo virtualenv test 3.12 riêng tên `.venv312` như dưới đây. Không cần xoá gì:

```powershell
cd D:\quick-assist-ext\apps\api
if (-not (Test-Path .venv312)) { py -3.12 -m venv .venv312 }
```

### B3. Bật backend khi chưa chạy

Trước hết kiểm tra. Nếu lệnh sau trả `200 OK` với `"status":"ok"` và `"db":"ok"`, bỏ qua block khởi động bên dưới.

```powershell
cd D:\quick-assist-ext
curl http://localhost:8000/api/v1/health/ready
```

Chỉ khi API chưa chạy hoặc `curl` không kết nối được, mới chạy:

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml up -d
curl http://localhost:8000/api/v1/health/ready
```

Chỉ thêm cờ `--build` nếu vừa sửa Dockerfile, dependency Python hoặc muốn chủ động build lại image:

```powershell
docker compose -f infra/docker-compose.yml up -d --build
```

### B4. Chạy test backend

Lệnh dưới đây lưu toàn bộ output của pytest vào `docs\qa\reports` đồng thời vẫn in ra terminal. Giữ file log khi có test đỏ để đối chiếu; không gửi API key, token hoặc nội dung bí mật vào log/báo cáo.

```powershell
cd D:\quick-assist-ext\apps\api
.\.venv312\Scripts\python.exe -m pip install -e ".[dev]"
$env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
.\.venv312\Scripts\python.exe -m pytest 2>&1 | Tee-Object -FilePath "..\..\docs\qa\reports\pytest-$stamp.log"
```

Nếu pytest có dòng `FAILED` hoặc kết thúc bằng số test failed:

1. **Dừng ở đây**, không coi B4 là đạt và không cần chạy smoke test ngay.
2. Giữ file `docs\qa\reports\pytest-<thời-gian>.log` vừa tạo.
3. Ghi ngắn gọn vào `docs\qa\reports\TESTING.md`: tên test fail, lỗi chính, cách tái hiện và thời gian chạy. Không dán toàn bộ log nếu log chứa dữ liệu nhạy cảm.
4. B5 là bộ test extension độc lập; có thể chạy sau để biết frontend có lỗi riêng không, nhưng B5 không thay thế việc xử lý test backend đỏ.

Chỉ khi pytest kết thúc không có `FAILED` hay `ERROR`, chạy smoke test với backend đang chạy:

```powershell
.\.venv312\Scripts\python.exe scripts/smoke_test.py --base http://localhost:8000 --dev-login --timeout 90
```

`--timeout 90` cần thiết khi đang dùng Gemini thật vì một lượt tóm tắt có thể lâu hơn 20 giây. Với `AI_PROVIDER=mock`, vẫn có thể bỏ tham số này.

### B5. Chạy test extension

Đây là bộ test TypeScript/React của extension, khác với pytest ở B4. Chạy nó sau khi đã lưu và đánh giá kết quả B4.

```powershell
cd D:\quick-assist-ext\apps\extension
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
npm ci
npm test
npm run typecheck
npm run build
npm run check:bundle
```

E2E không chạy chung với database demo. Chỉ chạy `npm run test:e2e` sau khi làm đúng môi trường database riêng ở mục 4.5 bên dưới.

### B6. Tắt khi xong

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml down
```

> Có test đỏ? Xem bảng *Lỗi thường gặp* (mục 6). Các mục bên dưới giải thích chi tiết từng phần.

---

> ## Cách dùng mục 1–5 sau khi xong A và B
>
> Đây là phần tham khảo kỹ thuật chi tiết, không phải năm bước bắt buộc phải chạy nối tiếp. Đặc biệt, **mục 1 và mục 2 là hai cách thay thế nhau** để chạy backend: chọn một cách, không chạy cùng lúc.
>
> Với máy của bạn ở thời điểm hiện tại: Docker đang chạy, B4 đạt `180 passed`, B5 đạt `80 passed`. Vì vậy, không chạy lại mục 1, 2, 4.1, 4.2, 4.4 hoặc 5. Nếu muốn kiểm tra thêm, chỉ chọn **4.3** (đánh giá search), **4.5** (E2E thật) hoặc **4.6** (đóng gói release) theo nhu cầu.
>
> | Mục | Dùng khi nào | Bạn cần làm ngay? |
> |---|---|---|
> | 1 | Một ngày khác muốn bật lại bằng Docker | Không; backend đã chạy |
> | 2 | Muốn sửa/debug code Python ngoài Docker | Không; thay thế mục 1 |
> | 3 | Muốn nạp lại bản extension production `dist` | Chỉ làm khi cần thử OAuth thật |
> | 4 | Muốn chạy test nâng cao | Chọn tiểu mục cần thiết; xem thứ tự bên dưới |
> | 5 | Sắp tự `git commit` code đã sửa | Chỉ chạy ngay trước commit |

## 1. Chạy nhanh toàn bộ backend bằng Docker (cách dễ nhất)

Mở PowerShell mới rồi chạy tại thư mục gốc. **Không copy đè `infra\.env` nếu file này đã có**: nó chứa cấu hình Gemini/CORS của bạn.

```powershell
cd D:\quick-assist-ext
if (-not (Test-Path infra\.env)) { Copy-Item infra\.env.example infra\.env }
docker compose -f infra/docker-compose.yml up -d --build
curl http://localhost:8000/api/v1/health/ready
```
Lệnh này dựng 4 service: `db` (PostgreSQL 16 + pgvector, cổng 5432), `migrate` (chạy `alembic upgrade head` rồi thoát), `api` (cổng 8000), `worker` (xử lý job index/tóm tắt).

Kiểm tra:
- Mở http://localhost:8000/docs → thấy Swagger.
- `curl http://localhost:8000/api/v1/health/ready` → `{"status":"ok"...}` (kiểm cả kết nối DB).

Mặc định `AI_PROVIDER=mock` (không gọi OpenAI, không tốn tiền) và `ENABLE_DEV_LOGIN=true` (đăng nhập thử không cần Google).
Muốn dùng OpenAI thật: sửa `infra/.env` → `AI_PROVIDER=openai`, `OPENAI_API_KEY=sk-...`, rồi `up` lại.

Dừng các service: `docker compose -f infra/docker-compose.yml down`. **Không thêm `-v`** trừ khi thực sự muốn xoá toàn bộ dữ liệu PostgreSQL.

---

## 2. Chạy backend không Docker (lựa chọn thay thế mục 1, khi sửa code Python)

Không làm mục này khi API/worker Docker đang chạy, vì cả hai cùng dùng cổng `8000`. Chỉ database tiếp tục chạy trong Docker. Nếu muốn chuyển sang cách này, làm đúng thứ tự sau.

**Terminal 1 — chỉ giữ database Docker:**

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml stop api worker
docker compose -f infra/docker-compose.yml up -d db
```

**Terminal 2 — API cục bộ:**

Phần test trên Windows đã xác nhận Python 3.12 ổn định. Dùng `.venv312` nếu đã tạo ở phần B; nếu chưa có thì tạo nó.

```powershell
cd D:\quick-assist-ext\apps\api
if (-not (Test-Path .venv312)) { py -3.12 -m venv .venv312 }
.\.venv312\Scripts\python.exe -m pip install -e ".[dev]"
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist"
$env:APP_ENV="dev"
$env:ENABLE_DEV_LOGIN="true"
$env:AI_PROVIDER="mock"   # hoặc gemini nếu infra\.env không được dùng ở chế độ này
.\.venv312\Scripts\python.exe -m alembic upgrade head
.\.venv312\Scripts\python.exe -m uvicorn quickassist.main:app --reload --port 8000
```

**Terminal 3 — worker cục bộ:** mở PowerShell khác và chạy:

```powershell
cd D:\quick-assist-ext\apps\api
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist"
$env:APP_ENV="dev"
$env:ENABLE_DEV_LOGIN="true"
$env:AI_PROVIDER="mock"
.\.venv312\Scripts\python.exe -m quickassist.worker
```

Không chạy worker thì ghi chú sẽ kẹt ở trạng thái `PENDING`. Khi xong, nhấn `Ctrl+C` ở Terminal 2 và 3, sau đó muốn quay lại Docker thì chạy `docker compose -f infra/docker-compose.yml up -d api worker` tại `D:\quick-assist-ext`.

---

## 3. Chạy extension trên Chrome

Mục này tạo bản **production** trong `dist`, khác bản test `dist-e2e` mà bạn đã nạp ở phần A. Chỉ làm mục này khi muốn thử đăng nhập Google OAuth thật hoặc chuẩn bị bản phát hành. Nếu đang dùng dev-login, tiếp tục dùng `dist-e2e`; không cần chạy lại mục 3.

```powershell
cd D:\quick-assist-ext\apps\extension
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
# Chỉ khi thử Google OAuth thật: mở .env.local và điền VITE_GOOGLE_CLIENT_ID.
& 'C:\Program Files\nodejs\npm.cmd' ci
& 'C:\Program Files\nodejs\npm.cmd' run build    # tạo thư mục dist/
```

Nạp vào Chrome:
1. Mở `chrome://extensions` → bật **Developer mode**.
2. **Load unpacked** → chọn `apps/extension/dist`.
3. Ghi lại **Extension ID**, rồi:
   - Thêm `chrome-extension://<ID>` vào `CORS_ORIGINS` và `https://<ID>.chromiumapp.org/` vào `OAUTH_ALLOWED_REDIRECT_URIS` trong `infra/.env`, rồi chạy `docker compose -f infra/docker-compose.yml up -d --build api` tại thư mục gốc.
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

Phần B4 đã chạy toàn bộ test này và integration test rồi. Chỉ dùng block này khi sửa backend sau đó và muốn kiểm tra lại nhanh.

```powershell
cd D:\quick-assist-ext\apps\api
.\.venv312\Scripts\python.exe -m pytest tests\architecture
```

### 4.2 Backend — integration (cần PostgreSQL)
Tạo DB test riêng một lần (đừng dùng DB `quickassist` vì test sẽ xoá sạch schema):
```powershell
docker compose -f infra/docker-compose.yml exec db createdb -U postgres quickassist_test
```
Chạy:
```powershell
cd D:\quick-assist-ext\apps\api
$env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test"
.\.venv312\Scripts\python.exe -m pytest -v
```
Kết quả mong đợi hiện tại: **180 passed**.

### 4.3 Đánh giá chất lượng tìm kiếm
```powershell
cd D:\quick-assist-ext\apps\api
$env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test"
.\.venv312\Scripts\python.exe -m tests.eval.run_eval
```
Kết quả ghi vào `apps/api/tests/eval/results/`; xem phân tích ở `docs/ai/eval-report.md`.

### 4.4 Extension — unit + kiến trúc
```powershell
cd D:\quick-assist-ext\apps\extension
& 'C:\Program Files\nodejs\npm.cmd' test -- --run   # mong đợi: 80 passed
& 'C:\Program Files\nodejs\npm.cmd' run typecheck
```

### 4.5 Extension — E2E (Playwright, chạy extension thật trên Chromium)

**Không chạy E2E trên database `quickassist` đang dùng để demo.** E2E tạo user/note/folder và có test sửa quota trực tiếp qua SQL. Đây là mục nâng cao: cần ba terminal, CORS/Extension ID cố định, và database `quickassist_e2e` riêng. Chỉ chạy sau khi đã đọc hết block này; không chạy cùng API/worker Docker.

Chuẩn bị database riêng một lần:

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml up -d db
docker compose -f infra/docker-compose.yml exec db createdb -U postgres quickassist_e2e
```

Nếu lệnh cuối báo `database "quickassist_e2e" already exists`, bỏ qua và tiếp tục. Không dùng `quickassist` hoặc `quickassist_test` ở bước này.

E2E cũng cần `VITE_EXTENSION_KEY` và `CORS_ORIGINS` khớp Extension ID như bước A2; nếu không, request từ extension sẽ bị CORS chặn. Thiết lập khoá/ID một lần theo mục **Cố định Extension ID** trong `apps/extension/README.md`, cập nhật `CORS_ORIGINS=chrome-extension://<ID>`, rồi đặt biến này ở cả hai terminal backend:

```powershell
$env:CORS_ORIGINS="chrome-extension://<EXTENSION_ID>"
```

Dừng API/worker Docker nếu chúng đang chạy để giải phóng cổng 8000, rồi chạy API và worker cục bộ ở hai terminal:

```powershell
docker compose -f infra/docker-compose.yml stop api worker
```

**Terminal 1 — API:**

```powershell
cd D:\quick-assist-ext\apps\api
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_e2e"
$env:APP_ENV="dev"
$env:ENABLE_DEV_LOGIN="true"
$env:AI_PROVIDER="mock"
$env:CORS_ORIGINS="chrome-extension://<EXTENSION_ID>"
.\.venv312\Scripts\python.exe -m alembic upgrade head
.\.venv312\Scripts\python.exe -m uvicorn quickassist.main:app --port 8000
```

**Terminal 2 — worker:**

```powershell
cd D:\quick-assist-ext\apps\api
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_e2e"
$env:APP_ENV="dev"
$env:ENABLE_DEV_LOGIN="true"
$env:AI_PROVIDER="mock"
$env:CORS_ORIGINS="chrome-extension://<EXTENSION_ID>"
.\.venv312\Scripts\python.exe -m quickassist.worker
```

Sau đó chạy Playwright ở terminal thứ ba:

```powershell
cd D:\quick-assist-ext\apps\extension
& 'C:\Program Files\nodejs\npm.cmd' exec playwright install chromium     # lần đầu
$env:E2E_DATABASE_URL="postgres://postgres:postgres@localhost:5432/quickassist_e2e"
& 'C:\Program Files\nodejs\npm.cmd' run test:e2e                    # build dist-e2e/ rồi chạy
$env:E2E_HEADED="1"
& 'C:\Program Files\nodejs\npm.cmd' run test:e2e                    # tuỳ chọn: xem trình duyệt chạy
& 'C:\Program Files\nodejs\npm.cmd' exec playwright show-report     # xem báo cáo HTML
```
Mong đợi: **28 passed**. Đóng hai terminal API/worker bằng `Ctrl+C` khi xong, rồi quay về thư mục gốc và bật lại backend Docker để dùng extension bình thường:

```powershell
cd D:\quick-assist-ext
docker compose -f infra/docker-compose.yml up -d api worker
```

Biến tuỳ chọn: `E2E_API_BASE_URL` (mặc định `http://localhost:8000/api/v1`), `E2E_DATABASE_URL` (phải là cùng database với API E2E). Chi tiết ở `apps/extension/e2e/README.md`.

### 4.6 Kiểm tra bản phát hành không lọt code test

Chạy khi chuẩn bị gửi bản extension cho người khác. Bước `package` chỉ tạo file zip trong `release/`, không đăng tải gì.
```powershell
cd D:\quick-assist-ext\apps\extension
& 'C:\Program Files\nodejs\npm.cmd' run build
& 'C:\Program Files\nodejs\npm.cmd' run check:bundle     # báo lỗi nếu dist/ chứa dev-login hoặc hook E2E
& 'C:\Program Files\nodejs\npm.cmd' run package          # đóng gói zip vào release/
```

### 4.7 Smoke test toàn hệ thống
Khi backend và worker đang chạy:
```powershell
cd D:\quick-assist-ext\apps\api
.\.venv312\Scripts\python.exe scripts\smoke_test.py --base http://localhost:8000 --dev-login --timeout 90
```
Mong đợi: **11/11 bước OK** (health, header bảo mật, 401, tạo ghi chú idempotent → READY → tìm thấy → tóm tắt → xoá). Khi dùng Gemini thật, tóm tắt có thể mất lâu hoặc Gemini có thể trả 500 tạm thời; chờ ít phút rồi chạy lại nếu chỉ riêng bước này lỗi. Bản deploy thật: xem `docs/deploy/runbook.md`.

---

## 5. Thứ tự kiểm tra trước khi commit

Chỉ chạy mục này khi chính bạn vừa sửa code và chuẩn bị tạo commit. Nó lặp lại B4/B5; không cần chạy chỉ để dùng thử extension.

```powershell
cd D:\quick-assist-ext\apps\api
$env:TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test"
.\.venv312\Scripts\python.exe -m pytest
cd D:\quick-assist-ext\apps\extension
& 'C:\Program Files\nodejs\npm.cmd' test -- --run
& 'C:\Program Files\nodejs\npm.cmd' run typecheck
& 'C:\Program Files\nodejs\npm.cmd' run build
& 'C:\Program Files\nodejs\npm.cmd' run check:bundle
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
