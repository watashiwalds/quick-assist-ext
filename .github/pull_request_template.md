## Task
<!-- Mã task trong bảng phân công, vd: N03 -->

## Thay đổi

## Checklist (Definition of Done)
- [ ] Chỉ sửa trong thư mục mình sở hữu, hoặc đã có owner thư mục kia duyệt
- [ ] Code nằm đúng tầng (presentation / business / data_access / data / infrastructure) — `tests/architecture/test_layers.py` pass
- [ ] Gọi service khác chỉ qua `quickassist.business.<service>` (backend) / RPC (extension)
- [ ] Đổi model DB → có migration Alembic (`alembic check` pass)
- [ ] Đổi API → đã cập nhật `docs/api/conventions.md` (nếu đổi quy ước) và chạy `npm run gen:api`
- [ ] Có test cho nhánh chính + nhánh lỗi
- [ ] Không log token / nội dung ghi chú; không hard-code secret
