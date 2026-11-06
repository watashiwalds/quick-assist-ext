# A01 — Sơ đồ thực thể (ERD) & quy ước migration

> Khớp `apps/api/src/quickassist/data/models/` và migration `0001` + `0002` (đã chạy `alembic check` = không lệch). Đối chiếu SDS v1.1 §6.

```mermaid
erDiagram
    users ||--o{ auth_sessions : "có (CASCADE)"
    users ||--o{ folders : "sở hữu (CASCADE)"
    users ||--o{ notes : "sở hữu (CASCADE)"
    users ||--o{ note_chunks : "sở hữu (CASCADE)"
    users ||--|| quota_accounts : "1-1 (CASCADE)"
    users ||--o{ quota_ledger : "nhật ký (CASCADE)"
    folders ||--o{ notes : "chứa (RESTRICT)"
    notes ||--o{ note_chunks : "chia thành (CASCADE)"

    users {
        uuid id PK
        string google_sub UK
        string email
        string display_name
        string avatar_url
        timestamptz created_at
        timestamptz last_active_at "chính sách lưu trữ 1 năm"
    }
    auth_sessions {
        uuid id PK
        uuid user_id FK
        string refresh_token_hash UK "SHA-256, không lưu token gốc"
        timestamptz expires_at
        timestamptz revoked_at
        uuid replaced_by "phiên mới khi xoay vòng"
        string user_agent
    }
    folders {
        uuid id PK
        uuid user_id FK
        string name "UNIQUE(user_id, name)"
        bool is_default "Inbox"
    }
    notes {
        uuid id PK
        uuid user_id FK
        uuid folder_id FK
        string url
        string domain
        string title
        text content "≤ MAX_NOTE_CHARS"
        text summary_text "chỉ lưu khi người dùng xác nhận"
        string index_status "PROCESSING|READY|SKIPPED|FAILED"
        string index_error
        int version "optimistic lock → 409"
        int index_rev "job cũ không ghi đè"
        timestamptz updated_at
        timestamptz deleted_at "tombstone cho sync"
    }
    note_chunks {
        uuid id PK
        uuid note_id FK
        uuid user_id FK
        uuid folder_id "bản sao để lọc"
        int ordinal
        text text
        string content_hash
        vector embedding "vector(1536), HNSW cosine"
        tsvector tsv "to_tsvector('simple', qa_unaccent(text)), GIN"
        string model
    }
    quota_accounts {
        uuid user_id PK
        bigint limit_tokens
        bigint used_tokens "CHECK >= 0"
        bigint reserved_tokens "CHECK >= 0"
        timestamptz period_start
    }
    quota_ledger {
        uuid id PK
        uuid user_id FK
        string request_id UK "chống trừ trùng"
        string operation "embed_note|search|summary|chat"
        bigint reserved_tokens
        bigint actual_tokens
        string status "RESERVED|COMMITTED|RELEASED"
    }
    idempotency_keys {
        uuid user_id PK
        string key PK
        string scope
        string request_hash
        uuid resource_id
        timestamptz created_at "hiệu lực 24h"
    }
    jobs {
        uuid id PK
        string kind
        jsonb payload
        string status "QUEUED|RUNNING|DONE|DEAD"
        int attempts
        timestamptz run_after
        string dedupe_key UK
    }
```

`idempotency_keys` và `jobs` không có FK tới `users` (khoá chính/payload chứa id) — xoá tài khoản vẫn sạch vì: idempotency hết hạn sau 24h; job index của note đã xoá tự dọn chunk (note không còn → `delete_for_note`).

## Chỉ mục
`notes(user_id, updated_at, id)` (sync/phân trang cursor) · `notes(user_id, folder_id)` · `note_chunks(user_id, folder_id)` · HNSW `note_chunks.embedding vector_cosine_ops` · GIN `note_chunks.tsv` · `jobs(status, run_after)` · `auth_sessions(user_id)` · `quota_ledger(user_id)`.

## Sở hữu bảng (luật L4)
| Bảng | Service (business/) | Repository |
|---|---|---|
| users, auth_sessions | auth | user_repository, auth_session_repository |
| folders, notes | notes | folder_repository, note_repository |
| note_chunks | semantic_search | note_chunk_repository |
| quota_accounts, quota_ledger | quota | quota_repository |
| idempotency_keys | common | idempotency_repository |
| jobs | infrastructure/jobs | (queue.py) |

## Quy ước migration theo service
| Quy tắc | Ví dụ |
|---|---|
| Tên file: `YYYYMMDD_NNNN_<service>_<mô tả>.py`, message bắt đầu bằng tên service | `20261008_0002_search_unaccent.py` — "semantic_search: …" |
| Chỉ sửa bảng của service mình; bảng mới khai báo trong `data/models/` | |
| Không sửa migration đã merge — tạo migration mới | |
| Phải có `downgrade()` chạy được — CI chạy `upgrade → check → downgrade base → upgrade` | |
| Hai người cùng thêm migration → `alembic heads` ra 2 head → sửa `down_revision` của migration MỚI hơn | CONTRIBUTING.md |
| Extension Postgres cần dùng (`vector`, `unaccent`) tạo trong migration bằng `CREATE EXTENSION IF NOT EXISTS` | |
