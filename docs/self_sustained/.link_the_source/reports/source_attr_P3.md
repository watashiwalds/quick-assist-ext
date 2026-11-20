# P3 — Tìm kiếm: nhóm con theo trang trong nhóm domain

> Phase 3 của `docs/self_sustained/source-attribution-plan.md`
> Ngày: 2026-11-20 · Trạng thái: ✅ Hoàn thành

## Đã làm

- `apps/extension/src/ui/features/search/SearchResults.tsx`:
  - Sửa `sourceKey(s) = s.document_id ?? s.domain ?? '__unknown__'` — hết trùng React key khi hai tài liệu khác nhau cùng domain (rủi ro đã ghi trong plan §11).
  - Trong mỗi `GroupSection` domain: nhóm `s.notes` (theo slice đang hiển thị) bằng `groupByPage` từ `shared/source.ts`.
  - `pages.length <= 1` → render danh sách note như cũ (không thêm header, không tăng nhiễu).
  - `> 1` → mỗi trang là `<section class="source-page">` với header `host + path` (link external khi có URL; “Không rõ trang” render span, không link) + count; “Không rõ trang” luôn cuối (tính chất của `groupByPage`).
  - “Xem thêm” vẫn ở cấp domain; mở rộng → nhóm trang tính lại trên dữ liệu mới tải.
- `styles.css`: `.source-page`, `.source-page-head`, `.source-page-label`, `.source-page-count` (dùng chung cho P4).
- Test: 4 case mới trong `tests/ui/ui.test.tsx` — 2 URL → 2 nhóm con + unknown cuối; 1 URL → ẩn header; 2 document cùng domain không mất nhóm; “Xem thêm” mở rộng tính lại nhóm trang.

## Kết quả kiểm chứng

- `npx vitest run tests/ui/ui.test.tsx` → 34/34 pass.
- Full suite → 276/276 pass (cùng P4), typecheck pass.

## Quyết định ghi nhận trong phase

| # | Vấn đề | Quyết định | Lý do |
|---|---|---|---|
| P3-D1 | Nhóm trang tính trên slice nào | Trên **notes đang hiển thị** (3 note đầu hoặc toàn bộ sau “Xem thêm”) | Đúng plan §7.5; count domain vẫn dùng `note_count` của backend |
| P3-D2 | Header trang khi chỉ có 1 trang | Ẩn | Đúng plan §6.3 — giảm nhiễu cho trường hợp phổ biến |
| P3-D3 | Nhãn trang có nên là link | Link external khi có URL; span thuần cho “Không rõ trang” | `<a>` không href sai ngữ nghĩa + bị loại khỏi role tree |
| P3-D4 | GroupSection domain có link nguồn không | Không (không truyền `sourceUrl` cho Search) | Domain có nhiều trang — không có URL duy nhất để mở |
