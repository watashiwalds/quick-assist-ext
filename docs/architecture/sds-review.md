# Rà soát SDS (`SDS_Nhomx.pdf` → v1.0) theo khung System Design Trade-offs

> **Trạng thái:** tất cả mục dưới đây đã được áp dụng trong **`docs/specs/SDS_Nhom1_v1.1.docx`** (02/10/2026). File này giữ lại làm lịch sử lý do thay đổi.

Đối chiếu theo 5 bước của tài liệu *System Design Trade_Offs.docx*: (1) yêu cầu & ràng buộc → (2) kiến trúc tổng → (3) đi sâu thành phần → (4) mở rộng & điểm nghẽn → (5) tổng kết trade-off.

## Điểm làm tốt
- Phạm vi Must-have / Nice-to-have / Out-of-scope rõ (bước 1).
- Đã nhận ra lưu bất đồng bộ (202 + PROCESSING), idempotency key, quota theo request_id, xoá tài khoản trong transaction — đều là quyết định đúng ở bước 3.
- Có nhắc prompt injection từ nội dung web (§2.2).

## Cần sửa trong SDS (đề xuất câu chữ thay thế)

| # | Vị trí | Vấn đề | Sửa thành |
|---|---|---|---|
| 1 | §5.2 "phân tách thành các microservice độc lập" | Mâu thuẫn với §4.2 (API và worker chạy cùng máy) và với chính Hình 1 (kiến trúc phân tầng). | "Hệ thống theo **kiến trúc phân tầng** (Hình 1), triển khai dạng monolith gồm 2 tiến trình (API, worker). Các *service* dưới đây là **service trong Business Layer**, gọi nhau qua interface công khai" (ADR-0001). |
| 2 | Hình 1: một `RepositoryService` duy nhất, mọi service nối thẳng `OpenAI API`, thiếu QuotaService | Repository chung khiến service nào cũng đụng được mọi bảng; AI không có lớp trừu tượng; Quota Service ở §5.2 không xuất hiện trên hình. | Vẽ lại Data Access Layer thành *Repositories (mỗi service một nhóm)*; thêm **QuotaService** vào Business Layer; chú thích "OpenAI API qua AI Adapter (có Mock)". |
| 2b | §5.2: Notes Service "thực thi transaction phức tạp (như xóa tài khoản)" | Xoá tài khoản là xoá bảng `users`, vốn thuộc Google OAuth Service ("tạo hoặc khôi phục tài khoản", §4.3). | Ghi: "Xoá tài khoản do **OAuth Service (AccountService)** thực hiện trong 1 transaction; CASCADE xoá dữ liệu của Notes/Search/Quota". Code: `business/auth/account_service.py`. |
| 3 | Thiếu "điểm cân bằng nhất quán" (bước 1) | Không nói chỗ nào cần nhất quán mạnh / chấp nhận trễ. | Thêm mục: nhất quán mạnh cho note, quota, xoá dữ liệu; eventual cho chỉ mục tìm kiếm (READY sau vài giây) và cache IndexedDB. |
| 4 | §5.1.2 — background worker không nói cơ chế | "Worker" mà không có hàng đợi bền → mất job khi restart. | Hàng đợi job trên PostgreSQL + outbox cùng transaction (ADR-0003). |
| 5 | §6 thiết kế dữ liệu | `quota_used` nằm trong `users` → không audit, không chống trừ trùng; thiếu `version`, `deleted_at`, `index_status`, bảng session, bảng jobs/idempotency. | Dùng bảng như `docs/architecture/README.md §6`. |
| 6 | §7 "framework cụ thể sẽ được chốt khi triển khai" | Kế hoạch tuần 1 cần khởi tạo skeleton → phải chốt ngay. | FastAPI + SQLAlchemy 2 (async) + Alembic; extension: Vite + CRXJS + React + TS. |
| 7 | §5.1.3 "top 5 theo vector" vs kịch bản "BM25 + vector + rerank" | Hai tài liệu lệch nhau. | Hybrid vector + full-text gộp RRF; rerank là tuỳ chọn có fallback (ADR-0006). |
| 8 | §3.2 "lưu tối đa một năm" | Không có cơ chế nào thực hiện. | Thêm job dọn dữ liệu theo `last_active_at` (task RET-01 trong kế hoạch v2) hoặc bỏ yêu cầu. |
| 9 | §9 "nhiều instance sau Load Balancer" | Không nói điều kiện để scale được. | API stateless (JWT), worker dùng SKIP LOCKED → scale ngang được; giới hạn thật là DB connection và quota OpenAI. |
| 10 | Thiếu ước lượng tải (bước 4) | Không có con số. | Demo ~50 user × 30 note/ngày ≈ 1 500 note/ngày ≈ 0.02 job/s; search cao điểm < 5 req/s → 1 API + 1 worker + 1 Postgres là dư; điểm nghẽn đầu tiên là **rate limit OpenAI**, không phải server. |

## Trade-off tổng kết (để đưa vào phần kết của SDS — bước 5)
1. **Đơn giản > khả năng mở rộng độc lập:** kiến trúc phân tầng trong monolith; chỉ tách service khi có số liệu chứng minh.
2. **Độ bền > độ trễ của chỉ mục:** note lưu ngay, AI xử lý nền; người dùng thấy READY sau vài giây.
3. **Một kho dữ liệu > kho chuyên dụng:** PostgreSQL+pgvector đủ cho quy mô, đổi lấy xoá dữ liệu nguyên tử.
4. **Quyền tối thiểu > tiện lợi khi code:** không content script thường trực, mọi gọi mạng qua background.
5. **Đã biết chưa làm:** rate limiting theo user, rerank, chat streaming, `unaccent` cho tiếng Việt, dọn dữ liệu 1 năm.
