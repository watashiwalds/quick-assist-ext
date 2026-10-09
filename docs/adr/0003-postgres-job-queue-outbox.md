# ADR-0003: Hàng đợi job trên PostgreSQL + transactional outbox

**Bối cảnh.** SDS §5.1.2 yêu cầu lưu note trả về ngay (PROCESSING) và xử lý chunk/embedding nền. Gọi OpenAI mất 0.5–5s và có thể lỗi; NFR yêu cầu lưu note < 2s và note gốc không mất nếu AI lỗi.

**Quyết định.** Bảng `jobs`; worker lấy job bằng `SELECT … FOR UPDATE SKIP LOCKED`; retry exponential backoff (10s → 10'), tối đa 5 lần rồi `DEAD`. Job được `INSERT` **trong cùng transaction** với thay đổi dữ liệu (outbox) → không bao giờ có note mà không có job index, hoặc ngược lại. Tên job ở `infrastructure/jobs/job_kinds.py`; service phát job (notes) không import service xử lý (semantic_search).

**Phương án đã loại.**
| Phương án | Lý do loại |
|---|---|
| Xử lý đồng bộ trong request | Request chờ OpenAI → vượt 2s, lỗi AI làm hỏng thao tác lưu. |
| FastAPI `BackgroundTasks` | Mất job khi tiến trình restart; không retry; không scale riêng. |
| Celery/RQ + Redis | Thêm broker; không có outbox nguyên tử với DB (có thể commit note mà job không vào queue). |

**Hệ quả.**
- (+) Độ bền: job sống qua restart; nhiều worker song song an toàn; dedupe job index theo note.
- (−) Poll mỗi 1s → độ trễ READY ~1–3s (eventual consistency, chấp nhận). Có thể thêm `LISTEN/NOTIFY` sau.
- (−) Throughput giới hạn ở vài trăm job/s — dư cho dự án; vượt ngưỡng thì đổi implementation `enqueue/worker_loop` sang broker mà không đổi API.
