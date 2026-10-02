# ① Presentation & Integration Layer

Cửa vào duy nhất của backend (SDS Hình 1 — "API Controller"). Nhận HTTP, xác thực, kiểm tra đầu vào, gọi **một** service ở Business Layer, trả DTO.

```
presentation/
├─ api/
│  ├─ deps.py              Dependency Injection: session DB, user hiện tại, khởi tạo service
│  ├─ middleware.py        request_id, log truy cập
│  ├─ error_handlers.py    BusinessError → HTTP {error:{code,message,details,request_id}}
│  └─ v1/
│     ├─ router.py         gộp mọi controller dưới /api/v1
│     └─ controllers/      mỗi file = 1 nhóm endpoint = 1 service
└─ schemas/                DTO Pydantic (request/response) — tách khỏi ORM model
```

**Được:** khai báo route, đọc header (`Authorization`, `Idempotency-Key`), validate DTO, map lỗi, mở transaction qua `deps`.

**Cấm:**
- import `data_access` hoặc `data.models` (controller không đụng DB) — test L1;
- viết nghiệp vụ trong controller (if/else về quota, ownership… thuộc service);
- trả ORM model ra ngoài — luôn chuyển sang schema.

Quy ước URL, mã lỗi, phân trang: `docs/api/conventions.md`.
