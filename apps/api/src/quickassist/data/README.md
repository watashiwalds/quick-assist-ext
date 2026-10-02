# ④ Data Layer

PostgreSQL 16 + pgvector — nguồn dữ liệu duy nhất (ADR-0002). SDS §6.

```
data/
├─ database.py     engine async, session factory, Base
└─ models/         ORM entity — 1 file / nhóm bảng (user, auth_session, note, note_chunk, quota, idempotency_key, job)
```
Schema được quản lý bằng Alembic ở `apps/api/migrations/`.

**Quy tắc:**
- Entity mới: thêm file trong `models/`, import trong `models/__init__.py`, rồi
  `alembic revision --autogenerate -m "<service>: <mô tả>"` — CI chạy `alembic check`, quên migration là đỏ.
- Không sửa migration đã merge vào `dev`; tạo migration mới.
- Chỉ chứa cấu trúc dữ liệu (cột, index, ràng buộc) — không logic.
- Khoá ngoại tới `users.id` dùng `ON DELETE CASCADE` (xoá tài khoản xoá sạch dữ liệu).
