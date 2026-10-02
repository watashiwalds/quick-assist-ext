# ② Business & Application Layer

Toàn bộ nghiệp vụ. Mỗi thư mục con là **một service trong SDS §5.2**, có owner riêng (xem `.github/CODEOWNERS`).

| Thư mục | Service (SDS) | Bảng sở hữu |
|---|---|---|
| `auth/` | Google OAuth Service — `AuthService`, `AccountService` | users, auth_sessions |
| `notes/` | Notes Service — `NotesService`, `FolderService` | folders, notes |
| `quota/` | Quota Service | quota_accounts, quota_ledger |
| `semantic_search/` | Semantic Search Service (+ chunking, job đánh chỉ mục) | note_chunks |
| `summary/` | Summary Service | — (ghi qua Notes) |
| `rag/` | RAG Service (Nice-to-have) | chat_* (khi triển khai) |
| `system/` | Health/readiness | — |
| `common/` | Ngoại lệ nghiệp vụ, idempotency dùng chung | idempotency_keys |

**Quy tắc:**
- **Public API**: mỗi service export qua `__init__.py` (`__all__`). Service khác chỉ được `from quickassist.business.notes import ...`, không import `notes/notes_service.py` trực tiếp — test L2.
- **Không vòng phụ thuộc** giữa các service — test L3. Cần báo cho service khác mà không phụ thuộc ngược → phát job (`infrastructure/jobs/job_kinds.py`).
- **Chỉ dùng repository của mình** — test L4. Cần dữ liệu của service khác → gọi hàm public của service đó (vd. `notes.get_note_for_indexing`).
- **Không SQL** (`select`, `text`, `session.execute`) — test L5. Viết trong repository.
- Service quyết định transaction (commit/rollback); gọi AI qua interface ở `infrastructure/openai` (không import SDK trực tiếp).
- Lỗi nghiệp vụ ném `common.exceptions.*` (NotFound, Conflict, QuotaExceeded…), không ném `HTTPException`.

Tạo service mới: `business/<tên>/__init__.py` + `<tên>_service.py`, thêm vào `OWNERSHIP` trong `tests/architecture/test_layers.py` nếu có bảng riêng.
