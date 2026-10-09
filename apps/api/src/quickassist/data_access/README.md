# ③ Data Access Layer

Repository — nơi **duy nhất** viết truy vấn SQL/ORM. SDS Hình 1 "Repositories (mỗi service một nhóm)".

```
data_access/repositories/
├─ user_repository.py, auth_session_repository.py   → auth
├─ folder_repository.py, note_repository.py         → notes
├─ quota_repository.py                              → quota
├─ note_chunk_repository.py                         → semantic_search (vector + full-text, RRF)
├─ idempotency_repository.py                        → common
└─ system_repository.py                             → system (ping DB)
```

**Được:** `select/insert/update`, `FOR UPDATE`, pgvector `<=>`, `tsvector`, nhận `AsyncSession` từ service.

**Cấm:**
- `session.commit()` / `rollback()` — transaction thuộc service (test L6);
- nghiệp vụ (kiểm tra quota, quyết định trạng thái…);
- import `business` hoặc `presentation` (test L1).

Mọi truy vấn dữ liệu người dùng **phải lọc theo `user_id`** (chống IDOR). Tên file `<entity>_repository.py`; khai báo owner trong `OWNERSHIP` của `tests/architecture/test_layers.py`.
