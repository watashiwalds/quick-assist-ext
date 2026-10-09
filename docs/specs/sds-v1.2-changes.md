# Thay đổi cần đưa vào SDS v1.2 (sau khi làm xong P0, 09/10/2026)

> D01 (cập nhật SDS theo `sds-review.md`) đã hoàn thành ở **SDS_Nhom1_v1.1**. Trong lúc triển khai P0, một số quyết định mới làm SDS v1.1 lệch code. Danh sách dưới đây để người phụ trách tài liệu sửa `SDS_Nhom1_v1.1.docx` → v1.2 rồi xuất PDF.

| # | Mục SDS | Nội dung hiện tại (v1.1) | Sửa thành | Lý do / nguồn |
|---|---|---|---|---|
| 1 | §3.1 FR lưu nhanh; §9 checklist bước 5 | "phím tắt Ctrl+Alt+N", hoàn tác Ctrl+Alt+Z | **Alt+Shift+N** / **Alt+Shift+Z** (đổi được tại chrome://extensions/shortcuts) | Chrome cấm Ctrl+Alt — extension không nạp được (ADR-0011) |
| 2 | §5.1.2 | "lỗi vĩnh viễn → FAILED để Thử lại" (phía server) | thêm: phía extension, ghi chú **gửi lỗi** không tự khắc phục được giữ trong mục "chưa gửi được" để người dùng Gửi lại/Bỏ — không bao giờ tự xoá | ADR-0011 |
| 3 | §5.1.3, Bảng 2 dòng hybrid search | "Full-text cấu hình simple chưa xử lý dấu tiếng Việt (đo và cải thiện sau)" | "Nhánh từ khoá bỏ dấu (unaccent) và kết hợp OR giữa các từ; đo bằng bộ đánh giá Recall@5 = 0.978, không dấu = 1.0" | R01, H03 (`docs/ai/eval-report.md`) |
| 4 | §5.1.2 chia đoạn | (không nêu chiến lược) | "Chia theo câu tiếng Việt (không tách sau chữ viết tắt/số thập phân), gói ≤ 1 200 ký tự, chồng lấp theo câu" | N04 |
| 5 | §5.3 Bảng 5 / quy ước lỗi | 402 hết quota | thêm **429 `RATE_LIMITED` + Retry-After** (30 tìm kiếm, 10 tóm tắt, 120 ghi / phút / user) | P02, ADR-0010 |
| 6 | §6 Bảng 6 `note_chunks.tsv` | `to_tsvector('simple', text)` | `to_tsvector('simple', qa_unaccent(text))` | migration 0002 |
| 7 | §5.2 Quota Service | reserve → commit/release | thêm: request_id gắn user; worker tự hoàn giữ chỗ treo > 15 phút; ước lượng giữ chỗ = ký tự/2 | A04, P03 |
| 8 | §8 Quyền Extension | — | thêm: CI rà soát bundle (không secret, không quyền thừa, không mã kiểm thử) | H01 |
| 9 | §9 Triển khai | "reverse proxy kết thúc HTTPS" | nêu cụ thể Caddy + Let's Encrypt, sao lưu hằng ngày `pg_dump` giữ 14 ngày, runbook `docs/deploy/runbook.md` | H04 |
| 10 | Bảng 1 lịch sử | — | dòng **1.2 – <ngày> – cập nhật theo kết quả triển khai P0 (mục 1–9)** | |
