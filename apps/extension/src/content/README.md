# content/ — Hàm tiêm vào trang

Không có content script thường trực (chỉ quyền `activeTab` + `scripting`). Background tiêm hàm khi người dùng thao tác (menu chuột phải, phím tắt).

**Quy tắc bắt buộc:**
- Mỗi hàm **tự chứa hoàn toàn**: không import, không dùng biến/helper bên ngoài — Chrome tuần tự hoá thân hàm.
- Chỉ được `export type`/`interface` để background dùng chung kiểu.
- Nội dung trang là dữ liệu không tin cậy: đọc bằng `textContent`, tạo DOM bằng `createElement` — không `innerHTML`.
