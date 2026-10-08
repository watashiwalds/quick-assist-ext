# QuickAssist — Trợ lý ghi chú nhanh dựa trên AI

Chrome extension (Manifest V3) cho phép bôi đen văn bản trên web để lưu ghi chú, tóm tắt bằng AI và tìm lại theo ngữ nghĩa.

- **Kiến trúc:** [`docs/architecture/README.md`](docs/architecture/README.md) (đọc trước khi code)
- **Quyết định kiến trúc (ADR):** [`docs/adr/`](docs/adr/)
- **Quy ước API:** [`docs/api/conventions.md`](docs/api/conventions.md)
- **Quy trình làm việc nhóm:** [`CONTRIBUTING.md`](CONTRIBUTING.md)

```
apps/api/            Backend Python (FastAPI) — Layered Architecture theo SDS Hình 1
  src/quickassist/
    presentation/      ① Presentation & Integration Layer (API Controller, DTO)
    business/          ② Business & Application Layer (auth, notes, quota, semantic_search, summary, rag)
    data_access/       ③ Data Access Layer (repositories)
    data/              ④ Data Layer (database, models) + apps/api/migrations
    infrastructure/    ⑤ Infrastructure Layer (google_oauth, openai, logging, jobs)
apps/extension/      Chrome extension MV3 (ui, background, content, shared)
infra/               docker-compose cho dev/demo
docs/                specs (SDS v1.1…), plan, architecture, adr, api, qa — xem docs/README.md
scripts/             tiện ích sinh tài liệu/kế hoạch
```

Mỗi app và mỗi thư mục tầng có `README.md` riêng: [`apps/api/README.md`](apps/api/README.md), [`apps/extension/README.md`](apps/extension/README.md).

## Chạy nhanh

### 1. Backend + database (Docker)
```bash
cp infra/.env.example infra/.env        # Windows: copy infra\.env.example infra\.env
docker compose -f infra/docker-compose.yml up --build
# → http://localhost:8000/docs  (Swagger)
```
Mặc định `AI_PROVIDER=mock` (không tốn tiền) và `ENABLE_DEV_LOGIN=true` (đăng nhập không cần Google để thử API).

### 2. Backend không dùng Docker (khi phát triển)
```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# cần PostgreSQL 16 + pgvector đang chạy (có thể chỉ chạy service db: docker compose -f ../../infra/docker-compose.yml up db)
alembic upgrade head
uvicorn quickassist.main:app --reload          # terminal 1
python -m quickassist.worker                   # terminal 2
```
Test: `pytest` (unit + kiến trúc). Thêm integration: đặt `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quickassist_test`.

### 3. Extension
```bash
cd apps/extension
cp .env.example .env.local     # điền VITE_GOOGLE_CLIENT_ID
npm install
npm run dev                    # hoặc: npm run build → thư mục dist/
```
Chrome → `chrome://extensions` → bật Developer mode → **Load unpacked** → chọn `apps/extension/dist`.
Lấy Extension ID, điền vào `CORS_ORIGINS` và `OAUTH_ALLOWED_REDIRECT_URIS` của backend, và thêm redirect URI `https://<ID>.chromiumapp.org/` trên Google Cloud Console.

Test: `npm test` (unit + kiến trúc) · `npm run gen:api` sinh lại kiểu TypeScript từ OpenAPI khi backend đổi.
