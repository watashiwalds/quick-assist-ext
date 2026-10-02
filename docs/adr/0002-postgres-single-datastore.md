# ADR-0002: PostgreSQL + pgvector là kho dữ liệu duy nhất

**Bối cảnh.** Cần lưu dữ liệu quan hệ (user, note, quota — cần ACID), vector embedding, chỉ mục full-text, hàng đợi job, idempotency key, session.

**Quyết định.** Dùng **một** PostgreSQL 16 + pgvector cho tất cả. Vector: cột `vector(1536)` + chỉ mục HNSW (cosine). Full-text: cột `tsvector` sinh tự động, cấu hình `simple` (tiếng Việt không có stemmer chuẩn).

**Phương án đã loại.**
| Phương án | Lý do loại |
|---|---|
| Vector DB riêng (Qdrant, Pinecone) | Dữ liệu tách 2 nơi → xoá note/tài khoản không còn atomic, phải đồng bộ; thêm 1 hệ thống. pgvector đủ cho < 1 triệu chunk. |
| Redis cho cache/queue/session | Thêm hạ tầng; tải hiện tại không cần. Session dùng JWT (stateless) + bảng refresh token. |
| NoSQL (MongoDB) | Mất ACID cho quota/xoá dữ liệu — đúng chỗ cần nhất quán mạnh. |

**Hệ quả.**
- (+) Một nguồn sự thật, nhất quán mạnh, backup 1 chỗ, CASCADE xoá sạch.
- (−) Đổi model embedding khác số chiều = migration mới + reindex toàn bộ (ghi rõ trong `search/models.py`).
- (−) Khi > vài triệu chunk hoặc QPS search lớn → cân nhắc read replica hoặc vector DB riêng.
