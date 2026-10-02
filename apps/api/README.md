# apps/api — Backend QuickAssist

Modular monolith theo **Layered Architecture** (SDS v1.1 — Hình 1), chạy thành 2 tiến trình từ cùng một codebase:

| Tiến trình | Lệnh | Vai trò |
|---|---|---|
| API | `uvicorn quickassist.main:app --reload` | Nhận HTTP từ extension (`/api/v1/...`) |
| Worker | `python -m quickassist.worker` | Lấy job từ hàng đợi PostgreSQL (`SKIP LOCKED`): embedding, xoá chỉ mục |

## Cấu trúc

```
apps/api/
├─ src/quickassist/
│  ├─ presentation/     ① Presentation & Integration — controller (router), DTO/schema, middleware, DI
│  ├─ business/         ② Business & Application    — các service: auth, notes, quota, semantic_search, summary, rag, system, common
│  ├─ data_access/      ③ Data Access               — repositories (mỗi service sở hữu repo/bảng của mình)
│  ├─ data/             ④ Data                      — engine/session, ORM models
│  ├─ infrastructure/   ⑤ Infrastructure            — config, logging, security (JWT), google_oauth, openai (adapter + mock), jobs (queue)
│  ├─ main.py           composition root của API
│  └─ worker.py         composition root của Worker
├─ migrations/          Alembic (schema của tầng Data)
└─ tests/
   ├─ architecture/     luật phân tầng L1–L7 (chạy trong CI — vi phạm là đỏ)
   ├─ unit/             test thuần, không cần DB (business/, infrastructure/)
   └─ integration/      test qua HTTP với PostgreSQL + pgvector thật
```

Mỗi thư mục tầng có `README.md` riêng nói **được đặt gì / cấm gì**. Đọc trước khi thêm file.

## Luồng phụ thuộc (một chiều)

```
presentation ──► business ──► data_access ──► data
      └────────────┴──────────────┴──────────► infrastructure
```

- Tầng trên chỉ gọi tầng ngay dưới qua **public API** của package (`from quickassist.business.notes import NotesService`), không import file nội bộ.
- `business` không viết SQL, không `commit()` trong repository — transaction do service mở.
- Bảng nào thuộc service nào: xem `OWNERSHIP` trong `tests/architecture/test_layers.py`.

## Thêm một tính năng — đặt file ở đâu

| Việc | File |
|---|---|
| Endpoint mới | `presentation/api/v1/controllers/<service>_controller.py` + DTO ở `presentation/schemas/<service>.py`, đăng ký ở `presentation/api/v1/router.py` |
| Nghiệp vụ | `business/<service>/<tên>_service.py`, export trong `business/<service>/__init__.py` (`__all__`) |
| Truy vấn DB | `data_access/repositories/<entity>_repository.py` |
| Bảng mới | `data/models/<entity>.py` → `alembic revision --autogenerate -m "<service>: ..."` |
| Gọi dịch vụ ngoài | `infrastructure/<nhà cung cấp>/` + interface (Port) để business dùng |
| Job nền | khai báo kind ở `infrastructure/jobs/job_kinds.py`, handler ở `business/<service>/`, đăng ký trong `worker.py` |

## Chạy local

```bash
cp .env.example .env                 # Windows: copy .env.example .env
python -m venv .venv && .venv\Scripts\activate      # Linux/mac: source .venv/bin/activate
pip install -e ".[dev]"
docker compose -f ../../infra/docker-compose.yml up -d db
alembic upgrade head
uvicorn quickassist.main:app --reload   # http://localhost:8000/docs
python -m quickassist.worker            # terminal khác
```

## Kiểm tra trước khi tạo PR

```bash
ruff check src tests migrations
pytest -q                               # unit + kiến trúc (+ integration nếu đặt TEST_DATABASE_URL)
alembic check                           # model và migration khớp nhau
```
