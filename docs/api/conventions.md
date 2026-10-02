# Quy ước API (giải quyết rủi ro R-02 / task P02)

Nguồn sự thật cho schema: **OpenAPI sinh tự động** tại `GET /api/v1/openapi.json` (Swagger UI: `/docs` ở môi trường dev).
File này chỉ chốt *quy ước*, không lặp lại từng field.

## 1. Quy tắc chung
- Tiền tố phiên bản: `/api/v1`. Thay đổi phá vỡ contract → `/api/v2`, không sửa ngầm v1.
- JSON `snake_case`; thời gian ISO-8601 UTC; id là UUID.
- Xác thực: `Authorization: Bearer <access_token>`. **user_id không bao giờ nằm trong body/query.**
- Tài nguyên của người khác → **404** (không phải 403) để không lộ sự tồn tại.
- Tạo mới có thể retry → header `Idempotency-Key: <uuid>` (bắt buộc với `POST /notes` từ extension).
- Mọi response có header `X-Request-ID` — ghi vào báo lỗi để tra log.
- Phân trang cursor: `?limit=&cursor=` → `{ items, next_cursor }`.
- Cập nhật dùng `PATCH` + trường `version` (optimistic lock) → lệch trả **409**.

## 2. Định dạng lỗi (mọi endpoint)
```json
{ "error": { "code": "NOTE_VERSION_CONFLICT", "message": "…", "details": {"current_version": 3}, "request_id": "…" } }
```
| HTTP | Khi nào | Ví dụ `code` |
|---|---|---|
| 401 | thiếu/sai/hết hạn token | `TOKEN_MISSING`, `TOKEN_EXPIRED`, `REFRESH_REUSED` |
| 402 | hết quota AI | `QUOTA_EXCEEDED` |
| 404 | không tồn tại / không thuộc user | `NOTE_NOT_FOUND`, `FOLDER_NOT_FOUND` |
| 409 | xung đột | `NOTE_VERSION_CONFLICT`, `IDEMPOTENCY_KEY_REUSED`, `FOLDER_EXISTS` |
| 413 | vượt giới hạn | `NOTE_TOO_LONG` |
| 422 | sai định dạng đầu vào | `VALIDATION_ERROR` |
| 502 | dịch vụ ngoài lỗi | `AI_UNAVAILABLE`, `OAUTH_UPSTREAM` |
| 501 | chưa làm | `CHAT_NOT_IMPLEMENTED` |

Extension map `code` → câu thông báo tại `apps/extension/src/shared/errors.ts`.

## 3. Danh mục endpoint (đã hợp nhất các điểm mâu thuẫn trong kịch bản)

| Method & path | Module | Ghi chú |
|---|---|---|
| `GET /health/live`, `/health/ready` | — | readiness kiểm tra DB |
| `POST /auth/google/exchange` | auth | `{code, code_verifier, redirect_uri, nonce}` → cặp token |
| `POST /auth/refresh` · `POST /auth/logout` | auth | refresh xoay vòng |
| `GET /me` · `DELETE /me` | accounts | xoá tài khoản + toàn bộ dữ liệu |
| `GET /me/quota` | quota | |
| `GET/POST /folders` · `PATCH/DELETE /folders/{id}` | notes | xoá thư mục → note về Inbox |
| `POST /notes` | notes | **thay cho** `/notes/quick` và `/notes/ragged` của kịch bản; 201 + `index_status=PROCESSING` |
| `GET /notes?folder_id&updated_since&cursor&limit` | notes | `updated_since` → kèm tombstone cho sync |
| `GET/PATCH/DELETE /notes/{id}` | notes | **thay cho** `PUT /notes` + ID trong body |
| `POST /notes/bulk-delete` | notes | **thay cho** `DELETE /notes` có body (nhiều proxy bỏ body của DELETE) |
| `PUT /notes/{id}/summary` | notes | lưu tóm tắt đã xác nhận |
| `POST /notes/{id}/reindex` | notes | "Thử lại" cho note FAILED/SKIPPED |
| `POST /search` | search | **thay cho** `/search/ranking` |
| `POST /ai/summaries` | ai | trả preview, không ghi DB |
| `POST /ai/chat` | ai | SSE — Nice-to-have (ADR-0009) |

Vì sao `POST /notes` trả **201** chứ không phải 202 như SDS: bản ghi note đã được tạo xong (đó là tài nguyên client cần); chỉ phần index AI là bất đồng bộ và được phản ánh qua `index_status`.

## 4. Quy trình đổi contract
1. Sửa `schemas.py` của module → test backend.
2. `npm run gen:api` trong `apps/extension` (API đang chạy) → commit `schema.d.ts`.
3. PR phải có duyệt của owner backend **và** owner extension (CODEOWNERS đã cấu hình cho `shared/api/`).
