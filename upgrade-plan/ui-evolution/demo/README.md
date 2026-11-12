# Demo — Thư viện ở chế độ mở rộng (W03)

> **Trạng thái:** demo tĩnh để review · **Phạm vi:** một màn hình có dữ liệu, light mode · **Ngày:** 2026-11-12
> Tham chiếu: [`../plan.md`](../plan.md) §3.3 · [`../screen-to-design.md`](../screen-to-design.md) W03 · wireframe [`../../redesign_notebook.svg`](../../redesign_notebook.svg)

## Câu hỏi thiết kế (How Might We)

> Làm thế nào để người dùng đang ở cửa sổ mở rộng (~1000px) vừa **quét nhanh danh sách ghi chú**, vừa **đọc chi tiết** và **sửa tại chỗ** mà không phải mở modal, không mất ngữ cảnh và không phải nhớ mình đang ở đâu?

## Hướng đề xuất

**Split-view 3 cột** cho màn Thư viện khi sidebar/cửa sổ được mở rộng:

1. **Folder rail** — lọc theo thư mục, kèm số lượng và tìm thư mục.
2. **Note list** — danh sách gọn, đủ tiêu đề + trích đoạn + ngày + thư mục + trạng thái.
3. **Reader/editor** — đọc trước; bấm **Sửa** thì form thay thế ngay trong cột phải.

### Vì sao hướng này

- **Đúng mẫu W03** và tận dụng chiều rộng thật của cửa sổ mở rộng; danh sách và nội dung không tranh chỗ.
- **Giữ ngữ cảnh:** người dùng luôn thấy danh sách bên trái khi đọc/sửa, chuyển ghi chú chỉ là một cú click.
- **Đọc trước, sửa sau:** mặc định mở reader an toàn hơn; editor chỉ xuất hiện khi được yêu cầu, tránh sửa nhầm.
- **Không phá ngôn ngữ thị giác hiện tại:** giữ token sáng, accent xanh, font hệ thống, radius 8px; chỉ tăng phân cấp, khoảng thở và mật độ.
- **Banner đồng bộ luôn hiện** ngay trên danh sách, vì đây là bất biến hành vi (không mất ghi chú) chứ không phải chi tiết trang trí.

## Giả định cần kiểm chứng

| # | Giả định | Cách kiểm chứng |
|---|---|---|
| 1 | Ở màn rộng, người dùng vừa đọc một ghi chú vừa liếc danh sách để chuyển ghi chú khác | Quan sát dogfood / usability test 5 người |
| 2 | Folder rail hữu ích ở ≥900px; dưới ngưỡng đó nên ẩn và đưa vào nút lọc | Thử 900px và đo số lần dùng filter |
| 3 | Người dùng muốn đọc trước rồi mới sửa, không muốn mở thẳng editor | So sánh tỉ lệ Sửa / mở note trong dogfood |
| 4 | Tóm tắt AI nên nằm trong mạch nội dung và có thể thu gọn, không chiếm ưu thế hơn nội dung gốc | Hỏi người dùng có mở/đóng card, có đọc phần tóm tắt không |
| 5 | Danh sách chỉ cần tiêu đề + 2 dòng trích đoạn là đủ để nhận diện ghi chú | Kiểm tra tỉ lệ chọn đúng note, thời gian tìm note |
| 6 | Trạng thái đồng bộ (Sẵn sàng / Đang xử lý / Lỗi AI / Chưa gửi) đủ rõ ở mật độ danh sách | Kiểm tra nhận biết trạng thái không cần mở note |

## Phạm vi MVP của demo

- Một màn **Thư viện có dữ liệu**, light mode, ở 1000–1200px.
- **3 cột:** folder rail · note list · reader/editor.
- Folder rail: tìm thư mục, mục "Tất cả ghi chú", 3 thư mục, số lượng, footer thao tác.
- Note list: 7 ghi chú mẫu, note đang mở, trạng thái Sẵn sàng / Đang xử lý / Lỗi AI.
- Banner "1 ghi chú chưa gửi được" với **Gửi lại** và **Xem**.
- Reader: breadcrumb, trạng thái, tiêu đề, thời gian + nguồn, nội dung, card **Tóm tắt AI** thu gọn/mở rộng.
- Chuyển **Sửa ↔ Huỷ** bằng CSS-only (`:has()` + checkbox ẩn); form gồm tiêu đề, nội dung + đếm ký tự, thư mục.
- Footer đổi theo chế độ: "Đã lưu" + Tóm tắt lại / Sửa / Xoá ↔ "Chưa lưu thay đổi" + Huỷ / Lưu.
- Responsive: ẩn folder rail ở ≤900px; xếp dọc list/reader ở ≤720px.

## Không làm trong demo này

- **Dark mode** và token dark placeholder.
- Các màn khác: Tìm kiếm, Tóm tắt vùng chọn, Cài đặt, Chat, popup.
- Trạng thái **empty / loading / error toàn màn**, hộp thoại **409**, xoá hàng loạt, quản lý thư mục.
- Dữ liệu thật, API, IndexedDB, outbox, đồng bộ, phân quyền.
- Chọn nhiều ghi chú, thao tác hàng loạt, kéo thả.
- Component hóa thành React/design-system, test, a11y audit đầy đủ.
- Container query: demo dùng **viewport media query** cho đơn giản; production phải dùng **container query ~560px** theo [`../plan.md`](../plan.md) §3.3.
- Pixel-perfect theo Figma (chưa có Figma).

## Cách mở

Mở trực tiếp:

```bash
xdg-open upgrade-plan/ui-evolution/demo/index.html
```

Hoặc chạy server tĩnh trong thư mục demo:

```bash
cd upgrade-plan/ui-evolution/demo
python3 -m http.server 8080
# http://localhost:8080
```

Nên xem ở **1200×800** (thoải mái) và **1000×760** (kích thước landscape tham chiếu). Ảnh chụp sẵn:

- `preview-1200.png` — reader ở 1200×800
- `preview-1000.png` — reader ở 1000×760
- `preview-1000-edit.png` — editor ở 1000×760

## Ghi chú triển khai

- File: [`index.html`](index.html) · [`styles.css`](styles.css).
- Không có JavaScript; tương tác đọc/sửa dùng `label[for]` + `input:checked` + `.app:has(...)`.
- Token giữ theo UI hiện tại: `--bg #ffffff`, `--surface #f6f8fa`, `--fg #1f2328`, `--muted #59636e`, `--border #d0d7de`, `--accent #0b57d0`; radius 8px, font hệ thống.
- Các điểm cần chốt khi đưa vào code thật: chiều rộng 3 cột, ngưỡng chuyển layout, cách hiển thị card tóm tắt khi đã thu gọn, và việc giữ editor trong cột phải thay modal ở landscape.
