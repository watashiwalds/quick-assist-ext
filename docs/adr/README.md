# Architecture Decision Records

Mỗi quyết định kiến trúc = 1 file ngắn: **Bối cảnh → Quyết định → Phương án đã loại → Hệ quả (trade-off)**.
Theo khung "System Design Trade-offs": luôn nêu ≥ 2 phương án, chọn 1, nói rõ cái giá phải trả.

| # | Quyết định | Trạng thái |
|---|---|---|
| [0001](0001-modular-monolith.md) | Layered Architecture (theo SDS Hình 1) trong một modular monolith | Chấp nhận |
| [0002](0002-postgres-single-datastore.md) | PostgreSQL + pgvector là kho dữ liệu duy nhất | Chấp nhận |
| [0003](0003-postgres-job-queue-outbox.md) | Hàng đợi job trên PostgreSQL + transactional outbox | Chấp nhận |
| [0004](0004-ai-provider-port-adapter.md) | AI qua port/adapter, có mock provider | Chấp nhận |
| [0005](0005-google-oauth-pkce-app-session.md) | Google OAuth Code+PKCE, server đổi code, app session riêng | Chấp nhận |
| [0006](0006-hybrid-search-rrf.md) | Hybrid search (vector + full-text) gộp bằng RRF trong SQL | Chấp nhận |
| [0007](0007-extension-background-gateway.md) | Extension: background là cổng mạng duy nhất, RPC có kiểu | Chấp nhận |
| [0008](0008-client-cache-outbox.md) | Cache-first đọc, outbox ghi, server là nguồn sự thật | Chấp nhận |
| [0009](0009-sse-for-chat-streaming.md) | SSE cho streaming chat (Nice-to-have) | Đề xuất |

Thêm ADR mới: copy file gần nhất, tăng số, mở PR cho cả nhóm duyệt.
