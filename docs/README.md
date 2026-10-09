# Tài liệu dự án

| Thư mục | Nội dung | Khi nào đọc |
|---|---|---|
| [`specs/`](specs/) | SDS (bản chính: **SDS_Nhom1_v1.1**), kịch bản chức năng, báo cáo ý tưởng, tài liệu tham khảo | Nguồn yêu cầu — đọc đầu tiên |
| [`architecture/`](architecture/) | Kiến trúc phân tầng, cây thư mục, đối chiếu SDS ↔ code, ownership bảng | Trước khi viết code |
| [`adr/`](adr/) | Quyết định kiến trúc (ADR-0001…0011) và lý do đánh đổi | Khi định đổi một quyết định đã chốt |
| [`api/`](api/) | Quy ước REST, mã lỗi, quyết định P02, **`openapi.json`** (contract, CI kiểm tra khớp code) | Khi thêm/sửa endpoint |
| [`ai/`](ai/) | Spike OpenAI (P03), báo cáo đánh giá tìm kiếm & chunking (H03, N04, R01) | Khi chỉnh model/chunk/tìm kiếm |
| [`ux/`](ux/) | 6 user flow + 17 màn hình thật mọi trạng thái (P04) | Khi làm/đổi giao diện |
| [`security/`](security/) | Checklist bảo mật extension + backend (H01, H02) | Trước phát hành |
| [`deploy/`](deploy/) | Runbook triển khai, rollback, sao lưu/khôi phục (H04, H07) | Khi deploy |
| [`plan/`](plan/) | Kế hoạch & phân công (v2 đang dùng) | Nhận task |
| [`qa/`](qa/) | Test plan, RTM, biên bản kiểm thử (P08, N07, C05, R05, SUM-04, H05) | Trước mỗi mốc |
| [`report/`](report/) · [`user-guide.md`](user-guide.md) · [`demo-script.md`](demo-script.md) | Báo cáo cuối (nháp), hướng dẫn sử dụng, kịch bản thuyết trình (H08) | Tuần 8 |
| [`github-setup.md`](github-setup.md) | Việc cần quyền admin GitHub: CODEOWNERS, bảo vệ nhánh (P09) | Một lần |

Đổi kiến trúc → cập nhật cả SDS (`specs/`), `architecture/README.md` và thêm ADR mới.
