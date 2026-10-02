# Tài liệu dự án

| Thư mục | Nội dung | Khi nào đọc |
|---|---|---|
| [`specs/`](specs/) | SDS (bản chính: **SDS_Nhom1_v1.1**), kịch bản chức năng, báo cáo ý tưởng, tài liệu tham khảo | Nguồn yêu cầu — đọc đầu tiên |
| [`architecture/`](architecture/) | Kiến trúc phân tầng, cây thư mục, đối chiếu SDS ↔ code, ownership bảng | Trước khi viết code |
| [`adr/`](adr/) | Quyết định kiến trúc (ADR-0001…0009) và lý do đánh đổi | Khi định đổi một quyết định đã chốt |
| [`api/`](api/) | Quy ước REST, mã lỗi, idempotency, controller ↔ service | Khi thêm/sửa endpoint |
| [`plan/`](plan/) | Kế hoạch & phân công (v2 đang dùng) | Nhận task |
| [`qa/`](qa/) | Chiến lược kiểm thử, checklist demo | Trước mỗi mốc |

Đổi kiến trúc → cập nhật cả SDS (`specs/`), `architecture/README.md` và thêm ADR mới.
